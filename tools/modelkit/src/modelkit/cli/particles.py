"""`modelkit particles`: .vpcf fields against the game's schema, and its particle textures."""

from pathlib import Path
from typing import Annotated

import typer

from modelkit import console
from modelkit.cli.app import particles_app
lazy from modelkit import particles


@particles_app.command("check")
def particles_check(files: Annotated[list[Path], typer.Argument(help=".vpcf files")]) -> None:
    """Report fields the game's schema does not declare; the compiler drops them silently."""
    found = particles.check(files)
    for path, where, cls, field in found:
        console.info(f"{path}: {where}: {cls} has no field {field}")
    console.info(f"{len(found)} unknown field(s) in {len(files)} file(s)")
    if found:
        raise typer.Exit(1)


@particles_app.command("fields")
def particles_fields(
    cls: Annotated[str, typer.Argument(help="Particle class, e.g. C_OP_Decay")],
) -> None:
    """List a particle class's fields with their real names and types."""
    rows = particles.Schema.load().list_fields(cls)
    if not rows:
        raise ValueError(f"no class {cls} in the schema dump")
    for owner, name, kind in rows:
        console.info(f"{owner:34} {name:40} {kind}")


@particles_app.command("textures")
def particles_textures(word: Annotated[str, typer.Argument(help="Part of the path")] = "") -> None:
    """List the game's particle textures whose path holds WORD."""
    console.info("\n".join(particles.find_textures(word)))
