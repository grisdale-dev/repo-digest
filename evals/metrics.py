"""Checks on generated notes that need no LLM: cheap, deterministic, and run on every case."""

from collections import Counter
from dataclasses import asdict, dataclass

from repo_digest.notes import ReleaseNotes

LONG_ENTRY_CHARS = 200  # a release-note bullet longer than this is usually several changes in one


@dataclass(frozen=True)
class StructureStats:
    entries: int
    shas_cited: int  # distinct
    duplicate_shas: int  # SHAs cited by more than one entry
    long_entries: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def structure_stats(notes: ReleaseNotes) -> StructureStats:
    changes = notes.all_changes()
    cited = Counter(sha for change in changes for sha in set(change.commits))
    return StructureStats(
        entries=len(changes),
        shas_cited=len(cited),
        duplicate_shas=sum(1 for n in cited.values() if n > 1),
        long_entries=sum(1 for c in changes if len(c.description) > LONG_ENTRY_CHARS),
    )
