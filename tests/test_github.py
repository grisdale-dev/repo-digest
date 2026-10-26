from datetime import UTC, datetime

import httpx
import pytest
import respx

from repo_digest.github import (
    GITHUB_API,
    Commit,
    fetch_commits,
    fetch_commits_between,
    parse_repo,
)


@pytest.mark.parametrize(
    "value",
    [
        "anthropics/anthropic-sdk-python",
        "https://github.com/anthropics/anthropic-sdk-python",
        "https://github.com/anthropics/anthropic-sdk-python.git",
        "  anthropics/anthropic-sdk-python/  ",
    ],
)
def test_parse_repo_accepts_common_forms(value: str) -> None:
    assert parse_repo(value) == ("anthropics", "anthropic-sdk-python")


@pytest.mark.parametrize(
    "value", ["", "just-a-name", "https://gitlab.com/a/b", "a/b/c", "a/b?x=1", 'a"><x/b']
)
def test_parse_repo_rejects_invalid_input(value: str) -> None:
    with pytest.raises(ValueError):
        parse_repo(value)


def _api_commit(sha: str, message: str) -> dict[str, object]:
    """The shape GitHub returns for one commit (only the fields we use)."""
    return {
        "sha": sha,
        "commit": {
            "message": message,
            "author": {"name": "Ada", "date": "2026-10-01T12:00:00Z"},
        },
    }


@respx.mock
def test_fetch_commits_maps_fields_and_follows_pagination() -> None:
    url = f"{GITHUB_API}/repos/octo/demo/commits"
    route = respx.get(url).mock(
        side_effect=[
            httpx.Response(
                200, json=[_api_commit("a1", "feat: add X"), _api_commit("b2", "fix: Y")]
            ),
            httpx.Response(200, json=[_api_commit("c3", "docs: Z")]),
            httpx.Response(200, json=[]),
        ]
    )

    with httpx.Client() as client:
        commits = fetch_commits(
            client,
            "octo",
            "demo",
            since=datetime(2026, 9, 1, tzinfo=UTC),
            until=datetime(2026, 10, 1, tzinfo=UTC),
        )

    assert [c.sha for c in commits] == ["a1", "b2", "c3"]
    assert commits[0] == Commit(
        sha="a1",
        message="feat: add X",
        author="Ada",
        date=datetime(2026, 10, 1, 12, tzinfo=UTC),
    )
    first_request = route.calls[0].request
    assert first_request.url.params["since"] == "2026-09-01T00:00:00+00:00"
    assert first_request.url.params["until"] == "2026-10-01T00:00:00+00:00"


@respx.mock
def test_fetch_commits_raises_on_http_error() -> None:
    respx.get(f"{GITHUB_API}/repos/octo/missing/commits").mock(return_value=httpx.Response(404))
    with httpx.Client() as client, pytest.raises(httpx.HTTPStatusError):
        fetch_commits(
            client,
            "octo",
            "missing",
            since=datetime(2026, 9, 1, tzinfo=UTC),
            until=datetime(2026, 10, 1, tzinfo=UTC),
        )


@respx.mock
def test_fetch_commits_stops_at_limit() -> None:
    route = respx.get(f"{GITHUB_API}/repos/octo/demo/commits").mock(
        return_value=httpx.Response(200, json=[_api_commit(f"s{i}", "m") for i in range(3)])
    )
    with httpx.Client() as client:
        commits = fetch_commits(
            client,
            "octo",
            "demo",
            since=datetime(2026, 9, 1, tzinfo=UTC),
            until=datetime(2026, 10, 1, tzinfo=UTC),
            limit=5,
        )
    assert [c.sha for c in commits] == ["s0", "s1", "s2", "s0", "s1"]
    assert route.call_count == 2  # no third request once the limit is reached


def _compare_page(total: int, shas: list[str]) -> httpx.Response:
    return httpx.Response(
        200, json={"total_commits": total, "commits": [_api_commit(s, "m") for s in shas]}
    )


@respx.mock
def test_fetch_commits_between_returns_newest_first() -> None:
    respx.get(f"{GITHUB_API}/repos/octo/demo/compare/v1...v2").mock(
        return_value=_compare_page(3, ["old", "mid", "new"])
    )
    with httpx.Client() as client:
        commits = fetch_commits_between(client, "octo", "demo", "v1", "v2")
    assert [c.sha for c in commits] == ["new", "mid", "old"]


@respx.mock
def test_fetch_commits_between_with_limit_fetches_only_the_newest_pages() -> None:
    # 250 commits over 3 pages (100, 100, 50), oldest first. With limit=60 we need pages 2-3.
    pages = {
        1: [f"c{i:03}" for i in range(0, 100)],
        2: [f"c{i:03}" for i in range(100, 200)],
        3: [f"c{i:03}" for i in range(200, 250)],
    }
    route = respx.get(f"{GITHUB_API}/repos/octo/demo/compare/v1...HEAD").mock(
        side_effect=lambda request: _compare_page(250, pages[int(request.url.params["page"])])
    )
    with httpx.Client() as client:
        commits = fetch_commits_between(client, "octo", "demo", "v1", "HEAD", limit=60)

    assert [c.sha for c in commits] == [f"c{i:03}" for i in range(249, 189, -1)]
    requested = sorted(int(call.request.url.params["page"]) for call in route.calls)
    assert requested == [1, 2, 3]  # page 1 for the total, then the newest pages
