from repo_digest.notes import Change, ReleaseNotes


def test_markdown_skips_empty_sections_and_links_commits() -> None:
    notes = ReleaseNotes(
        summary="Small release.",
        features=[Change(description="Add X.", commits=["a1b2c3d", "e4f5a6b"])],
    )

    md = notes.to_markdown(repo=("octo", "demo"))

    assert md == (
        "Small release.\n"
        "\n"
        "### Features\n"
        "\n"
        "- Add X. ([`a1b2c3d`](https://github.com/octo/demo/commit/a1b2c3d), "
        "[`e4f5a6b`](https://github.com/octo/demo/commit/e4f5a6b))\n"
    )
    assert "Breaking" not in md and "Fixes" not in md


def test_markdown_without_repo_uses_plain_shas() -> None:
    notes = ReleaseNotes(summary="S.", fixes=[Change(description="Fix Y.", commits=["a1b2c3d"])])
    assert "- Fix Y. (`a1b2c3d`)" in notes.to_markdown()
