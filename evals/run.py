"""Run repo-digest on real releases and score it against the maintainers' release notes.

    uv run python -m evals.run --label baseline
    uv run python -m evals.run --label baseline --repeat 3
    uv run python -m evals.run --label quick --only uv,flask

Needs LLM_API_KEY (and ideally GITHUB_TOKEN) in the environment or .env. Writes
evals/results/<label>.json (everything, for later comparison) and <label>.md (a summary table).
"""

import argparse
import json
import statistics
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI

from evals.judge import judge
from evals.metrics import structure_stats
from repo_digest.config import load_settings
from repo_digest.github import fetch_commits_between, make_client, parse_repo
from repo_digest.summarise import MAX_COMMITS, summarise

HERE = Path(__file__).parent


def fetch_release_notes(client: httpx.Client, owner: str, repo: str, tag: str) -> str:
    response = client.get(f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}")
    response.raise_for_status()
    body: str = response.json().get("body") or ""
    return body


def run_case(
    case: dict[str, str], gh: httpx.Client, llm: OpenAI, model: str, judge_model: str
) -> dict[str, Any]:
    owner, repo = parse_repo(case["repo"])
    commits = fetch_commits_between(gh, owner, repo, case["base"], case["head"], MAX_COMMITS + 1)
    reference = fetch_release_notes(gh, owner, repo, case["head"])

    started = time.perf_counter()
    result = summarise(llm, case["repo"], commits, model=model)
    seconds = time.perf_counter() - started

    used = commits[: result.commits_used]
    verdict, judge_usage = judge(llm, used, reference, result.notes, model=judge_model)

    return {
        **case,
        "commits": len(used),
        "truncated": result.truncated,
        "attempts": result.attempts,
        "seconds": round(seconds, 1),
        "tokens": result.usage.total_tokens,
        "judge_tokens": judge_usage.total_tokens,
        "recall": verdict.recall,
        "accuracy": verdict.accuracy,
        **structure_stats(result.notes).as_dict(),
        "notes": result.notes.model_dump(),
        "verdict": verdict.model_dump(),
    }


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x:.0%}"


def _mean(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return statistics.mean(present) if present else None


def _case_summary(name: str, runs: list[dict[str, Any]]) -> str:
    ok = [r for r in runs if "error" not in r]
    errors = len(runs) - len(ok)
    if not ok:
        return f"| {name} | all {errors} runs failed |||||||||"
    return (
        f"| {name} | {ok[0]['commits']} | {_pct(_mean([r['recall'] for r in ok]))} "
        f"| {_pct(_mean([r['accuracy'] for r in ok]))} "
        f"| {statistics.mean(r['entries'] for r in ok):.1f} "
        f"| {sum(r['duplicate_shas'] for r in ok)} | {sum(r['long_entries'] for r in ok)} "
        f"| {statistics.mean(r['attempts'] for r in ok):.1f} "
        f"| {statistics.mean(r['tokens'] for r in ok):,.0f} "
        f"| {statistics.mean(r['seconds'] for r in ok):.1f} |"
        + (f" {errors} failed" if errors else "")
    )


def report(label: str, model: str, rows: list[dict[str, Any]], repeat: int) -> str:
    ok = [r for r in rows if "error" not in r]
    names = list(dict.fromkeys(r["name"] for r in rows))
    lines = [
        f"# Eval: {label}",
        "",
        f"Model: `{model}`, {repeat} run(s) per case; figures are per-run means, and the "
        "duplicate-SHA and long-entry columns are totals across runs. Recall and accuracy are "
        "judged by an LLM; the rest is counted.",
        "",
        "| Case | Commits | Recall | Accuracy | Entries | Dup SHAs | Long entries "
        "| Attempts | Tokens | Seconds |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    lines += [_case_summary(n, [r for r in rows if r["name"] == n]) for n in names]
    if ok:
        # Average per case first, so cases with more successful runs don't weigh more.
        def per_case(key: str) -> list[float | None]:
            return [_mean([r[key] for r in ok if r["name"] == n]) for n in names]

        lines.append(
            f"| **All** | | **{_pct(_mean(per_case('recall')))}** "
            f"| **{_pct(_mean(per_case('accuracy')))}** |||||||"
        )

    misses = [
        (r["name"], r["run"], item["text"])
        for r in ok
        for item in r["verdict"]["reference_items"]
        if item["coverage"] == "missed"
    ]
    wrong = [
        (r["name"], r["run"], item["id"], item["reason"])
        for r in ok
        for item in r["verdict"]["generated_items"]
        if not item["accurate"]
    ]
    if wrong:
        lines += ["", "## Inaccurate entries", ""]
        lines += [f"- **{name}** run {run}, #{i}: {reason}" for name, run, i, reason in wrong]
    if misses:
        lines += ["", "## Missed reference changes", ""]
        lines += [f"- **{name}** run {run}: {text}" for name, run, text in misses]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--label", default="latest", help="name for the results files")
    parser.add_argument("--only", help="comma-separated case names to run")
    parser.add_argument("--repeat", type=int, default=1, help="runs per case (scores are noisy)")
    parser.add_argument("--model", help="model to evaluate (default: LLM_MODEL)")
    parser.add_argument("--judge-model", help="model that grades (default: LLM_MODEL)")
    args = parser.parse_args(argv)

    cases: list[dict[str, str]] = json.loads((HERE / "cases.json").read_text())
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["name"] in wanted]

    settings = load_settings()
    model = args.model or settings.llm_model
    judge_model = args.judge_model or settings.llm_model
    llm = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    rows = []
    with make_client(settings.github_token) as gh:
        for case in cases:
            for run in range(1, args.repeat + 1):
                print(f"{case['name']} run {run}: {case['repo']} {case['base']}...{case['head']}")
                try:
                    rows.append({"run": run, **run_case(case, gh, llm, model, judge_model)})
                except Exception as e:  # one bad case shouldn't lose the others' results
                    print(f"  failed: {e}", file=sys.stderr)
                    rows.append({"run": run, **case, "error": type(e).__name__})

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    meta = {"label": args.label, "model": model, "judge_model": judge_model, "repeat": args.repeat}
    (out / f"{args.label}.json").write_text(
        json.dumps({**meta, "cases": rows}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    summary = report(args.label, model, rows, args.repeat)
    (out / f"{args.label}.md").write_text(summary, encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
