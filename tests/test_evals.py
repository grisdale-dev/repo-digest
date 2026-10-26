from datetime import UTC, datetime

from evals.judge import ReferenceItem, Verdict, number_entries
from evals.metrics import LONG_ENTRY_CHARS, structure_stats
from repo_digest.github import Commit
from repo_digest.notes import Change, ReleaseNotes

NOTES = ReleaseNotes(
    summary="s",
    features=[Change(description="New flag.", commits=["aaaaaaa", "bbbbbbb"])],
    fixes=[Change(description="x" * (LONG_ENTRY_CHARS + 1), commits=["bbbbbbb"])],
    other=[Change(description="Docs.", commits=["ccccccc", "ccccccc"])],
)


def test_structure_stats() -> None:
    stats = structure_stats(NOTES)
    assert stats.entries == 3
    assert stats.shas_cited == 3
    assert stats.duplicate_shas == 1  # bbbbbbb; citing ccccccc twice in one entry doesn't count
    assert stats.long_entries == 1


def test_entries_are_numbered_in_display_order() -> None:
    assert [(i, s) for i, s, _ in number_entries(NOTES)] == [
        (1, "features"),
        (2, "fixes"),
        (3, "other"),
    ]


def test_recall_counts_partial_as_half() -> None:
    items = [
        ReferenceItem(text="a", coverage="full"),
        ReferenceItem(text="b", coverage="partial"),
        ReferenceItem(text="c", coverage="missed"),
        ReferenceItem(text="d", coverage="missed"),
        ReferenceItem(text="e", coverage="absent"),  # not in the commits, so not counted
    ]
    assert Verdict(reference_items=items, generated_items=[]).recall == 0.375


def test_scores_are_none_when_there_is_nothing_to_score() -> None:
    verdict = Verdict(reference_items=[], generated_items=[])
    assert verdict.recall is None
    assert verdict.accuracy is None


def test_missed_changes_need_a_real_commit() -> None:
    when = datetime(2026, 1, 1, tzinfo=UTC)
    commit = Commit(sha="abcdef0123", message="m", author="a", date=when)
    verdict = Verdict(
        reference_items=[
            ReferenceItem(text="real", coverage="missed", commit="abcdef0"),
            ReferenceItem(text="no evidence", coverage="missed"),
            ReferenceItem(text="made up", coverage="missed", commit="1234567"),
        ],
        generated_items=[],
    ).ground([commit])
    assert [i.coverage for i in verdict.reference_items] == ["missed", "absent", "absent"]
