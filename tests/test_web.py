from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import Any

import httpx
import httpx2
import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError

from repo_digest import digest, web
from repo_digest.config import Settings
from repo_digest.digest import CommitRange, DateRange, RefRange
from repo_digest.github import Commit
from repo_digest.notes import Change, ReleaseNotes
from repo_digest.summarise import Summary, SummaryError, Usage

SETTINGS = Settings("key", "https://llm.test", "test-model", None, 1000)
COMMIT = Commit(sha="a1b2c3d4e5", message="m", author="A", date=datetime(2026, 10, 1, tzinfo=UTC))
NOTES = ReleaseNotes(summary="Adds <X>.", features=[Change(description="X.", commits=["a1b2c3d"])])


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    recorded: dict[str, Any] = {}

    def fake_fetch(_gh: object, owner: str, repo: str, rng: CommitRange) -> list[Commit]:
        recorded["fetch"] = (owner, repo, rng)
        return [COMMIT]

    def fake_summarise(
        _llm: object, repo: str, commits: Sequence[Commit], *, model: str
    ) -> Summary:
        recorded["summarise"] = (repo, model)
        return Summary(NOTES, Usage(100, 20), attempts=1, commits_used=1, truncated=False)

    monkeypatch.setattr(digest, "fetch_range", fake_fetch)
    monkeypatch.setattr(web, "summarise", fake_summarise)
    return recorded


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(web.create_app(SETTINGS)) as c:
        yield c


def test_index_serves_the_page(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "repo-digest" in response.text and "/api/digest" in response.text


def test_digest_defaults_to_last_30_days(client: TestClient, calls: dict[str, Any]) -> None:
    response = client.post("/api/digest", json={"repo": "https://github.com/octo/demo"})

    assert response.status_code == 200
    data = response.json()
    assert data["repo"] == "octo/demo"
    assert data["model"] == "test-model"
    assert data["usage"] == {"input_tokens": 100, "output_tokens": 20}
    assert data["markdown"].startswith("Adds <X>.")
    assert "Adds &lt;X&gt;." in data["html"]
    owner, repo, rng = calls["fetch"]
    assert isinstance(rng, DateRange) and (rng.until - rng.since).days == 30


def test_digest_date_range_end_is_inclusive(client: TestClient, calls: dict[str, Any]) -> None:
    client.post(
        "/api/digest", json={"repo": "octo/demo", "since": "2026-09-01", "until": "2026-09-30"}
    )
    _, _, rng = calls["fetch"]
    assert rng == DateRange(datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 10, 1, tzinfo=UTC))


def test_digest_tag_range(client: TestClient, calls: dict[str, Any]) -> None:
    client.post("/api/digest", json={"repo": "octo/demo", "base": "v1.0"})
    assert calls["fetch"][2] == RefRange("v1.0", "HEAD")


@pytest.mark.parametrize(
    "body",
    [
        {"repo": "not a repo"},
        {"repo": "octo/demo", "head": "v2"},
        {"repo": "octo/demo", "base": "v1", "since": "2026-01-01"},
        {"repo": "octo/demo", "since": "2026-10-05", "until": "2026-10-01"},
        {"repo": "octo/demo", "base": "../../users"},
    ],
)
def test_invalid_input_is_400(
    client: TestClient, calls: dict[str, Any], body: dict[str, str]
) -> None:
    response = client.post("/api/digest", json=body)
    assert response.status_code == 400
    assert "fetch" not in calls


def _github_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.github.com/x")
    return httpx.HTTPStatusError("e", request=request, response=httpx.Response(status))


@pytest.mark.parametrize(("github_status", "expected"), [(404, 404), (403, 503), (500, 503)])
def test_github_errors_are_mapped(
    client: TestClient,
    calls: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    github_status: int,
    expected: int,
) -> None:
    def failing(*_args: object) -> list[Commit]:
        raise _github_error(github_status)

    monkeypatch.setattr(digest, "fetch_range", failing)
    response = client.post("/api/digest", json={"repo": "octo/demo"})
    assert response.status_code == expected
    assert response.json()["detail"]


def test_no_commits_is_404(
    client: TestClient, calls: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(digest, "fetch_range", lambda *_args: [])
    response = client.post("/api/digest", json={"repo": "octo/demo"})
    assert response.status_code == 404
    assert "No commits" in response.json()["detail"]
    assert "summarise" not in calls


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (SummaryError("bad"), 502),
        (APIConnectionError(request=httpx2.Request("POST", "https://llm.test")), 503),
    ],
)
def test_llm_errors_are_mapped(
    client: TestClient,
    calls: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected: int,
) -> None:
    def failing(*_args: object, **_kwargs: object) -> Summary:
        raise error

    monkeypatch.setattr(web, "summarise", failing)
    response = client.post("/api/digest", json={"repo": "octo/demo"})
    assert response.status_code == expected
