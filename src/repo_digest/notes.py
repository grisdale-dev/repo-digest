"""The structured release-notes format the model must produce, and rendering it as Markdown."""

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

    def all_changes(self) -> list[Change]:
        return [*self.breaking, *self.features, *self.fixes, *self.other]

    def to_markdown(self, repo: tuple[str, str] | None = None) -> str:
        """Render as Markdown. With `repo` (owner, name), commit SHAs become links."""

        def ref(sha: str) -> str:
            if repo is None:
                return f"`{sha}`"
            owner, name = repo
            return f"[`{sha}`](https://github.com/{owner}/{name}/commit/{sha})"

        sections = [
            ("⚠️ Breaking changes", self.breaking),
            ("Features", self.features),
            ("Fixes", self.fixes),
            ("Other", self.other),
        ]
        lines = [self.summary]
        for title, changes in sections:
            if not changes:
                continue
            lines += ["", f"### {title}", ""]
            lines += [
                f"- {c.description} ({', '.join(ref(s) for s in c.commits)})" for c in changes
            ]
        return "\n".join(lines) + "\n"
