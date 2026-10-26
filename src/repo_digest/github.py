"""Fetching commit history from the GitHub REST API."""

from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel

GITHUB_API = "https://api.github.com"
GITHUB_WEB = "https://github.com/"
PER_PAGE = 100


class Commit(BaseModel):
    """One commit, trimmed to what the summariser needs."""

    sha: str
    message: str
    author: str
    date: datetime


def parse_repo(value: str) -> tuple[str, str]:
    """Turn user input into (owner, repo).

    Accepts "owner/repo", "https://github.com/owner/repo" and "https://github.com/owner/repo.git".
    Raises ValueError for anything else.
    """
    path = value.strip().removeprefix(GITHUB_WEB).removesuffix(".git").strip("/")
    parts = path.split("/")
    if len(parts) != 2 or not all(parts) or ":" in path:
        raise ValueError(f"Expected 'owner/repo' or a github.com URL, got {value!r}")
    owner, repo = parts
    return owner, repo


def _to_commit(item: dict[str, Any]) -> Commit:
    """Map one item from the GitHub commits API onto a Commit."""
    commit = item["commit"]
    return Commit(
        sha=item["sha"],
        message=commit["message"],
        author=commit["author"]["name"],
        date=commit["author"]["date"],
    )


def fetch_commits(
    client: httpx.Client,
    owner: str,
    repo: str,
    since: datetime,
    until: datetime,
) -> list[Commit]:
    """Return the commits between `since` and `until`, newest first.

    Requests pages until GitHub returns an empty one. Raises httpx.HTTPStatusError on API errors.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits"
    commits: list[Commit] = []
    page = 1
    while True:
        response = client.get(
            url,
            params={
                "since": since.isoformat(),
                "until": until.isoformat(),
                "per_page": PER_PAGE,
                "page": page,
            },
        )
        response.raise_for_status()
        items: list[dict[str, Any]] = response.json()
        if not items:
            return commits
        commits.extend(_to_commit(item) for item in items)
        page += 1
