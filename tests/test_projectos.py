"""Tests for ProjectOS services: autopsy, completion, todo analysis, revival, scoring."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from armillary import autopsy_service, completion_service
from armillary import potential_scoring_service, revival_plan_service
from armillary import todo_analysis_service
from armillary.models import Project, ProjectMetadata, ProjectType, Status


def _project(**overrides) -> Project:
    now = datetime.now(timezone.utc)
    md_kwargs = dict(
        branch="main",
        last_commit_ts=now - timedelta(days=120),
        dirty_count=3,
        commit_count=40,
        commit_velocity=[0, 0, 0, 0],
        branch_count=8,
        has_remote=False,
        file_count=150,
        readme_excerpt="A test project",
    )
    md_overrides = overrides.pop("metadata", {}) or {}
    md_kwargs.update(md_overrides)
    md = ProjectMetadata(status=Status.DORMANT, **md_kwargs)
    return Project(
        path=Path("/tmp/fake-proj"),
        name="fake-proj",
        type=ProjectType.GIT,
        umbrella=Path("/tmp"),
        last_modified=now,
        metadata=md,
        **overrides,
    )


def test_autopsy_detects_abandonment():
    report = autopsy_service.autopsy(_project())
    assert report.project_name == "fake-proj"
    assert any(f.category == "abandonment" for f in report.findings)
    assert report.confidence > 0
    md = report.to_markdown()
    assert "Autopsy" in md


def test_autopsy_no_metadata():
    p = _project(metadata=None)
    p.metadata = None
    report = autopsy_service.autopsy(p)
    assert any(f.severity == "critical" for f in report.findings)


def test_todo_analysis_counts(tmp_path: Path):
    (tmp_path / "main.py").write_text("# TODO: fix this\n# FIXME: and this\nx = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_x(): pass\n")
    analysis = todo_analysis_service.analyze(tmp_path, "demo")
    assert analysis.todo_count == 2
    assert analysis.test_files == 1
    assert analysis.source_files == 1
    assert "TODO" in analysis.to_markdown()


def test_completion_estimate_ranges():
    p = _project()
    todo = todo_analysis_service.TodoAnalysis(project_name="fake-proj")
    est = completion_service.estimate(p, todo)
    assert 5 <= est.percent_complete <= 95
    assert est.remaining_hours_low <= est.remaining_hours_high
    assert est.work_items  # dirty files + no CI etc.
    assert "Completion estimate" in est.to_markdown()


def test_revival_plan_ordered():
    p = _project()
    autopsy = autopsy_service.autopsy(p)
    plan = revival_plan_service.plan(p.name, autopsy, None, None)
    assert plan.steps
    assert [s.order for s in plan.steps] == list(range(1, len(plan.steps) + 1))
    assert plan.total_hours > 0
    assert "Revival plan" in plan.to_markdown()


def test_potential_scoring_verdict():
    p = _project()
    result = potential_scoring_service.score(p, None)
    assert 0 <= result.total <= 100
    assert result.verdict
    assert len(result.dimensions) == 5
    assert "Potential score" in result.to_markdown()
