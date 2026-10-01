"""ProjectOS: project-potential scoring.

Scores 0–100 across five dimensions so `projectos next` can rank
"which forgotten project is actually worth reviving?"
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Project
from .todo_analysis_service import TodoAnalysis


@dataclass
class DimensionScore:
    name: str
    score: int  # 0-100
    reason: str


@dataclass
class PotentialScore:
    project_name: str
    total: int
    dimensions: list[DimensionScore] = field(default_factory=list)
    verdict: str = ""

    def to_markdown(self) -> str:
        lines = [
            f"# Potential score: {self.project_name}",
            f"**{self.total}/100** — {self.verdict}",
            "",
        ]
        for d in self.dimensions:
            lines.append(f"- **{d.name}**: {d.score}/100 — {d.reason}")
        return "\n".join(lines)


def _clamp(v: float) -> int:
    return int(max(0, min(100, round(v))))


def score(project: Project, todo: TodoAnalysis | None = None) -> PotentialScore:
    """Score project potential across momentum, completeness, hygiene, docs, uniqueness."""
    md = project.metadata
    dims: list[DimensionScore] = []

    # 1. Momentum (recent activity)
    momentum = 20.0
    if md:
        velocity = md.commit_velocity or []
        recent = sum(velocity[-2:]) if len(velocity) >= 2 else sum(velocity)
        if recent > 20:
            momentum = 90
        elif recent > 5:
            momentum = 65
        elif recent > 0:
            momentum = 40
        reason = f"{recent} commits in last 2 weeks"
    else:
        reason = "no metadata"
    dims.append(DimensionScore("Momentum", _clamp(momentum), reason))

    # 2. Completeness (commit depth + low TODO load)
    completeness = 50.0
    if md and (md.commit_count or 0) > 100:
        completeness += 20
    if todo:
        if todo.todo_count < 5:
            completeness += 15
        elif todo.todo_count > 30:
            completeness -= 20
    dims.append(DimensionScore("Completeness", _clamp(completeness),
                               f"{(md.commit_count or 0) if md else 0} commits, "
                               f"{todo.todo_count if todo else '?'} TODOs"))

    # 3. Hygiene (tests + CI)
    hygiene = 30.0
    if todo:
        hygiene = todo.test_ratio * 100
        if todo.has_ci:
            hygiene = min(100, hygiene + 20)
    dims.append(DimensionScore("Hygiene", _clamp(hygiene),
                               "tests + CI presence"))

    # 4. Documentation
    docs = 20.0
    if md and md.readme_excerpt:
        docs = 70.0
        if len(md.readme_excerpt) > 500:
            docs = 85.0
    if md and md.adr_paths:
        docs = min(100, docs + 10)
    dims.append(DimensionScore("Documentation", _clamp(docs), "README/ADR presence"))

    # 5. Uniqueness proxy: idea projects and large codebases score higher
    # (real uniqueness needs cross-repo comparison; this is a stub signal).
    uniqueness = 50.0
    if md and (md.file_count or 0) > 200:
        uniqueness = 70.0
    dims.append(DimensionScore("Depth", _clamp(uniqueness),
                               f"{(md.file_count or 0) if md else 0} files"))

    total = _clamp(sum(d.score for d in dims) / len(dims))
    if total >= 75:
        verdict = "Strong revival candidate"
    elif total >= 55:
        verdict = "Worth a timeboxed revival sprint"
    elif total >= 35:
        verdict = "Only if it solves a current problem"
    else:
        verdict = "Archive — keep the reusable parts"
    return PotentialScore(project_name=project.name, total=total,
                          dimensions=dims, verdict=verdict)
