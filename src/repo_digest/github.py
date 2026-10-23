"""Fetching commit history from the GitHub REST API.

Exercise 1: implement everything marked TODO until `uv run pytest` passes.
"""

from datetime import datetime

import httpx
from pydantic import BaseModel

GITHUB_API = "https://api.github.com"


class Commit(BaseModel):
    """One commit, trimmed to what the summariser needs."""

    # TODO: add the fields the tests expect: sha (str), message (str), author (str), date (datetime)


def parse_repo(value: str) -> tuple[str, str]:
    """Turn user input into (owner, repo).

    Accepts "owner/repo", "https://github.com/owner/repo" and "https://github.com/owner/repo.git".
    Raises ValueError for anything else.
    """
    raise NotImplementedError  # TODO


def fetch_commits(
    client: httpx.Client,
    owner: str,
    repo: str,
    since: datetime,
    until: datetime,
) -> list[Commit]:
    """Return the commits between `since` and `until`, newest first.

    Uses GET /repos/{owner}/{repo}/commits with the `since`, `until` and `per_page` query params.
    Follows pagination until there are no more pages. Hint: look at the `Link` header,
    or keep requesting `page=2, 3, ...` until you get an empty list.
    """
    raise NotImplementedError  # TODO
