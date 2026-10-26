from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from repo_digest import cli, digest
from repo_digest.config import Settings
from repo_digest.github import Commit
from repo_digest.notes import Change, ReleaseNotes
from repo_digest.summarise import Summary, Usage

COMMIT = Commit(
    sha="a1b2c3d4e5", message="feat: x", author="A", date=datetime(2026, 10, 1, tzinfo=UTC)
)
NOTES = ReleaseNotes(summary="Adds X ⚠️.", features=[Change(description="X.", commits=["a1b2c3d"])])


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace settings, GitHub and the LLM with fakes; record how they were called."""
    recorded: dict[str, Any] = {}
    settings = Settings("key", "https://llm.test", "test-model", None, 1000)
    monkeypatch.setattr(cli, "load_settings", lambda: settings)

    def fake_fetch(
        _client: object,
        owner: str,
        repo: str,
        since: datetime,
        until: datetime,
        limit: int | None = None,
    ) -> list[Commit]:
        recorded["fetch"] = (owner, repo, since, until)
        return [COMMIT]

    def fake_between(
        _client: object, owner: str, repo: str, base: str, head: str, limit: int | None = None
    ) -> list[Commit]:
        recorded["between"] = (owner, repo, base, head)
        return [COMMIT]

    def fake_summarise(
        _client: object, repo: str, commits: Sequence[Commit], *, model: str
    ) -> Summary:
        recorded["summarise"] = (repo, list(commits), model)
        return Summary(NOTES, Usage(100, 20), attempts=1, commits_used=1, truncated=False)

    monkeypatch.setattr(digest, "fetch_commits", fake_fetch)
    monkeypatch.setattr(digest, "fetch_commits_between", fake_between)
    monkeypatch.setattr(cli, "summarise", fake_summarise)
    return recorded


def test_defaults_to_last_30_days_and_prints_markdown(
    calls: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["https://github.com/octo/demo"]) == 0

    owner, repo, since, until = calls["fetch"]
    assert (owner, repo) == ("octo", "demo")
    assert until - since == timedelta(days=digest.DEFAULT_DAYS)
    assert calls["summarise"][2] == "test-model"
    out = capsys.readouterr()
    assert out.out.startswith("Adds X ⚠️.")
    assert "Found 1 commits" in out.err


def test_date_range(calls: dict[str, Any]) -> None:
    assert cli.main(["octo/demo", "--since", "2026-09-01", "--until", "2026-10-01", "-q"]) == 0
    _, _, since, until = calls["fetch"]
    assert since == datetime(2026, 9, 1, tzinfo=UTC)
    assert until == datetime(2026, 10, 1, tzinfo=UTC)


def test_ref_range_defaults_head(calls: dict[str, Any]) -> None:
    assert cli.main(["octo/demo", "--from", "v1.0", "-q"]) == 0
    assert calls["between"] == ("octo", "demo", "v1.0", "HEAD")
    assert "fetch" not in calls


def test_model_override(calls: dict[str, Any]) -> None:
    cli.main(["octo/demo", "--model", "other-model", "-q"])
    assert calls["summarise"][2] == "other-model"


def test_writes_output_file(calls: dict[str, Any], tmp_path: Path) -> None:
    target = tmp_path / "NOTES.md"
    assert cli.main(["octo/demo", "-o", str(target), "-q"]) == 0
    assert target.read_text(encoding="utf-8").startswith("Adds X ⚠️.")


@pytest.mark.parametrize(
    "argv",
    [
        ["not-a-repo"],
        ["octo/demo", "--since", "yesterday"],
        ["octo/demo", "--to", "v2"],
        ["octo/demo", "--from", "v1", "--since", "2026-01-01"],
        ["octo/demo", "--since", "2026-10-02", "--until", "2026-10-01"],
    ],
)
def test_invalid_arguments_exit_with_usage_error(calls: dict[str, Any], argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 2


def test_github_404_is_a_friendly_error(
    calls: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def not_found(*_args: object, **_kwargs: object) -> list[Commit]:
        request = httpx.Request("GET", "https://api.github.com/x")
        raise httpx.HTTPStatusError("nf", request=request, response=httpx.Response(404))

    monkeypatch.setattr(digest, "fetch_commits", not_found)
    assert cli.main(["octo/missing"]) == 1
    assert "couldn't find that repository" in capsys.readouterr().err


def test_no_commits(
    calls: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(digest, "fetch_commits", lambda *a, **k: [])
    assert cli.main(["octo/demo"]) == 1
    assert "no commits" in capsys.readouterr().err
    assert "summarise" not in calls
