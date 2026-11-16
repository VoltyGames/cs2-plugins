"""Build, audit and check Source 2 props for the plugins' workshop addons.

Run from the repository root: uv run modelkit <command>
"""

import dataclasses
import json
import tempfile
from pathlib import Path
from typing import Annotated, Any

import typer

from modelkit import console

# Lazy, so --help skips numpy, Pillow and the audits.
lazy from modelkit import baking, checks, game, headless, icons, particles
lazy from modelkit.audit import compiled, find_models, textures, triangles, uv

app = typer.Typer(help=__doc__, no_args_is_help=True, pretty_exceptions_enable=False)
audit_app = typer.Typer(help="Find what makes models look flat or blurry.", no_args_is_help=True)
particles_app = typer.Typer(
    help="Check particle effects against the game's schema.", no_args_is_help=True
)
app.add_typer(audit_app, name="audit")
app.add_typer(particles_app, name="particles")

PluginArgument = Annotated[str, typer.Argument(help="Plugin folder name, e.g. stronghold")]
ModelOption = Annotated[
    list[str] | None,
    typer.Option("--model", "-m", help="Model folder; repeat for more; default: all"),
]
ProblemsOption = Annotated[bool, typer.Option("--problems", help="Show only rows with problems")]
JsonOption = Annotated[bool, typer.Option("--json", help="Print JSON instead of a table")]
OperationOption = Annotated[
    list[str] | None,
    typer.Option(
        "--only", help="degenerate, coplanar or hidden; repeat for more; default: all three"
    ),
]


def chosen_operations(only: list[str] | None) -> tuple[str, ...]:
    unknown = set(only or ()) - set(triangles.OPERATIONS)
    if unknown:
        raise fail(f"unknown operation {', '.join(sorted(unknown))}")
    return tuple(only) if only else triangles.OPERATIONS


def triangle_cells(report: Any) -> list[str]:
    removable = report.removable
    return [
        report.model,
        report.part,
        str(report.triangles),
        *(str(removable.get(op, 0)) for op in triangles.OPERATIONS),
        f"{report.saved / max(report.triangles, 1):.1%}",
    ]


def fail(message: str) -> typer.Exit:
    console.error(message)
    return typer.Exit(1)


def show(
    title: str,
    reports: list[Any],
    columns: list[str],
    row: Any,
    problems_only: bool,
    as_json: bool,
) -> None:
    """Prints `reports` as JSON or as a table of `row(report)` cells plus a problems column."""
    if as_json:
        print(json.dumps([dataclasses.asdict(r) for r in reports], indent=1))
        return
    shown = [r for r in reports if r.problems or not problems_only]
    console.table(
        title,
        [*columns, "problems"],
        [[*row(r), ", ".join(r.problems)] for r in shown],
        [bool(r.problems) for r in shown],
    )
    flagged = sum(bool(r.problems) for r in reports)
    console.info(f"{flagged} of {len(reports)} with problems")


def size(value: tuple[int, int] | None) -> str:
    return f"{value[0]}x{value[1]}" if value else "-"


def percent(value: float | None) -> str:
    return "-" if value is None else f"{value:.0%}"


def models(plugin: str, only: list[str] | None) -> list[Path]:
    try:
        return find_models(plugin, only)
    except FileNotFoundError as missing:
        raise fail(str(missing)) from None


@app.command()
def check(
    plugin: Annotated[str | None, typer.Argument(help="Also check this plugin's addon")] = None,
) -> None:
    """Check Blender, Source Tools, Codex, Git LFS and the CS2 Workshop Tools."""
    if not checks.run(plugin):
        raise typer.Exit(1)


@app.command()
def render(
    plugin: PluginArgument,
    model: Annotated[str, typer.Argument(help="Model folder, e.g. tank")],
    out: Annotated[Path, typer.Option("--out", "-o", help="PNG to write")] = Path("render.png"),
    skip: Annotated[list[str] | None, typer.Option(help="Part scene to leave out; repeat")] = None,
    at: Annotated[
        list[str] | None,
        typer.Option(help="Place a part, in Blender units: scene=x,y,z; repeat"),
    ] = None,
) -> None:
    """Render a whole model at eye level, every part posed at its idle, for concept work.

    Parts the plugin stacks in code need --at, at the code offset divided by the .vmdl scale.
    """
    blend = game.models_dir(plugin) / model / f"{model}.blend"
    if not blend.is_file():
        raise fail(f"no {blend}")
    placed = {}
    for item in at or []:
        scene, _, offset = item.partition("=")
        placed[scene] = [float(v) for v in offset.split(",")]
    try:
        result = headless.run_job(
            "render", blend, path=str(out.resolve()), skip=skip or [], at=placed
        )
    except headless.BlenderError as failed:
        raise fail(str(failed)) from None
    console.done(f"wrote {result['path']} ({', '.join(result['parts'])})")


@app.command()
def icon(
    plugin: PluginArgument,
    cards: Annotated[
        list[str] | None,
        typer.Argument(help="Cards to render; default: every card in bake/icons.json"),
    ] = None,
) -> None:
    """Render store cards from the models into panorama/images/<plugin>/."""
    try:
        listed = icons.read_list(plugin)
    except FileNotFoundError as missing:
        raise fail(str(missing)) from None
    unknown = set(cards or ()) - set(listed["icons"])
    if unknown:
        raise fail(f"no card {', '.join(sorted(unknown))} in bake/icons.json")
    size = tuple(listed.get("size", (384, 256)))
    for card in cards or listed["icons"]:
        try:
            out = icons.render(plugin, card, listed["icons"][card], (size[0], size[1]))
        except (FileNotFoundError, headless.BlenderError) as failed:
            raise fail(str(failed)) from None
        console.done(f"wrote {out}")


@app.command()
def bake(
    plugin: PluginArgument,
    model: Annotated[
        str, typer.Argument(help="Model folder; its recipe is plugins/<plugin>/bake/<model>.json")
    ],
    write: Annotated[
        bool, typer.Option("--write", help="Ship the last preview into the model folder")
    ] = False,
) -> None:
    """Retexture a model from its bake recipe: CC0 materials baked with wear into one texture
    set per part, with its maker's marks. Previews first; --write ships the preview."""
    try:
        if write:
            for path in baking.write(plugin, model):
                console.info(f"wrote {path}")
            command = f"uv run voltmod content compile {plugin} models/{plugin}/{model}"
            console.done(f"now compile: {command} --install client")
            return
        result = baking.preview(plugin, model)
    except (FileNotFoundError, ValueError, headless.BlenderError) as failed:
        raise fail(str(failed)) from None
    for part, density in result.density.items():
        console.info(f"{part}: {density:.1f} pixels per unit in game")
    console.info(f"baked on {result.device}")
    for path in result.renders:
        console.info(f"preview {path}")
    console.done(f"review the renders, then: uv run modelkit bake {plugin} {model} --write")


@audit_app.command("textures")
def audit_textures(
    plugin: PluginArgument,
    model: ModelOption = None,
    problems: ProblemsOption = False,
    as_json: JsonOption = False,
) -> None:
    """Colour contrast, roughness, normal strength, AO and metalness per material."""
    reports = textures.audit(plugin, models(plugin, model))
    show(
        "Textures (contrast and normal on 0-255)",
        reports,
        ["model", "material", "size", "contrast", "roughness", "normal", "AO", "metal"],
        lambda r: [
            r.model,
            r.material,
            size(r.size),
            f"{r.contrast:.1f}",
            r.roughness,
            "-" if r.normal is None else f"{r.normal:.1f}",
            r.ambient_occlusion,
            r.metalness,
        ],
        problems,
        as_json,
    )


@audit_app.command("uv")
def audit_uv(
    plugin: PluginArgument,
    model: ModelOption = None,
    target: Annotated[float, typer.Option(help="Pixels per game unit to aim for")] = 12.0,
    problems: ProblemsOption = False,
    as_json: JsonOption = False,
) -> None:
    """Texel density at the size the game loads, atlas fill, overlap and faces without UV area."""
    try:
        reports = uv.audit(plugin, models(plugin, model), target)
    except headless.BlenderError as failed:
        raise fail(str(failed)) from None
    show(
        f"UVs (pixels per game unit; target {target:g})",
        reports,
        [
            "model",
            "part",
            "material",
            "shipped",
            "tris",
            "density",
            "p10-p90",
            "fill",
            "overlap",
            "span",
        ],
        lambda r: [
            r.model,
            r.part,
            r.material,
            size(r.shipped),
            str(r.triangles),
            f"{r.density:.1f}",
            f"{r.p10:.1f}-{r.p90:.1f}",
            percent(r.coverage),
            "-" if r.overlap is None else f"{r.overlap:.2f}",
            "-" if r.coverage is not None else f"{r.span:.1f}",
        ],
        problems,
        as_json,
    )


@audit_app.command("compiled")
def audit_compiled(
    plugin: PluginArgument,
    model: ModelOption = None,
    problems: ProblemsOption = False,
    as_json: JsonOption = False,
) -> None:
    """Each source texture against the .vtex_c the Workshop Tools wrote."""
    reports = compiled.audit(plugin, models(plugin, model))
    if not as_json:
        console.info(f"texture cap: {game.read_texture_cap() or 'none'} (PublicToolsDefaultMaxRes)")
    show(
        "Compiled textures",
        reports,
        ["model", "texture", "source", "shipped"],
        lambda r: [r.model, r.texture, size(r.source), size(r.shipped)],
        problems,
        as_json,
    )


@audit_app.command("triangles")
def audit_triangles(
    plugin: PluginArgument,
    model: ModelOption = None,
    only: OperationOption = None,
    problems: ProblemsOption = False,
    as_json: JsonOption = False,
) -> None:
    """Triangles each part can lose without looking different: degenerate, coplanar, hidden."""
    try:
        reports = triangles.audit(models(plugin, model), chosen_operations(only))
    except headless.BlenderError as failed:
        raise fail(str(failed)) from None
    show(
        "Triangles that can go",
        reports,
        ["model", "part", "tris", *triangles.OPERATIONS, "saving"],
        triangle_cells,
        problems,
        as_json,
    )


@app.command()
def optimize(
    plugin: PluginArgument,
    model: Annotated[str, typer.Argument(help="Model folder, e.g. tank")],
    only: OperationOption = None,
    views: Annotated[
        Path | None, typer.Option(help="Folder for the before/after renders; default: a temp one")
    ] = None,
) -> None:
    """Trim triangles in a model's .blend, keeping each part's trim only if renders from all
    round still match. Re-export the DMX and compile afterwards; the .blend is in Git."""
    [folder] = models(plugin, [model])
    views = views or Path(tempfile.gettempdir()) / "modelkit_views" / model
    try:
        reports = triangles.optimize(folder, views, chosen_operations(only))
    except headless.BlenderError as failed:
        raise fail(str(failed)) from None
    show(
        f"Trimmed {model} (renders in {views})",
        reports,
        ["model", "part", "tris", *triangles.OPERATIONS, "saving", "applied", "changed"],
        lambda r: [
            *triangle_cells(r),
            "yes" if r.applied else "no",
            "-" if r.changed is None else f"{r.changed:.3%}",
        ],
        False,
        False,
    )


@particles_app.command("check")
def particles_check(files: Annotated[list[Path], typer.Argument(help=".vpcf files")]) -> None:
    """Report fields the game's schema does not declare; the compiler drops them silently."""
    try:
        found = particles.check(files)
    except FileNotFoundError as missing:
        raise fail(str(missing)) from None
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
    try:
        rows = particles.list_fields(cls)
    except FileNotFoundError as missing:
        raise fail(str(missing)) from None
    if not rows:
        raise fail(f"no class {cls} in the schema dump")
    for owner, name, kind in rows:
        console.info(f"{owner:34} {name:40} {kind}")


@particles_app.command("textures")
def particles_textures(word: Annotated[str, typer.Argument(help="Part of the path")] = "") -> None:
    """List the game's particle textures whose path holds WORD."""
    console.info("\n".join(particles.find_textures(word)))
