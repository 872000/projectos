"""ProjectOS CLI commands: autopsy, estimate, revive-plan, potential.

Extracted as a submodule; importing registers the commands on the
main typer app (see cli.py bottom).
"""

from __future__ import annotations

from pathlib import Path

import typer

from armillary import autopsy_service, completion_service, potential_scoring_service
from armillary import revival_plan_service, todo_analysis_service
from armillary.cache import Cache
from armillary.cli import app
from armillary.cli_helpers import _resolve_project_or_report


def _load_project(name: str):
    with Cache() as cache:
        project = _resolve_project_or_report(cache, name)
    if project is None:
        raise typer.Exit(1)
    return project


@app.command("autopsy")
def autopsy_cmd(
    name: str = typer.Argument(..., help="Project name (from cache)."),
    markdown: bool = typer.Option(False, "--md", help="Print Markdown report."),
) -> None:
    """Explain why a project stalled: autopsy report."""
    project = _load_project(name)
    report = autopsy_service.autopsy(project)
    if markdown:
        typer.echo(report.to_markdown())
    else:
        typer.secho(f"Autopsy: {report.project_name}", bold=True)
        typer.echo(f"Status: {report.status}")
        typer.echo(f"Likely cause: {report.cause_of_death} ({report.confidence:.0%})")
        for f in report.findings:
            typer.echo(f"  [{f.severity}] {f.category}: {f.summary}")


@app.command("estimate")
def estimate_cmd(
    name: str = typer.Argument(..., help="Project name (from cache)."),
    markdown: bool = typer.Option(False, "--md", help="Print Markdown report."),
) -> None:
    """Estimate % complete and remaining work for a project."""
    project = _load_project(name)
    todo = todo_analysis_service.analyze(Path(project.path), project.name)
    est = completion_service.estimate(project, todo)
    if markdown:
        typer.echo(est.to_markdown())
    else:
        typer.secho(f"Completion: {est.project_name}", bold=True)
        typer.echo(f"{est.percent_complete}% complete — "
                   f"{est.remaining_hours_low:.0f}–{est.remaining_hours_high:.0f}h remaining")
        for w in est.work_items:
            typer.echo(f"  - {w.area} (~{w.estimate_hours:.0f}h): {w.reason}")


@app.command("revive-plan")
def revive_plan_cmd(
    name: str = typer.Argument(..., help="Project name (from cache)."),
    markdown: bool = typer.Option(False, "--md", help="Print Markdown report."),
) -> None:
    """Generate a concrete, ordered revival plan for a stalled project."""
    project = _load_project(name)
    todo = todo_analysis_service.analyze(Path(project.path), project.name)
    autopsy = autopsy_service.autopsy(project)
    completion = completion_service.estimate(project, todo)
    plan = revival_plan_service.plan(project.name, autopsy, completion, todo)
    if markdown:
        typer.echo(plan.to_markdown())
    else:
        typer.secho(f"Revival plan: {plan.project_name} "
                     f"({plan.total_hours:.0f}h, {len(plan.steps)} steps)", bold=True)
        for s in plan.steps:
            typer.echo(f"  {s.order}. {s.title} (~{s.hours:.0f}h)")


@app.command("potential")
def potential_cmd(
    name: str = typer.Argument(..., help="Project name (from cache)."),
    markdown: bool = typer.Option(False, "--md", help="Print Markdown report."),
) -> None:
    """Score a project's revival potential (0-100)."""
    project = _load_project(name)
    todo = todo_analysis_service.analyze(Path(project.path), project.name)
    result = potential_scoring_service.score(project, todo)
    if markdown:
        typer.echo(result.to_markdown())
    else:
        typer.secho(f"Potential: {result.project_name} — "
                     f"{result.total}/100 ({result.verdict})", bold=True)
        for d in result.dimensions:
            typer.echo(f"  {d.name}: {d.score}/100 — {d.reason}")


@app.command("projectos-report")
def projectos_report_cmd(
    name: str = typer.Argument(..., help="Project name (from cache)."),
    out: Path | None = typer.Option(None, "--out", "-o",
                                    help="Write Markdown bundle to file."),
) -> None:
    """Full ProjectOS bundle: autopsy + TODO/test + estimate + plan + score."""
    project = _load_project(name)
    todo = todo_analysis_service.analyze(Path(project.path), project.name)
    autopsy = autopsy_service.autopsy(project)
    completion = completion_service.estimate(project, todo)
    plan = revival_plan_service.plan(project.name, autopsy, completion, todo)
    result = potential_scoring_service.score(project, todo)
    bundle = "\n\n---\n\n".join([
        autopsy.to_markdown(),
        todo.to_markdown(),
        completion.to_markdown(),
        plan.to_markdown(),
        result.to_markdown(),
    ])
    if out:
        out.write_text(bundle, encoding="utf-8")
        typer.secho(f"Wrote {out}", fg=typer.colors.GREEN)
    else:
        typer.echo(bundle)
