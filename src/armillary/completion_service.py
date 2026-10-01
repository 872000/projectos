"""ProjectOS: completion estimation.

Heuristic % complete + remaining-work breakdown derived from git
signals, TODO density, and test health. Estimates, not promises.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Project
from .todo_analysis_service import TodoAnalysis


@dataclass
class WorkItem:
    area: str
    estimate_hours: float
    reason: str


@dataclass
class CompletionEstimate:
    project_name: str
    percent_complete: int
    remaining_hours_low: float
    remaining_hours_high: float
    work_items: list[WorkItem] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            f"# Completion estimate: {self.project_name}",
            "",
            f"**Estimated complete:** {self.percent_complete}%",
            f"**Remaining work:** {self.remaining_hours_low:.0f}–"
            f"{self.remaining_hours_high:.0f} hours",
            "",
            "## Remaining work",
        ]
        for w in self.work_items:
            lines.append(f"- **{w.area}** (~{w.estimate_hours:.0f}h) — {w.reason}")
        if not self.work_items:
            lines.append("- No remaining work detected. Ship it.")
        return "\n".join(lines)


def estimate(project: Project, todo: TodoAnalysis | None = None) -> CompletionEstimate:
    """Estimate completion from metadata + TODO/test signals."""
    md = project.metadata
    score = 50.0  # prior: half-built side project
    items: list[WorkItem] = []

    if md:
        commits = md.commit_count or 0
        if commits > 200:
            score += 20
        elif commits > 50:
            score += 10
        elif commits < 10:
            score -= 15
            items.append(WorkItem("core implementation", 20,
                                  f"only {commits} commits — thin history"))

        if (md.dirty_count or 0) > 0:
            score -= 5
            items.append(WorkItem("land in-progress work", 4,
                                  f"{md.dirty_count} dirty files uncommitted"))

        velocity = md.commit_velocity or []
        if velocity and sum(velocity[-2:]) == 0:
            score -= 5

    if todo is not None:
        if todo.todo_count > 30:
            score -= 10
            items.append(WorkItem("clear TODO backlog", todo.todo_count * 0.5,
                                  f"{todo.todo_count} open markers"))
        elif todo.todo_count > 10:
            score -= 5
            items.append(WorkItem("clear TODO backlog", todo.todo_count * 0.5,
                                  f"{todo.todo_count} open markers"))

        if todo.test_ratio < 0.1 and todo.source_files > 10:
            score -= 10
            items.append(WorkItem("test coverage", 16,
                                  f"test ratio {todo.test_ratio:.0%} — below 10%"))
        elif todo.test_ratio < 0.25 and todo.source_files > 10:
            score -= 5
            items.append(WorkItem("test coverage", 8,
                                  f"test ratio {todo.test_ratio:.0%} — thin"))

        if not todo.has_ci and todo.source_files > 5:
            score -= 5
            items.append(WorkItem("CI pipeline", 6, "no CI configuration found"))

    if md and md.readme_excerpt:
        score += 5
    else:
        items.append(WorkItem("docs/readme", 3, "no README excerpt captured"))

    percent = int(max(5, min(95, round(score))))
    # Remaining hours scale inversely with completeness.
    missing = 100 - percent
    low = round(missing * 0.8, 1)
    high = round(missing * 1.6, 1)
    return CompletionEstimate(
        project_name=project.name,
        percent_complete=percent,
        remaining_hours_low=low,
        remaining_hours_high=high,
        work_items=items,
    )
