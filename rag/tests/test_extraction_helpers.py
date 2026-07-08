"""Pure-function helpers used by stage 3 extraction — no LLM involved, so
these run fully offline and guard the section-splitting logic that keeps
each extraction call within a sane prompt size.
"""
from ragapp.extraction import _MAX_SECTION_CHARS, _nearest_anchor, _split_sections


def test_short_text_is_a_single_section():
    text = "# כותרת\n\nפסקה קצרה.\n"
    assert _split_sections(text) == [text]


def test_long_text_splits_on_headings_and_preserves_content():
    section_body = "תוכן " * 400  # ~2000 chars per section
    text = "".join(f"## כותרת {i}\n\n{section_body}\n\n" for i in range(6))
    assert len(text) > _MAX_SECTION_CHARS

    sections = _split_sections(text)

    assert len(sections) > 1
    assert all(len(s) <= _MAX_SECTION_CHARS + len(section_body) for s in sections)
    # nothing gets dropped in the split
    assert "".join(sections) == text


def test_nearest_anchor_finds_first_heading():
    section = "## כותרת ראשית\n\nתוכן כלשהו.\n### תת-כותרת\n"
    assert _nearest_anchor(section) == "## כותרת ראשית"


def test_nearest_anchor_returns_none_without_heading():
    assert _nearest_anchor("סתם פסקה בלי כותרת.\n") is None
