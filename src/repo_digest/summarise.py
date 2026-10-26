"""Turning commits into structured release notes with an LLM.

Uses the OpenAI-compatible Chat Completions API, so any compatible provider works.
The default is DeepSeek (see config.py).
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError

from repo_digest.github import Commit
from repo_digest.notes import ReleaseNotes

SHORT_SHA = 7
MAX_COMMITS = 300  # newest first; older ones are dropped and Summary.truncated is set
MAX_BODY_CHARS = 400  # per commit message body
MAX_OUTPUT_TOKENS = 4000

_EXAMPLE = {
    "summary": "Adds offline mode and fixes several sync bugs.",
    "breaking": [
        {
            "description": "`sync()` now requires an explicit `timeout` argument.",
            "commits": ["1a2b3c4"],
        }
    ],
    "features": [
        {"description": "Offline mode with automatic resync.", "commits": ["5d6e7f8", "9a0b1c2"]}
    ],
    "fixes": [{"description": "Fixed duplicate items after reconnecting.", "commits": ["3d4e5f6"]}],
    "other": [],
}

SYSTEM_PROMPT = f"""\
You write release notes for software projects from their commit history.

Rules:
- Write for the project's users, not its maintainers: say what changed for them, concisely.
- Merge related commits into one entry. Leave out noise (CI tweaks, typo fixes, dependency bumps,
  merge commits with no content) unless it matters to users.
- "breaking" is only for changes that require users to act (removed or renamed APIs, changed
  defaults, dropped platform support).
- Cite commits by the 7-character SHAs you were given. Never invent a SHA.
- Every category except "summary" may be an empty list.

Respond with JSON only, in exactly this format:
{json.dumps(_EXAMPLE, indent=2)}
"""


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens
        )


class SummaryError(Exception):
    """The model didn't produce valid release notes within the allowed attempts."""

    def __init__(self, message: str, usage: Usage | None = None) -> None:
        super().__init__(message)
        self.usage = usage or Usage()  # tokens spent on the failed attempts


@dataclass(frozen=True)
class Summary:
    notes: ReleaseNotes
    usage: Usage
    attempts: int
    commits_used: int
    truncated: bool


def format_commits(commits: Sequence[Commit]) -> str:
    """Render commits as compact text for the prompt."""
    blocks = []
    for c in commits:
        title, _, body = c.message.strip().partition("\n")
        block = f"{c.sha[:SHORT_SHA]} {title}"
        body = body.strip()
        if body:
            if len(body) > MAX_BODY_CHARS:
                body = body[:MAX_BODY_CHARS] + "…"
            block += "\n" + "\n".join(f"    {line}" for line in body.splitlines())
        blocks.append(block)
    return "\n".join(blocks)


def check_notes(notes: ReleaseNotes, commits: Sequence[Commit]) -> list[str]:
    """Problems with otherwise well-formed notes, e.g. citing commits that don't exist."""
    known = {c.sha[:SHORT_SHA] for c in commits}
    unknown = sorted({s for ch in notes.all_changes() for s in ch.commits} - known)
    return [f"These SHAs are not in the commit list: {', '.join(unknown)}"] if unknown else []


def summarise(
    client: OpenAI,
    repo: str,
    commits: Sequence[Commit],
    *,
    model: str,
    max_attempts: int = 3,
) -> Summary:
    """Ask the model for release notes, validating and retrying with feedback on bad output."""
    if not commits:
        raise ValueError("No commits to summarise")
    used = list(commits[:MAX_COMMITS])

    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Repository: {repo}\nCommits (newest first):\n\n{format_commits(used)}",
        },
    ]
    usage = Usage()

    for attempt in range(1, max_attempts + 1):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=MAX_OUTPUT_TOKENS,
            # Summarising doesn't need step-by-step reasoning; turning it off is faster and cheaper.
            extra_body={"thinking": {"type": "disabled"}},
        )
        if response.usage:
            usage += Usage(response.usage.prompt_tokens, response.usage.completion_tokens)

        content = (response.choices[0].message.content or "").strip()
        if not content:
            continue  # known DeepSeek quirk: occasionally empty, so just ask again

        try:
            notes = ReleaseNotes.model_validate_json(content)
            problems = check_notes(notes, used)
        except ValidationError as e:
            problems = [str(e)]

        if not problems:
            return Summary(notes, usage, attempt, len(used), len(commits) > len(used))

        messages += [
            {"role": "assistant", "content": content},
            {
                "role": "user",
                "content": "That response has problems:\n"
                + "\n".join(problems)
                + "\nReply with the corrected JSON only.",
            },
        ]

    raise SummaryError(f"No valid release notes after {max_attempts} attempts", usage)
