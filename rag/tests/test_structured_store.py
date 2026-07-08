"""Stage 3: the structured store must answer list/tag/keyword/date/latest
queries correctly and deterministically — this is exactly what semantic
search can't guarantee, so it needs its own coverage independent of any LLM.
"""
from ragapp.schema import StructuredQuerySpec


def test_store_unavailable_when_file_missing(empty_store):
    assert empty_store.available is False
    assert "not built" in empty_store.describe()


def test_store_available_and_describes_counts(store):
    assert store.available is True
    desc = store.describe()
    assert "decisions: 2" in desc
    assert "rules: 1" in desc
    assert "warnings: 1" in desc
    assert "changes: 1" in desc


def test_filter_by_item_type_returns_only_that_type(store):
    results = store.query(StructuredQuerySpec(item_types=["decisions"]))
    assert len(results) == 2
    assert all(r["item_type"] == "decisions" for r in results)


def test_no_item_types_returns_all_types(store):
    results = store.query(StructuredQuerySpec())
    assert {r["item_type"] for r in results} == {"decisions", "rules", "warnings", "changes"}


def test_keyword_filter_matches_hebrew_text_case_insensitively(store):
    results = store.query(StructuredQuerySpec(keywords=["RTL"]))
    assert len(results) == 1
    assert results[0]["id"] == "rule-001"


def test_keyword_filter_with_no_match_returns_empty(store):
    results = store.query(StructuredQuerySpec(keywords=["שוקולד"]))
    assert results == []


def test_tag_filter_matches_tags_scope_and_area(store):
    by_tag = store.query(StructuredQuerySpec(tags=["db"]))
    assert [r["id"] for r in by_tag] == ["dec-001"]

    by_scope = store.query(StructuredQuerySpec(tags=["ui"]))
    assert [r["id"] for r in by_scope] == ["rule-001"]

    by_area = store.query(StructuredQuerySpec(tags=["AuthGate"]))
    assert [r["id"] for r in by_area] == ["warn-001"]


def test_date_from_is_inclusive_lower_bound(store):
    results = store.query(StructuredQuerySpec(date_from="2026-07-01"))
    ids = {r["id"] for r in results}
    assert ids == {"rule-001", "warn-001", "chg-001"}  # everything on/after July 1


def test_date_to_is_inclusive_upper_bound(store):
    results = store.query(StructuredQuerySpec(date_to="2026-06-12"))
    ids = {r["id"] for r in results}
    assert ids == {"dec-001", "dec-002"}


def test_date_range_narrows_to_window(store):
    results = store.query(StructuredQuerySpec(date_from="2026-07-01", date_to="2026-07-02"))
    ids = {r["id"] for r in results}
    assert ids == {"rule-001", "chg-001"}


def test_results_sorted_newest_first(store):
    results = store.query(StructuredQuerySpec())
    dates = [r["observed_at"] for r in results]
    assert dates == sorted(dates, reverse=True)


def test_latest_only_keeps_newest_items_capped_at_five(store):
    results = store.query(StructuredQuerySpec(latest_only=True))
    assert results[0]["id"] == "warn-001"  # 2026-07-03 is the newest item overall
    assert len(results) <= 5


def test_limit_is_respected(store):
    results = store.query(StructuredQuerySpec(item_types=["decisions"], limit=1))
    assert len(results) == 1
