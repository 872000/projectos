"""Tests for small shared utility helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from armillary.models import Project, ProjectType
from armillary.utils import (
    excerpt_one_liner,
    load_json_str_list,
    summarize_project_matches,
)


def test_load_json_str_list_filters_non_strings(tmp_path: Path) -> None:
    payload = '["ok", 123, null, true, "still-ok", {"x": 1}]'
    path = tmp_path / "mixed.json"
    path.write_text(payload, encoding="utf-8")

    assert load_json_str_list(path) == ["ok", "still-ok"]


def _project(name: str, path: str) -> Project:
    p = Path(path)
    return Project(
        path=p,
        name=name,
        type=ProjectType.GIT,
        umbrella=p.parent,
        last_modified=datetime(2026, 5, 4, 12, 0, 0),
        metadata=None,
    )


def test_summarize_project_matches_unique_names_just_names() -> None:
    matches = [
        _project("alpha", "/repos/alpha"),
        _project("beta", "/repos/beta"),
    ]
    assert summarize_project_matches(matches) == "alpha, beta"


def test_summarize_project_matches_duplicate_names_show_paths() -> None:
    home = str(Path.home())
    matches = [
        _project("foo", f"{home}/projects_prod/foo"),
        _project("foo", f"{home}/RubymineProjects/foo"),
    ]
    out = summarize_project_matches(matches)
    # Both names annotated with their home-shortened paths so the
    # CLI's "Be more specific" prompt is actually actionable.
    assert "foo (~/projects_prod/foo)" in out
    assert "foo (~/RubymineProjects/foo)" in out


def test_summarize_project_matches_partial_duplicate_annotates_all() -> None:
    """When ANY duplicate is in the visible window, every entry gets a
    path so the rendered list is consistent and unambiguous."""
    matches = [
        _project("foo", "/a/foo"),
        _project("foo", "/b/foo"),
        _project("bar", "/c/bar"),
    ]
    out = summarize_project_matches(matches)
    assert "foo (/a/foo)" in out
    assert "foo (/b/foo)" in out
    assert "bar (/c/bar)" in out


def test_summarize_project_matches_truncates_to_limit() -> None:
    matches = [_project(f"p{i}", f"/r/p{i}") for i in range(7)]
    assert summarize_project_matches(matches, limit=3) == "p0, p1, p2 (+4 more)"


def test_summarize_project_matches_empty_returns_empty_string() -> None:
    assert summarize_project_matches([]) == ""


def test_excerpt_one_liner_empty_returns_empty_string() -> None:
    assert excerpt_one_liner("") == ""


def test_excerpt_one_liner_returns_first_sentence() -> None:
    assert excerpt_one_liner("Built in a weekend. Then abandoned for a year.") == (
        "Built in a weekend."
    )


def test_excerpt_one_liner_truncates_without_sentence_boundary() -> None:
    text = "word " * 30
    assert excerpt_one_liner(text) == text[:80]
    assert len(excerpt_one_liner(text)) == 80


def test_excerpt_one_liner_truncates_when_sentence_beyond_limit() -> None:
    text = "A very long opening sentence that keeps going and going. Short tail."
    assert excerpt_one_liner(text, max_chars=20) == text[:20]
