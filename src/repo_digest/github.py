"""Fetching commit history from the GitHub REST API."""

import re
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel

GITHUB_API = "https://api.github.com"
GITHUB_WEB = "https://github.com/"
PER_PAGE = 100
# Characters GitHub allows in owner and repository names.
_NAME = re.compile(r"[A-Za-z0-9_.-]+")


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
    if len(parts) != 2 or not all(_NAME.fullmatch(p) for p in parts):
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
    limit: int | None = None,
) -> list[Commit]:
    """Return the commits between `since` and `until`, newest first.

    Requests pages until GitHub returns an empty one, or until `limit` commits have been
    collected. Raises httpx.HTTPStatusError on API errors.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits"
    commits: list[Commit] = []
    page = 1
    while limit is None or len(commits) < limit:
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
            break
        commits.extend(_to_commit(item) for item in items)
        page += 1
    return commits[:limit]


def fetch_commits_between(
    client: httpx.Client,
    owner: str,
    repo: str,
    base: str,
    head: str,
    limit: int | None = None,
) -> list[Commit]:
    """Return the commits in `head` that aren't in `base` (tags, branches or SHAs), newest first.

    The compare API lists commits oldest first, so when there are more than `limit`, only the
    last pages are fetched. Raises httpx.HTTPStatusError on API errors (404 for an unknown ref).
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/compare/{base}...{head}"

    def get_page(page: int) -> dict[str, Any]:
        response = client.get(url, params={"per_page": PER_PAGE, "page": page})
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data

    first = get_page(1)
    total: int = first["total_commits"]
    last_page = max(1, -(-total // PER_PAGE))  # ceiling division

    first_page_wanted = 1
    if limit is not None:
        # The newest commits are on the last pages. +1 page because the last one may be short.
        first_page_wanted = max(1, last_page - (-(-limit // PER_PAGE)))

    oldest_first: list[Commit] = []
    for page in range(first_page_wanted, last_page + 1):
        data = first if page == 1 else get_page(page)
        oldest_first.extend(_to_commit(item) for item in data["commits"])

    newest_first = oldest_first[::-1]
    return newest_first[:limit]


def make_client(token: str | None = None) -> httpx.Client:
    """An httpx client set up for the GitHub REST API, authenticated if a token is given."""
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(headers=headers, timeout=30)
