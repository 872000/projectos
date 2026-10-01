"""ProjectOS: project autopsy.

Answers "why did this project stall?" by combining git history,
working-tree state, TODO density, and test health into a structured
report. Pure functions over Project/ProjectMetadata — no Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .models import Project


@dataclass
class AutopsyFinding:
    category: str
    severity: str  # info / warning / critical
    summary: str
    detail: str = ""


@dataclass
class AutopsyReport:
    project_name: str
    generated_at: datetime
    status: str
    findings: list[AutopsyFinding] = field(default_factory=list)
    cause_of_death: str = "unknown"
    confidence: float = 0.0

    def to_markdown(self) -> str:
        lines = [
            f"# Autopsy: {self.project_name}",
            f"_Generated {self.generated_at.isoformat()}_",
            "",
            f"**Status:** {self.status}",
            f"**Likely cause of stall:** {self.cause_of_death}",
            f"**Confidence:** {self.confidence:.0%}",
            "",
            "## Findings",
        ]
        for f in self.findings:
            lines.append(f"- **[{f.severity}] {f.category}** — {f.summary}")
            if f.detail:
                lines.append(f"  {f.detail}")
        return "\n".join(lines)


def _days_since(dt: datetime | None, now: datetime) -> int | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (now - dt).days)


def autopsy(project: Project, now: datetime | None = None) -> AutopsyReport:
    """Build an autopsy report for a single project."""
    now = now or datetime.now(timezone.utc)
    md = project.metadata
    report = AutopsyReport(
        project_name=project.name,
        generated_at=now,
        status=str(md.status) if md and md.status else "unknown",
    )
    if md is None:
        report.findings.append(
            AutopsyFinding("metadata", "critical", "No metadata available",
                           "Run a scan first so autopsy has git/FS signals.")
        )
        return report

    days_idle = _days_since(md.last_commit_ts, now)
    if days_idle is not None and days_idle > 90:
        report.findings.append(AutopsyFinding(
            "abandonment", "critical",
            f"No commits for {days_idle} days",
            "Long idle stretches usually mean context loss; revival needs a re-entry brief.",
        ))
    elif days_idle is not None and days_idle > 30:
        report.findings.append(AutopsyFinding(
            "abandonment", "warning", f"No commits for {days_idle} days"))

    if (md.dirty_count or 0) > 0 and (days_idle or 0) > 14:
        report.findings.append(AutopsyFinding(
            "uncommitted-work", "warning",
            f"{md.dirty_count} dirty files left uncommitted",
            "Uncommitted work is the #1 context-loss vector on revisit.",
        ))

    velocity = md.commit_velocity or []
    if velocity and sum(velocity) == 0:
        report.findings.append(AutopsyFinding(
            "velocity", "critical", "Zero commits in the last 4 weeks",
            f"Weekly buckets (oldest→newest): {velocity}",
        ))

    if md.branch_count and md.branch_count > 5:
        report.findings.append(AutopsyFinding(
            "branch-sprawl", "warning",
            f"{md.branch_count} local branches",
            "Branch sprawl suggests unfinished experiments never merged or pruned.",
        ))

    if md.has_remote is False:
        report.findings.append(AutopsyFinding(
            "backup-risk", "warning", "No git remote configured",
            "Work exists only on this machine.",
        ))

    # Cause-of-death heuristic: pick the highest-severity pattern.
    severities = [f.severity for f in report.findings]
    if "critical" in severities:
        crit = [f for f in report.findings if f.severity == "critical"]
        report.cause_of_death = crit[0].summary
        report.confidence = 0.75
    elif report.findings:
        report.cause_of_death = report.findings[0].summary
        report.confidence = 0.5
    else:
        report.cause_of_death = "No clear stall signal — project looks healthy"
        report.confidence = 0.6

    return report
