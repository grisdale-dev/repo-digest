"""Command-line interface: `repo-digest owner/repo [range options]` prints release notes."""

import argparse
import io
import sys
from datetime import UTC, date, datetime, time

import httpx
from openai import APIError, OpenAI

from repo_digest import digest
from repo_digest.config import load_settings
from repo_digest.digest import CommitRange, DateRange, RefRange
from repo_digest.github import make_client, parse_repo
from repo_digest.summarise import SummaryError, summarise

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


def _range_from_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> CommitRange:
    if args.head and not args.base:
        parser.error("--to needs --from")
    if args.base:
        if args.since or args.until:
            parser.error("use either dates (--since/--until) or refs (--from/--to), not both")
        try:
            return RefRange(args.base, args.head or "HEAD")
        except ValueError as e:
            parser.error(str(e))
    until = args.until or datetime.now(UTC)
    if args.since is None:
        return digest.last_days(now=until)
    try:
        return DateRange(args.since, until)
    except ValueError:
        parser.error("--since must be before --until")


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
    rng = _range_from_args(parser, args)

    def log(message: str) -> None:
        if not args.quiet:
            print(message, file=sys.stderr)

    def fail(message: str) -> int:
        print(f"error: {message}", file=sys.stderr)
        return 1

    try:
        settings = load_settings()
    except RuntimeError as e:
        return fail(str(e))
    model = args.model or settings.llm_model

    try:
        with make_client(settings.github_token) as gh:
            commits = digest.fetch_range(gh, owner, repo, rng)
    except httpx.HTTPStatusError as e:
        return fail(digest.github_error_message(e, rng))
    except httpx.TransportError as e:
        return fail(f"couldn't reach GitHub: {e}")

    if not commits:
        return fail(f"no commits in {owner}/{repo} for {rng.describe()}.")
    log(f"Found {len(commits)} commits in {owner}/{repo} ({rng.describe()}).")
    log(f"Summarising with {model}…")

    llm = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    try:
        result = summarise(llm, f"{owner}/{repo}", commits, model=model)
    except SummaryError as e:
        return fail(str(e))
    except APIError as e:
        return fail(f"LLM API request failed: {e}")

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
