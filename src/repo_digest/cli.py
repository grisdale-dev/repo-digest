"""Command-line interface: `repo-digest owner/repo [range options]` prints release notes."""

import argparse
import io
import sys
from datetime import UTC, date, datetime, time, timedelta

import httpx
from openai import APIError, OpenAI

from repo_digest.config import load_settings
from repo_digest.github import Commit, fetch_commits, fetch_commits_between, make_client, parse_repo
from repo_digest.summarise import MAX_COMMITS, SummaryError, summarise

DEFAULT_DAYS = 30

EXAMPLES = """\
examples:
  repo-digest astral-sh/uv                              last 30 days
  repo-digest astral-sh/uv --since 2026-10-01           from a date until now
  repo-digest astral-sh/uv --from 0.9.0 --to 0.9.1      between two tags
  repo-digest astral-sh/uv --from 0.9.0                 from a tag to the latest commit
  repo-digest astral-sh/uv -o NOTES.md                  write to a file
"""


def _parse_date(value: str) -> datetime:
    try:
        return datetime.combine(date.fromisoformat(value), time(), tzinfo=UTC)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected a date like 2026-10-01, got {value!r}"
        ) from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-digest",
        description="Turn a GitHub repository's history into readable release notes.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("repo", help="owner/repo or a github.com URL")

    dates = parser.add_argument_group("date range (default: the last 30 days)")
    dates.add_argument("--since", type=_parse_date, metavar="DATE", help="start date, inclusive")
    dates.add_argument("--until", type=_parse_date, metavar="DATE", help="end date, exclusive")

    refs = parser.add_argument_group("ref range (instead of dates)")
    refs.add_argument(
        "--from", dest="base", metavar="REF", help="tag, branch or SHA to start after"
    )
    refs.add_argument("--to", dest="head", metavar="REF", help="tag, branch or SHA to end at")

    parser.add_argument("-o", "--output", metavar="FILE", help="write the Markdown to FILE")
    parser.add_argument("--model", help="override LLM_MODEL from the environment")
    parser.add_argument("-q", "--quiet", action="store_true", help="don't print progress")
    return parser


def _describe_range(args: argparse.Namespace) -> str:
    if args.base:
        return f"{args.base}...{args.head or 'HEAD'}"
    return f"{args.since:%Y-%m-%d} to {args.until:%Y-%m-%d}"


def _fetch(client: httpx.Client, owner: str, repo: str, args: argparse.Namespace) -> list[Commit]:
    # One more than the summariser uses, so it can tell the user the range was truncated.
    limit = MAX_COMMITS + 1
    if args.base:
        return fetch_commits_between(client, owner, repo, args.base, args.head or "HEAD", limit)
    return fetch_commits(client, owner, repo, args.since, args.until, limit)


def _github_error(e: httpx.HTTPStatusError, args: argparse.Namespace) -> str:
    status = e.response.status_code
    if status == 404:
        what = "repository or ref" if args.base else "repository"
        return f"GitHub couldn't find that {what} (404). Is it public and spelled correctly?"
    if status in (403, 429):
        return "GitHub rate limit reached. Set GITHUB_TOKEN in .env to raise it, or wait an hour."
    return f"GitHub API error {status}: {e.response.text[:200]}"


def main(argv: list[str] | None = None) -> int:
    # Windows consoles and redirected output may default to a legacy encoding; the notes use emoji.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        owner, repo = parse_repo(args.repo)
    except ValueError as e:
        parser.error(str(e))
    if args.head and not args.base:
        parser.error("--to needs --from")
    if args.base and (args.since or args.until):
        parser.error("use either dates (--since/--until) or refs (--from/--to), not both")
    if not args.base:
        args.until = args.until or datetime.now(UTC)
        args.since = args.since or args.until - timedelta(days=DEFAULT_DAYS)
        if args.since >= args.until:
            parser.error("--since must be before --until")

    def log(message: str) -> None:
        if not args.quiet:
            print(message, file=sys.stderr)

    try:
        settings = load_settings()
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    model = args.model or settings.llm_model

    try:
        with make_client(settings.github_token) as gh:
            commits = _fetch(gh, owner, repo, args)
    except httpx.HTTPStatusError as e:
        print(f"error: {_github_error(e, args)}", file=sys.stderr)
        return 1
    except httpx.TransportError as e:
        print(f"error: couldn't reach GitHub: {e}", file=sys.stderr)
        return 1

    if not commits:
        print(f"No commits in {owner}/{repo} for {_describe_range(args)}.", file=sys.stderr)
        return 1
    log(f"Found {len(commits)} commits in {owner}/{repo} ({_describe_range(args)}).")
    log(f"Summarising with {model}…")

    llm = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    try:
        result = summarise(llm, f"{owner}/{repo}", commits, model=model)
    except SummaryError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except APIError as e:
        print(f"error: LLM API request failed: {e}", file=sys.stderr)
        return 1

    if result.truncated:
        log(f"Note: only the newest {result.commits_used} commits were summarised.")
    log(
        f"Done in {result.attempts} attempt(s): "
        f"{result.usage.input_tokens:,} input + {result.usage.output_tokens:,} output tokens."
    )

    markdown = result.notes.to_markdown(repo=(owner, repo))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(markdown)
        log(f"Wrote {args.output}")
    else:
        print(markdown, end="")
    return 0
