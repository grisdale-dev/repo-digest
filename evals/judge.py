"""LLM-as-judge: score generated notes against the maintainers' own release notes.

Two questions, each answered per item so the scores can be audited:
- Recall: which changes in the human-written notes do the generated notes cover?
- Accuracy: does each generated entry correctly describe its commits?
"""

from collections.abc import Sequence
from typing import Literal

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, ValidationError

from repo_digest.github import Commit
from repo_digest.notes import Change, ReleaseNotes
from repo_digest.summarise import SHORT_SHA, Usage, format_commits

MAX_REFERENCE_CHARS = 15_000

SYSTEM_PROMPT = """\
You grade automatically generated release notes. You get the commit list for a release, the
release notes the maintainers wrote by hand (the reference), and numbered generated entries.

1. List each distinct user-facing change in the reference. Ignore headings, contributor lists,
   install instructions, links and "full changelog" lines. For each, say whether the generated
   notes cover it: "full" (same change, enough detail for a user), "partial" (mentioned, but
   vague or missing what matters), "missed", or "absent" (no commit in the list makes this
   change, e.g. it was released separately, so the generated notes couldn't have known).
   For "missed", give the 7-character SHA of the commit that makes the change in "commit";
   if you can't point to one, the change is "absent".
2. For every generated entry, by its number, say whether it accurately describes what its
   commits do. "accurate": false means it misstates the change, overstates it, or describes
   something the commits don't contain. Being terse or unimportant is not inaccurate.

Respond with JSON only, in exactly this format:
{
  "reference_items": [{"text": "short paraphrase", "coverage": "missed", "commit": "1a2b3c4"}],
  "generated_items": [{"id": 1, "accurate": true, "reason": "only if inaccurate"}]
}
"""


class ReferenceItem(BaseModel):
    text: str
    coverage: Literal["full", "partial", "missed", "absent"]
    commit: str | None = None  # the SHA behind a "missed" change


class GeneratedItem(BaseModel):
    id: int
    accurate: bool
    reason: str = ""


class Verdict(BaseModel):
    reference_items: list[ReferenceItem]
    generated_items: list[GeneratedItem]

    def ground(self, commits: Sequence[Commit]) -> Verdict:
        """Treat a "missed" change as "absent" unless the judge named a real commit for it.

        Without this, the judge's guess about whether a change is in the commits at all was the
        noisiest part of the recall score.
        """
        known = {c.sha[:SHORT_SHA] for c in commits}
        items = [
            i.model_copy(update={"coverage": "absent"})
            if i.coverage == "missed" and (i.commit or "")[:SHORT_SHA] not in known
            else i
            for i in self.reference_items
        ]
        return self.model_copy(update={"reference_items": items})

    @property
    def recall(self) -> float | None:
        """Share of reference changes covered; partial counts as half.

        Changes the commits don't contain ("absent") are left out: no summary of the commits
        could include them.
        """
        score = {"full": 1.0, "partial": 0.5, "missed": 0.0}
        scored = [score[i.coverage] for i in self.reference_items if i.coverage != "absent"]
        return sum(scored) / len(scored) if scored else None

    @property
    def accuracy(self) -> float | None:
        if not self.generated_items:
            return None
        return sum(i.accurate for i in self.generated_items) / len(self.generated_items)


class JudgeError(Exception):
    pass


def number_entries(notes: ReleaseNotes) -> list[tuple[int, str, Change]]:
    """(id, section, change) for every entry, numbered from 1 in display order."""
    sections = [
        ("breaking", notes.breaking),
        ("features", notes.features),
        ("fixes", notes.fixes),
        ("other", notes.other),
    ]
    entries = [(name, change) for name, changes in sections for change in changes]
    return [(i, name, change) for i, (name, change) in enumerate(entries, start=1)]


def judge(
    client: OpenAI,
    commits: Sequence[Commit],
    reference: str,
    notes: ReleaseNotes,
    *,
    model: str,
    max_attempts: int = 2,
) -> tuple[Verdict, Usage]:
    entries = number_entries(notes)
    generated = "\n".join(
        f"{i}. [{section}] {c.description} (commits: {', '.join(c.commits)})"
        for i, section, c in entries
    )
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Commits:\n{format_commits(commits)}\n\n"
            f"Reference release notes:\n{reference[:MAX_REFERENCE_CHARS]}\n\n"
            f"Generated entries:\n{generated or '(none)'}",
        },
    ]
    usage = Usage()
    expected_ids = {i for i, _, _ in entries}

    for _ in range(max_attempts):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=4000,
            extra_body={"thinking": {"type": "disabled"}},
        )
        if response.usage:
            usage += Usage(response.usage.prompt_tokens, response.usage.completion_tokens)
        content = (response.choices[0].message.content or "").strip()
        if not content:
            continue
        try:
            verdict = Verdict.model_validate_json(content)
        except ValidationError as e:
            problem = str(e)
        else:
            got = {item.id for item in verdict.generated_items}
            if got == expected_ids:
                return verdict.ground(commits), usage
            problem = f"Grade every generated entry exactly once: ids {sorted(expected_ids)}"
        messages += [
            {"role": "assistant", "content": content},
            {"role": "user", "content": f"{problem}\nReply with the corrected JSON only."},
        ]

    raise JudgeError(f"No valid verdict after {max_attempts} attempts")
