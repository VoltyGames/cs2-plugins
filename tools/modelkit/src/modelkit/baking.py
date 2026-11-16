"""Retexturing a model from its bake recipe, plugins/<plugin>/bake/<model>.json. Recipes stay
out of content/, whose unreferenced files `voltmod content compile --prune` deletes.

`preview` bakes into build/bake/<plugin>/<model>/ and renders the result; nothing in the model
folder changes. `write` then ships that bake: the PNGs and .vmat into the model folder, the
.blend saved and the DMX re-exported.

A recipe:

    {
      "density": 12,
      "parts": {"<object>": {"material": "<new>.vmat", "surfaces": {"<old>.vmat": "<finish>"}}},
      "finishes": {"<finish>": {"base": "polyhaven:<id>", "under": "polyhaven:<id>", "tile": 96,
                                "tint": [r, g, b], "metallic": 0.0, "wear": 0.5, "grime": 0.5,
                                "dust": 0.4}},
      "marks": [{"text": "...", "part": "<object>", "at": [x, y, z], "height": 1.2,
                 "style": "stamp"}],
      "hidden_mark": "...",
      "at": {"<scene>": [x, y, z]}
    }

`"blend"` (default 0.25) softens the seams of a finish's box projection; raise it for small,
rounded parts, where a face looking half up smears the top-down projection down its side.

`"artwork": true` in a finish keeps the surface's own colour texture, such as hazard stripes,
under the library material's roughness, normal and wear.

Each part bakes at the smallest of 512, 1024 and 2048 that gives it `density` pixels per game
unit (DENSITY by default); a part or the recipe may set `density`, or a fixed `size`, instead.

`at` in a mark is a point in Blender units on the face to stamp; its `surface`, one of the part's
old .vmat names, keeps it on that material's faces where another surface lies close by, and
its `right`, a direction, turns the text, which otherwise runs level across the face.

The top-level `at` places parts the plugin stacks in code, for the preview render.

A model that keeps its own textures has a recipe of only `marks`, which `stamp_marks` presses
into its colour texture without a bake.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from modelkit import finish, game, headless, library
from modelkit.source2 import modeldoc

# Pixels per game unit a part's atlas aims for when the recipe sets no size: sharp at the
# distances structures are seen from. Props seen up close set a higher `density`.
DENSITY = 12.0

# The pixels kept free along the atlas's top edge for the hidden mark: the bake's 12-pixel
# margin spills into it, and the mark needs 16 clear rows.
HIDDEN_BAND = 40


@dataclass(frozen=True)
class Preview:
    renders: list[str]
    density: dict[str, float]
    """Each part's pixels per game unit at its atlas size."""
    device: str


def scratch_dir(plugin: str, model: str) -> Path:
    return game.REPO / "build" / "bake" / plugin / model


def read_recipe(plugin: str, model: str) -> dict[str, Any]:
    path = game.plugin_dir(plugin) / "bake" / f"{model}.json"
    if not path.is_file():
        raise FileNotFoundError(f"no bake recipe {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_finishes(finishes: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The finishes with each material name replaced by its downloaded maps."""
    resolved = {}
    for name, settings in finishes.items():
        maps = {
            key: library.find_maps(settings[key]) for key in ("base", "under") if key in settings
        }
        resolved[name] = settings | maps
    return resolved


def stem_of(material: str) -> str:
    return PurePosixPath(material).stem


def extract_source(plugin: str, model: str, revision: str, into: Path) -> Path:
    """The model folder as it was at `revision` of the plugin's repo, Git LFS files resolved,
    copied into `into`; returns its .blend. For re-baking a model whose .blend already holds
    the baked material instead of the surfaces its recipe names."""
    repo = game.plugin_dir(plugin)
    folder = PurePosixPath("content", "models", plugin, model)
    listed = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", revision, str(folder)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    into.mkdir(parents=True)
    for name in listed:
        stored = subprocess.run(
            ["git", "-C", str(repo), "show", f"{revision}:{name}"], check=True, capture_output=True
        ).stdout
        content = subprocess.run(
            ["git", "-C", str(repo), "lfs", "smudge"],
            input=stored,
            check=True,
            capture_output=True,
        ).stdout
        (into / PurePosixPath(name).name).write_bytes(content)
    blend = into / f"{model}.blend"
    if not blend.is_file():
        raise FileNotFoundError(f"no {model}.blend in {folder} at {revision}")
    return blend


def preview(plugin: str, model: str, source: str | None = None) -> Preview:
    """Bakes the recipe; `source`, a revision of the plugin's repo, bakes from the model's
    .blend as it was then."""
    folder = game.models_dir(plugin) / model
    recipe = read_recipe(plugin, model)
    scratch = scratch_dir(plugin, model)
    if scratch.exists():
        shutil.rmtree(scratch)
    (scratch / "raw").mkdir(parents=True)
    blend = folder / f"{model}.blend"
    if source:
        blend = extract_source(plugin, model, source, scratch / "source")
    baked = headless.run_job(
        "bake",
        blend,
        parts=recipe["parts"],
        finishes=resolve_finishes(recipe["finishes"]),
        marks=recipe.get("marks", []),
        size=recipe.get("size"),
        density=recipe.get("density", DENSITY),
        largest=game.read_texture_cap() or 2048,
        folder=str(scratch / "raw"),
        save_to=str(scratch / f"{model}.blend"),
        reserve=HIDDEN_BAND if recipe.get("hidden_mark") else 0,
    )
    textures, density, device = {}, {}, "CPU"
    for object_name, result in baked.items():
        material = recipe["parts"][object_name]["material"]
        written = finish.finish(
            result["files"],
            scratch / "final",
            stem_of(material),
            result["frames"],
            recipe.get("hidden_mark"),
        )
        textures[material] = {channel: str(path) for channel, path in written.items()}
        density[object_name] = result["density"] * result["size"]
        device = result["device"]
    shown = headless.run_job(
        "adopt",
        scratch / f"{model}.blend",
        textures=textures,
        render_dir=str(scratch),
        at=recipe.get("at"),
    )
    return Preview(shown["renders"], density, device)


def keep_shared(folder: Path, addon_folder: str, target: Path, kept_materials: set[str]) -> None:
    """Before `target` is overwritten, moves it to a _flat_ name for the kept materials still
    using it, such as a flat roughness map shared by glass and glow."""
    reference = f"{addon_folder}{target.name}"
    users = [
        vmat
        for vmat in folder.glob("*.vmat")
        if vmat.name in kept_materials and reference in vmat.read_text()
    ]
    if not users or not target.exists():
        return
    stem, _, suffix = target.stem.rpartition("_")
    kept = target.with_name(f"{stem}_flat_{suffix}.png")
    if not kept.exists():
        shutil.copyfile(target, kept)
    for vmat in users:
        text = vmat.read_text().replace(reference, f"{addon_folder}{kept.name}")
        vmat.write_text(text, newline="\n")


def texture_names(vmat: Path) -> set[str]:
    return {Path(value).name for value in modeldoc.read_vmat(vmat).values()}


def remove_replaced(
    folder: Path, addon_folder: str, replaced: set[str], dropped: set[str] | None = None
) -> list[str]:
    """Deletes the replaced .vmat files, and their textures and `dropped` ones that no remaining
    .vmat names."""
    names = set(dropped or ())
    deleted = sorted(name for name in replaced if (folder / name).exists())
    for name in deleted:
        names |= texture_names(folder / name)
        (folder / name).unlink()
    still_used = {name for vmat in folder.glob("*.vmat") for name in texture_names(vmat)}
    removed = [name for name in sorted(names - still_used) if (folder / name).exists()]
    for name in removed:
        (folder / name).unlink()
    return [str(folder / name) for name in deleted + removed]


def write(plugin: str, model: str) -> list[str]:
    """Ships the last preview; returns the files written."""
    folder = game.models_dir(plugin) / model
    recipe = read_recipe(plugin, model)
    scratch = scratch_dir(plugin, model)
    if not (scratch / f"{model}.blend").is_file():
        raise FileNotFoundError(f"no preview in {scratch}; run modelkit bake without --write first")
    addon_folder = f"models/{plugin}/{model}/"
    replaced = {name for part in recipe["parts"].values() for name in part["surfaces"]}
    new = {part["material"] for part in recipe["parts"].values()}
    kept = {v.name for v in folder.glob("*.vmat")} - replaced - new
    # What a part's material named before it was baked over, such as an old AO map.
    dropped = {n for m in new if (folder / m).exists() for n in texture_names(folder / m)}
    textures, written = {}, []
    for part in recipe["parts"].values():
        stem = stem_of(part["material"])
        maps = {}
        for channel, (suffix, _) in finish.SHIPPED.items():
            target = folder / f"{stem}_{suffix}.png"
            keep_shared(folder, addon_folder, target, kept)
            shutil.copyfile(scratch / "final" / target.name, target)
            maps[channel] = str(target)
            written.append(str(target))
        textures[part["material"]] = maps
        written.append(
            modeldoc.write_baked_vmat(str(folder / part["material"]), addon_folder, stem)
        )
    adopted = headless.run_job(
        "adopt",
        scratch / f"{model}.blend",
        user_settings=True,
        textures=textures,
        save=str(folder / f"{model}.blend"),
        export_dir=str(folder),
        relink_from=str(scratch / "source"),
    )
    # A part may keep its old material's name; that file is the new one now.
    removed = [
        f"removed {path}" for path in remove_replaced(folder, addon_folder, replaced - new, dropped)
    ]
    return written + [adopted["saved"], *adopted["exported"], *removed]


def stamp_marks(plugin: str, model: str) -> list[str]:
    """Stamps the recipe's marks onto the model's own colour textures, with no bake: for models
    whose hand-made textures stay. Run it once; a second run presses the marks in again."""
    folder = game.models_dir(plugin) / model
    recipe = read_recipe(plugin, model)
    placed = headless.run_job("mark", folder / f"{model}.blend", marks=recipe.get("marks", []))
    stamped = []
    for frame in placed:
        path = Path(frame["image"])
        rough_path = path.with_name(path.name.replace("_color", "_rough"))
        written = finish.stamp_image(path, rough_path if rough_path.is_file() else None, frame)
        stamped += [str(p) for p in written]
    return stamped
