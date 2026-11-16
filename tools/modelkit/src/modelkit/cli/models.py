"""Commands that change or render one model: check, render, bake, mark and optimize."""

import tempfile
from pathlib import Path
from typing import Annotated

import typer

from modelkit import console
from modelkit.audit.triangles import Operation
from modelkit.cli.app import ModelArgument, PluginArgument, app, show, show_compile_hint
lazy from modelkit import checks, headless
lazy from modelkit.audit import triangles
lazy from modelkit.baking import ModelBake
lazy from modelkit.models import ModelFolder


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
    model: ModelArgument,
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
    folder = ModelFolder.find(plugin, model)
    if not folder.blend.is_file():
        raise FileNotFoundError(f"no {folder.blend}")
    placed = {}
    for item in at or []:
        scene, _, offset = item.partition("=")
        placed[scene] = [float(v) for v in offset.split(",")]
    result = headless.run_job(
        "render", folder.blend, path=str(out.resolve()), skip=skip or [], at=placed
    )
    console.done(f"wrote {result['path']} ({', '.join(result['parts'])})")


@app.command()
def bake(
    plugin: PluginArgument,
    model: Annotated[
        str, typer.Argument(help="Model folder; its recipe is plugins/<plugin>/bake/<model>.json")
    ],
    write: Annotated[
        bool, typer.Option("--write", help="Ship the last preview into the model folder")
    ] = False,
    source: Annotated[
        str | None,
        typer.Option(help="Bake from the model's .blend at this revision of the plugin's repo"),
    ] = None,
) -> None:
    """Retexture a model from its bake recipe and preview it; --write ships the preview."""
    model_bake = ModelBake(plugin, model)
    if write:
        for path in model_bake.write():
            console.info(f"wrote {path}")
        show_compile_hint(plugin, model)
        return
    result = model_bake.preview(source)
    for part, density in result.pixels_per_unit.items():
        console.info(f"{part}: {density:.1f} pixels per unit in game")
    console.info(f"baked on {result.device}")
    for path in result.renders:
        console.info(f"preview {path}")
    console.done(f"review the renders, then: uv run modelkit bake {plugin} {model} --write")


@app.command()
def mark(plugin: PluginArgument, model: ModelArgument) -> None:
    """Stamp the recipe's maker's marks onto a model's own textures, without a bake. Run it
    once: a second run presses the marks in again."""
    for path in ModelBake(plugin, model).stamp_marks():
        console.info(f"stamped {path}")
    show_compile_hint(plugin, model)


@app.command()
def optimize(
    plugin: PluginArgument,
    model: ModelArgument,
    only: Annotated[
        list[Operation] | None, typer.Option("--only", help="Repeat for more; default: all")
    ] = None,
    views: Annotated[
        Path | None, typer.Option(help="Folder for the before/after renders; default: a temp one")
    ] = None,
) -> None:
    """Trim triangles in a model's .blend, keeping each part's trim only if renders from all
    round still match. Re-export the DMX and compile afterwards; the .blend is in Git."""
    views = views or Path(tempfile.gettempdir()) / "modelkit_views" / model
    reports = triangles.optimize(ModelFolder.find(plugin, model), views, only or list(Operation))
    show(f"Trimmed {model} (renders in {views})", reports)
