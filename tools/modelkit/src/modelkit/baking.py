"""Retexturing a model from its bake recipe (see modelkit.recipe).

`preview` bakes into build/bake/<plugin>/<model>/ and renders the result, leaving the model
folder alone; `write` then ships that bake into the model folder.
"""

import shutil
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path, PurePosixPath

from modelkit import game, headless
from modelkit.git_files import export_folder
from modelkit.models import ModelFolder
from modelkit.recipe import SIZES, Recipe
from modelkit.source2 import vmat
from modelkit.texture_set import TextureSet

# Pixels kept free along the atlas's top edge for the hidden mark: the bake's 12-pixel margin
# spills into it, and the mark needs clear rows beyond that.
HIDDEN_BAND = 40


@dataclass(frozen=True)
class Preview:
    renders: list[str]
    pixels_per_unit: dict[str, float]
    device: str


class ModelBake:
    def __init__(self, plugin: str, model: str) -> None:
        self.plugin = plugin
        self.folder = ModelFolder(plugin, game.models_dir(plugin) / model)
        self.scratch = game.REPO / "build" / "bake" / plugin / model
        self.baked_blend = self.scratch / f"{model}.blend"

    @cached_property
    def recipe(self) -> Recipe:
        return Recipe.load(self.plugin, self.folder.name)

    def extract_source(self, revision: str) -> Path:
        """The model folder as it was at `revision` of the plugin's repo, in the scratch folder;
        returns its .blend."""
        folder = PurePosixPath("content", "models", self.plugin, self.folder.name)
        into = self.scratch / "source"
        if into.exists():
            shutil.rmtree(into)
        export_folder(game.plugin_dir(self.plugin), folder, revision, into)
        blend = into / self.folder.blend.name
        if not blend.is_file():
            raise FileNotFoundError(f"no {blend.name} in {folder} at {revision}")
        return blend

    def preview(self, source: str | None = None) -> Preview:
        """Bakes the recipe; `source`, a revision of the plugin's repo, bakes from the model's
        .blend as it was then."""
        recipe = self.recipe
        if not recipe.parts:
            raise ValueError(f"the {self.folder.name} recipe has no parts to bake")
        if self.scratch.exists():
            shutil.rmtree(self.scratch)
        (self.scratch / "raw").mkdir(parents=True)
        blend = self.extract_source(source) if source else self.folder.blend
        largest = game.read_texture_cap() or SIZES[-1]
        baked = headless.run_job(
            "bake",
            blend,
            parts={
                part.name: {
                    "material": part.material,
                    "surfaces": part.surfaces,
                    "density": part.density,
                    "size": part.size,
                }
                for part in recipe.parts
            },
            finishes=recipe.resolve_finishes(),
            folder=str(self.scratch / "raw"),
            save_to=str(self.baked_blend),
            sizes=[size for size in SIZES if size <= largest] or [largest],
            reserve=HIDDEN_BAND if recipe.hidden_mark else 0,
        )
        textures, density = {}, {}
        for part in recipe.parts:
            result = baked["parts"][part.name]
            texture_set = TextureSet(result["files"])
            if recipe.hidden_mark:
                texture_set.hide(recipe.hidden_mark)
            written = texture_set.save(self.scratch / "final", part.stem)
            textures[part.material] = {channel: str(path) for channel, path in written.items()}
            density[part.name] = result["pixels_per_unit"]
        shown = headless.run_job(
            "preview",
            self.baked_blend,
            textures=textures,
            folder=str(self.scratch),
            at=recipe.offsets,
        )
        return Preview(shown["renders"], density, baked["device"])

    def keep_shared(self, target: Path, kept_materials: set[str]) -> None:
        """Before `target` is overwritten, moves it to a _flat_ name for the kept materials still
        using it, such as a flat roughness map shared by glass and glow."""
        reference = f"{self.folder.addon_path}{target.name}"
        users = [
            path
            for path in self.folder.path.glob("*.vmat")
            if path.name in kept_materials and reference in path.read_text()
        ]
        if not users or not target.exists():
            return
        stem, _, suffix = target.stem.rpartition("_")
        kept = target.with_name(f"{stem}_flat_{suffix}.png")
        if not kept.exists():
            shutil.copyfile(target, kept)
        for path in users:
            text = path.read_text().replace(reference, f"{self.folder.addon_path}{kept.name}")
            path.write_text(text, newline="\n")

    def remove_replaced(self, replaced: set[str], dropped: set[str]) -> list[str]:
        """Deletes the replaced .vmat files, and their textures and `dropped` ones that no
        remaining .vmat names."""
        folder = self.folder.path
        names = set(dropped)
        deleted = sorted(name for name in replaced if (folder / name).exists())
        for name in deleted:
            names |= self.folder.read_texture_names(name)
            (folder / name).unlink()
        still_used = {
            n for path in folder.glob("*.vmat") for n in self.folder.read_texture_names(path.name)
        }
        removed = [name for name in sorted(names - still_used) if (folder / name).exists()]
        for name in removed:
            (folder / name).unlink()
        return [str(folder / name) for name in deleted + removed]

    def write(self) -> list[str]:
        """Ships the last preview; returns the files written and removed."""
        if not self.baked_blend.is_file():
            raise FileNotFoundError(
                f"no preview in {self.scratch}; run modelkit bake without --write first"
            )
        recipe, folder = self.recipe, self.folder.path
        kept = {path.name for path in folder.glob("*.vmat")} - recipe.replaced - recipe.materials
        # What a part's material named before it was baked over, such as an old AO map.
        dropped = {
            name
            for material in recipe.materials
            if (folder / material).exists()
            for name in self.folder.read_texture_names(material)
        }
        textures, written = defaultdict(dict), []
        for part in recipe.parts:
            for channel, suffix in vmat.BAKED_SUFFIXES.items():
                target = folder / f"{part.stem}_{suffix}.png"
                self.keep_shared(target, kept)
                shutil.copyfile(self.scratch / "final" / target.name, target)
                textures[part.material][channel] = str(target)
                written.append(str(target))
            path = vmat.write_baked_vmat(folder / part.material, self.folder.addon_path, part.stem)
            written.append(str(path))
        shipped = headless.run_job(
            "ship",
            self.baked_blend,
            user_settings=True,
            textures=textures,
            save=str(self.folder.blend),
            export_dir=str(folder),
            relink_from=str(self.scratch / "source"),
        )
        # A part may keep its old material's name; that file is the new one now.
        removed = self.remove_replaced(recipe.replaced - recipe.materials, dropped)
        return written + [
            shipped["saved"],
            *shipped["exported"],
            *(f"removed {p}" for p in removed),
        ]
