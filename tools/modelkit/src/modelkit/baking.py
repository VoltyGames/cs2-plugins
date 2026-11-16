"""Retexturing a model from its bake recipe, plugins/<plugin>/bake/<model>.json. Recipes stay
out of content/, whose unreferenced files `voltmod content compile --prune` deletes.

`preview` bakes into build/bake/<plugin>/<model>/ and renders the result; nothing in the model
folder changes. `write` then ships that bake: the PNGs and .vmat into the model folder, the
.blend saved and the DMX re-exported.

A recipe:

    {
      "size": 2048,
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

`at` in a mark is a point in Blender units on the face to stamp; the top-level `at` places parts
the plugin stacks in code, for the preview render.
"""

import json
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from modelkit import finish, game, headless, library
from modelkit.source2 import modeldoc

# The atlas share kept free along its top edge for the hidden mark.
HIDDEN_BAND = 0.03


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


def preview(plugin: str, model: str) -> Preview:
    folder = game.models_dir(plugin) / model
    recipe = read_recipe(plugin, model)
    scratch = scratch_dir(plugin, model)
    if scratch.exists():
        shutil.rmtree(scratch)
    (scratch / "raw").mkdir(parents=True)
    baked = headless.run_job(
        "bake",
        folder / f"{model}.blend",
        parts=recipe["parts"],
        finishes=resolve_finishes(recipe["finishes"]),
        marks=recipe.get("marks", []),
        size=recipe.get("size", 2048),
        folder=str(scratch / "raw"),
        save_to=str(scratch / f"{model}.blend"),
        reserve=HIDDEN_BAND if recipe.get("hidden_mark") else 0.0,
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
        size = recipe.get("size", 2048)
        density[object_name] = result["density"] * min(size, game.read_texture_cap() or size)
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


def remove_replaced(folder: Path, addon_folder: str, replaced: set[str]) -> list[str]:
    """Deletes the replaced .vmat files and the textures no remaining .vmat names."""
    names: set[str] = set()
    for name in replaced:
        vmat = folder / name
        if vmat.exists():
            names |= texture_names(vmat)
            vmat.unlink()
    still_used = {name for vmat in folder.glob("*.vmat") for name in texture_names(vmat)}
    removed = [name for name in sorted(names - still_used) if (folder / name).exists()]
    for name in removed:
        (folder / name).unlink()
    return [str(folder / name) for name in sorted(replaced)] + [str(folder / n) for n in removed]


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
    )
    removed = [f"removed {path}" for path in remove_replaced(folder, addon_folder, replaced)]
    return written + [adopted["saved"], *adopted["exported"], *removed]
