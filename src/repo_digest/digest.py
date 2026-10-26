"""Shared by the CLI and the web app: commit ranges, fetching them, and GitHub error messages."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from repo_digest.github import Commit, fetch_commits, fetch_commits_between
from repo_digest.summarise import MAX_COMMITS

DEFAULT_DAYS = 30


@dataclass(frozen=True)
class DateRange:
    since: datetime
    until: datetime

    def __post_init__(self) -> None:
        if self.since >= self.until:
            raise ValueError("The start date must be before the end date")

    def describe(self) -> str:
        return f"{self.since:%Y-%m-%d} to {self.until:%Y-%m-%d}"


_REF = re.compile(r"[A-Za-z0-9._/+-]{1,100}")


@dataclass(frozen=True)
class RefRange:
    base: str
    head: str = "HEAD"

    def __post_init__(self) -> None:
        # Refs end up in the API URL path, so keep them to characters real tags and branches use.
        for ref in (self.base, self.head):
            if not _REF.fullmatch(ref) or ".." in ref:
                raise ValueError(f"Not a valid tag, branch or commit: {ref!r}")

    def describe(self) -> str:
        return f"{self.base}...{self.head}"


CommitRange = DateRange | RefRange


def last_days(days: int = DEFAULT_DAYS, now: datetime | None = None) -> DateRange:
    until = now or datetime.now(UTC)
    return DateRange(until - timedelta(days=days), until)


def fetch_range(client: httpx.Client, owner: str, repo: str, rng: CommitRange) -> list[Commit]:
    # One more than the summariser uses, so it can report that the range was truncated.
    limit = MAX_COMMITS + 1
    if isinstance(rng, RefRange):
        return fetch_commits_between(client, owner, repo, rng.base, rng.head, limit)
    return fetch_commits(client, owner, repo, rng.since, rng.until, limit)


def github_error_message(e: httpx.HTTPStatusError, rng: CommitRange) -> str:
    status = e.response.status_code
    if status == 404:
        what = "repository or ref" if isinstance(rng, RefRange) else "repository"
        return f"GitHub couldn't find that {what}. Is it public and spelled correctly?"
    if status in (403, 429):
        return "GitHub's rate limit was reached. Please try again later."
    return f"GitHub API error {status}."
