"""The Typer apps, the options commands share, and report output."""

import dataclasses
import json
from typing import Annotated

import typer

from modelkit import console
lazy from modelkit.audit import Report

app = typer.Typer(
    help="Build, audit and check Source 2 props for the plugins' workshop addons.\n\n"
    "Run from the repository root: uv run modelkit <command>",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
audit_app = typer.Typer(help="Find what makes models look flat or blurry.", no_args_is_help=True)
particles_app = typer.Typer(
    help="Check particle effects against the game's schema.", no_args_is_help=True
)
app.add_typer(audit_app, name="audit")
app.add_typer(particles_app, name="particles")

PluginArgument = Annotated[str, typer.Argument(help="Plugin folder name, e.g. stronghold")]
ModelArgument = Annotated[str, typer.Argument(help="Model folder, e.g. tank")]
ModelOption = Annotated[
    list[str] | None,
    typer.Option("--model", "-m", help="Model folder; repeat for more; default: all"),
]
ProblemsOption = Annotated[bool, typer.Option("--problems", help="Show only rows with problems")]
JsonOption = Annotated[bool, typer.Option("--json", help="Print JSON instead of a table")]


def show(
    title: str, reports: list[Report], problems_only: bool = False, as_json: bool = False
) -> None:
    """Prints the reports as JSON, or as a table with a problems column."""
    if as_json:
        print(json.dumps([dataclasses.asdict(r) for r in reports], indent=1))
        return
    shown = [r for r in reports if r.problems or not problems_only]
    columns = [*type(reports[0]).COLUMNS, "problems"] if reports else ["problems"]
    console.table(
        title,
        columns,
        [[*r.cells(), ", ".join(r.problems)] for r in shown],
        [bool(r.problems) for r in shown],
    )
    flagged = sum(bool(r.problems) for r in reports)
    console.info(f"{flagged} of {len(reports)} with problems")


def show_compile_hint(plugin: str, model: str) -> None:
    command = f"uv run voltmod content compile {plugin} models/{plugin}/{model}"
    console.done(f"now compile: {command} --install client")
