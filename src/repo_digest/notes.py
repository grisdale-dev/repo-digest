"""The structured release-notes format the model must produce, and rendering it."""

import html
import re

from pydantic import BaseModel, Field


class Change(BaseModel):
    """One user-facing change, backed by one or more commits."""

    description: str = Field(min_length=1)
    commits: list[str] = Field(min_length=1, description="Short SHAs of the commits behind it")


class ReleaseNotes(BaseModel):
    summary: str = Field(min_length=1, description="One or two sentences on the release overall")
    breaking: list[Change] = []
    features: list[Change] = []
    fixes: list[Change] = []
    other: list[Change] = []

    def sections(self) -> list[tuple[str, list[Change]]]:
        """Non-empty sections, in display order."""
        all_sections = [
            ("⚠️ Breaking changes", self.breaking),
            ("Features", self.features),
            ("Fixes", self.fixes),
            ("Other", self.other),
        ]
        return [(title, changes) for title, changes in all_sections if changes]

    def all_changes(self) -> list[Change]:
        return [*self.breaking, *self.features, *self.fixes, *self.other]

    def to_markdown(self, repo: tuple[str, str] | None = None) -> str:
        """Render as Markdown. With `repo` (owner, name), commit SHAs become links."""

        def ref(sha: str) -> str:
            if repo is None:
                return f"`{sha}`"
            return f"[`{sha}`]({_commit_url(repo, sha)})"

        lines = [self.summary]
        for title, changes in self.sections():
            lines += ["", f"### {title}", ""]
            lines += [
                f"- {c.description} ({', '.join(ref(s) for s in c.commits)})" for c in changes
            ]
        return "\n".join(lines) + "\n"

    def to_html(self, repo: tuple[str, str]) -> str:
        """Render as an HTML fragment. All model-written text is escaped."""

        def ref(sha: str) -> str:
            url = html.escape(_commit_url(repo, sha))
            return f'<a href="{url}"><code>{html.escape(sha)}</code></a>'

        parts = [f"<p>{_inline(self.summary)}</p>"]
        for title, changes in self.sections():
            parts.append(f"<h3>{html.escape(title)}</h3>")
            items = "".join(
                f'<li>{_inline(c.description)} <span class="refs">'
                f"({', '.join(ref(s) for s in c.commits)})</span></li>"
                for c in changes
            )
            parts.append(f"<ul>{items}</ul>")
        return "\n".join(parts)


def _commit_url(repo: tuple[str, str], sha: str) -> str:
    owner, name = repo
    return f"https://github.com/{owner}/{name}/commit/{sha}"


_CODE_SPAN = re.compile(r"`([^`]+)`")


def _inline(text: str) -> str:
    """Escape text, then turn `backtick spans` into <code> (safe: content is already escaped)."""
    return _CODE_SPAN.sub(r"<code>\1</code>", html.escape(text))
