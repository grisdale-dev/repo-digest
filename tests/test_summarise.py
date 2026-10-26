import json
from datetime import UTC, datetime

import httpx
import pytest
import respx
from openai import OpenAI

from repo_digest.github import Commit
from repo_digest.summarise import (
    MAX_BODY_CHARS,
    SummaryError,
    format_commits,
    summarise,
)

BASE_URL = "https://llm.test/v1"
ENDPOINT = f"{BASE_URL}/chat/completions"

COMMITS = [
    Commit(
        sha="a1b2c3d4e5f6",
        message="feat: add offline mode\n\nWorks without a network.",
        author="Ada",
        date=datetime(2026, 10, 2, tzinfo=UTC),
    ),
    Commit(
        sha="0f9e8d7c6b5a",
        message="fix: crash on empty list",
        author="Lin",
        date=datetime(2026, 10, 1, tzinfo=UTC),
    ),
]

VALID_NOTES = {
    "summary": "Adds offline mode.",
    "features": [{"description": "Offline mode.", "commits": ["a1b2c3d"]}],
    "fixes": [{"description": "No more crash on empty lists.", "commits": ["0f9e8d7"]}],
}


def completion(
    content: str, prompt_tokens: int = 100, completion_tokens: int = 20
) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "c1",
            "object": "chat.completion",
            "created": 0,
            "model": "test-model",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content},
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        },
    )


@pytest.fixture
def client() -> OpenAI:
    # Pass a plain httpx client so respx can intercept requests. The SDK defaults to httpx2 and
    # accepts legacy httpx clients at runtime, but its type hints only name httpx2.
    http_client = httpx.Client()
    return OpenAI(
        api_key="test",
        base_url=BASE_URL,
        max_retries=0,
        http_client=http_client,  # type: ignore[arg-type]
    )


@respx.mock
def test_returns_validated_notes_and_sends_expected_request(client: OpenAI) -> None:
    route = respx.post(ENDPOINT).mock(return_value=completion(json.dumps(VALID_NOTES)))

    result = summarise(client, "octo/demo", COMMITS, model="test-model")

    assert result.notes.features[0].commits == ["a1b2c3d"]
    assert result.attempts == 1
    assert result.usage.total_tokens == 120
    assert result.truncated is False

    body = json.loads(route.calls[0].request.content)
    assert body["model"] == "test-model"
    assert body["response_format"] == {"type": "json_object"}
    assert body["thinking"] == {"type": "disabled"}
    assert "json" in body["messages"][0]["content"].lower()  # DeepSeek JSON mode requires this
    assert "a1b2c3d feat: add offline mode" in body["messages"][1]["content"]


@respx.mock
def test_retries_with_feedback_after_invalid_json(client: OpenAI) -> None:
    route = respx.post(ENDPOINT).mock(
        side_effect=[completion('{"summary": '), completion(json.dumps(VALID_NOTES))]
    )

    result = summarise(client, "octo/demo", COMMITS, model="test-model")

    assert result.attempts == 2
    assert result.usage.total_tokens == 240  # both attempts are counted
    retry_messages = json.loads(route.calls[1].request.content)["messages"]
    assert retry_messages[-2] == {"role": "assistant", "content": '{"summary":'}
    assert "corrected JSON" in retry_messages[-1]["content"]


@respx.mock
def test_rejects_invented_shas(client: OpenAI) -> None:
    invented = {**VALID_NOTES, "fixes": [{"description": "Fix.", "commits": ["deadbee"]}]}
    route = respx.post(ENDPOINT).mock(
        side_effect=[completion(json.dumps(invented)), completion(json.dumps(VALID_NOTES))]
    )

    result = summarise(client, "octo/demo", COMMITS, model="test-model")

    assert result.attempts == 2
    feedback = json.loads(route.calls[1].request.content)["messages"][-1]["content"]
    assert "deadbee" in feedback


@respx.mock
def test_retries_on_empty_content(client: OpenAI) -> None:
    respx.post(ENDPOINT).mock(side_effect=[completion(""), completion(json.dumps(VALID_NOTES))])
    assert summarise(client, "octo/demo", COMMITS, model="test-model").attempts == 2


@respx.mock
def test_gives_up_after_max_attempts(client: OpenAI) -> None:
    route = respx.post(ENDPOINT).mock(return_value=completion("not json"))
    with pytest.raises(SummaryError) as exc:
        summarise(client, "octo/demo", COMMITS, model="test-model", max_attempts=3)
    assert route.call_count == 3
    assert exc.value.usage.total_tokens == 360  # failed attempts still cost tokens


def test_rejects_empty_commit_list(client: OpenAI) -> None:
    with pytest.raises(ValueError):
        summarise(client, "octo/demo", [], model="test-model")


def test_format_commits_truncates_long_bodies() -> None:
    long = Commit(
        sha="abcdef123456",
        message="title\n\n" + "x" * (MAX_BODY_CHARS + 50),
        author="A",
        date=datetime(2026, 1, 1, tzinfo=UTC),
    )
    text = format_commits([long])
    assert text.startswith("abcdef1 title\n    ")
    assert text.endswith("…")
    assert text.count("x") == MAX_BODY_CHARS
