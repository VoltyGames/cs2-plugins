"""`modelkit audit`: what makes models look flat or blurry."""

from typing import Annotated

import typer

from modelkit import console
from modelkit.audit.triangles import Operation
from modelkit.cli.app import (
    JsonOption,
    ModelOption,
    PluginArgument,
    ProblemsOption,
    audit_app,
    show,
)
lazy from modelkit import game
lazy from modelkit.audit import compiled, textures, triangles, uv
lazy from modelkit.models import ModelFolder


@audit_app.command("textures")
def audit_textures(
    plugin: PluginArgument,
    model: ModelOption = None,
    problems: ProblemsOption = False,
    as_json: JsonOption = False,
) -> None:
    """Colour contrast, roughness, normal strength, AO and metalness per material."""
    reports = textures.audit(ModelFolder.find_all(plugin, model))
    show("Textures (contrast and normal on 0-255)", reports, problems, as_json)


@audit_app.command("uv")
def audit_uv(
    plugin: PluginArgument,
    model: ModelOption = None,
    target: Annotated[float | None, typer.Option(help="Pixels per game unit to aim for")] = None,
    problems: ProblemsOption = False,
    as_json: JsonOption = False,
) -> None:
    """Texel density at the size the game loads, atlas fill, overlap and faces without UV area."""
    target = target or uv.TARGET_DENSITY
    reports = uv.audit(ModelFolder.find_all(plugin, model), target)
    show(f"UVs (pixels per game unit; target {target:g})", reports, problems, as_json)


@audit_app.command("compiled")
def audit_compiled(
    plugin: PluginArgument,
    model: ModelOption = None,
    problems: ProblemsOption = False,
    as_json: JsonOption = False,
) -> None:
    """Each source texture against the .vtex_c the Workshop Tools wrote."""
    reports = compiled.audit(ModelFolder.find_all(plugin, model))
    if not as_json:
        console.info(f"texture cap: {game.read_texture_cap() or 'none'} (PublicToolsDefaultMaxRes)")
    show("Compiled textures", reports, problems, as_json)


@audit_app.command("triangles")
def audit_triangles(
    plugin: PluginArgument,
    model: ModelOption = None,
    only: Annotated[
        list[Operation] | None, typer.Option("--only", help="Repeat for more; default: all")
    ] = None,
    problems: ProblemsOption = False,
    as_json: JsonOption = False,
) -> None:
    """Triangles each part can lose without looking different: degenerate, coplanar, hidden."""
    reports = triangles.audit(ModelFolder.find_all(plugin, model), only or list(Operation))
    show("Triangles that can go", reports, problems, as_json)
