"""ProjectOS: revival plans.

Turns autopsy + completion + TODO analysis into a concrete,
ordered revival checklist an AI agent (or human) can execute.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .autopsy_service import AutopsyReport
from .completion_service import CompletionEstimate
from .todo_analysis_service import TodoAnalysis


@dataclass
class RevivalStep:
    order: int
    title: str
    detail: str
    hours: float = 0.0


@dataclass
class RevivalPlan:
    project_name: str
    steps: list[RevivalStep] = field(default_factory=list)

    @property
    def total_hours(self) -> float:
        return sum(s.hours for s in self.steps)

    def to_markdown(self) -> str:
        lines = [
            f"# Revival plan: {self.project_name}",
            f"_Estimated {self.total_hours:.0f} hours across {len(self.steps)} steps_",
            "",
        ]
        for s in self.steps:
            lines.append(f"## {s.order}. {s.title} (~{s.hours:.0f}h)")
            lines.append(s.detail)
            lines.append("")
        return "\n".join(lines)


def plan(project_name: str,
         autopsy: AutopsyReport | None = None,
         completion: CompletionEstimate | None = None,
         todo: TodoAnalysis | None = None) -> RevivalPlan:
    """Build an ordered revival plan from the three analyses."""
    steps: list[RevivalStep] = []
    n = 0

    def add(title: str, detail: str, hours: float = 0.0):
        nonlocal n
        n += 1
        steps.append(RevivalStep(order=n, title=title, detail=detail, hours=hours))

    add("Re-entry brief",
        "Read the README, ADRs, and last 20 commits. Write a 10-line "
        "STATUS.md capturing: what it does, where it stopped, what hurts.",
        hours=1)

    if autopsy and any(f.category == "uncommitted-work" for f in autopsy.findings):
        add("Triage the working tree",
            "Stash or commit dirty files per-file. Delete what you can't "
            "explain in one sentence. Tag the pre-revival state.",
            hours=2)

    if autopsy and any(f.category == "branch-sprawl" for f in autopsy.findings):
        add("Prune branches",
            "Delete merged branches. For each unmerged branch decide: merge, "
            "cherry-pick the good parts, or delete. Keep at most 3.",
            hours=2)

    add("Get it running",
        "Fresh clone → install → run tests (or smoke test). Fix the setup "
        "path first; document every manual step you needed.",
        hours=4)

    if todo and todo.todo_count:
        add("Burn down the TODO backlog",
            f"{todo.todo_count} open markers. Fix-or-delete each: a TODO older "
            "than 6 months is a decision you already made — delete it.",
            hours=min(12, todo.todo_count * 0.5))

    if completion:
        for w in completion.work_items:
            if w.area in {"test coverage", "CI pipeline"}:
                add(f"Close gap: {w.area}", w.reason, hours=w.estimate_hours)

    add("Define done",
        "Write the 3 acceptance criteria that mean 'revived'. "
        "Timebox: if the core loop doesn't work in 2 sessions, archive it.",
        hours=1)

    if completion and completion.percent_complete < 70:
        add("Ship the smallest valuable slice",
            "Cut scope to one user-visible improvement. Revival dies on "
            "'rewrite everything' — ship a slice, then decide.",
            hours=8)

    add("Decide: revive or archive",
        "After the slice, score again. If potential is low, archive with a "
        "one-paragraph postmortem and move the reusable code to your snippets.",
        hours=1)

    return RevivalPlan(project_name=project_name, steps=steps)
