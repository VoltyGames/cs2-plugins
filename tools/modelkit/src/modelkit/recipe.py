"""Bake recipes: plugins/<plugin>/bake/<model>.json, over the plugin's shared
bake/defaults.json. Recipes stay out of content/, which `voltmod content compile --prune` prunes.

    {
      "density": 12,                      pixels per game unit; or a fixed "size"
      "parts": {"<object>": {"material": "<new>.vmat", "surfaces": {"<old>.vmat": "<finish>"},
                             "density": 16}},
      "finishes": {"<finish>": {...}},    on top of the shared ones; "extends" copies one
      "hidden_mark": "<text>",            written into the atlas band no face uses
      "at": {"<scene>": [x, y, z]}        parts the plugin stacks in code, for the preview
    }

defaults.json, when present, holds `finishes` every recipe can use.

A finish: `base` and `under` ("polyhaven:<id>" or "ambientcg:<id>") are the surface and what
its worn edges show; `tile` is game units per repeat; `blend` (0.25) softens box-projection
seams; `hue_shift`, `saturation` and `tint` recolour the base; `paint` ([r, g, b], linear) is
a solid colour keeping `grain` (0.6) of the base's grain, and `camo` ({"colors", "scale",
"detail"}) blobs of colour; `artwork: true` keeps the surface's own colour texture;
`metallic` overrides metalness; `wear`, `grime`, `dust`, `streaks` run 0-1; `normal_strength`
defaults to 0.5.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Self

from modelkit import game, library
from modelkit.audit.uv import TARGET_DENSITY

SIZES = (512, 1024, 2048)

type Settings = dict[str, Any]


def read_json(path: Path) -> Settings:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def merge_finishes(shared: dict[str, Settings], own: dict[str, Settings]) -> dict[str, Settings]:
    """The shared finishes under the recipe's; {"extends": name, ...} overrides a shared one."""
    merged = shared | own
    for name, settings in own.items():
        if base := settings.get("extends"):
            merged[name] = shared[base] | {k: v for k, v in settings.items() if k != "extends"}
    return merged


@dataclass(frozen=True)
class Part:
    name: str
    material: str
    surfaces: dict[str, str]
    """The old .vmat names it replaces, each with its finish."""
    density: float
    size: int | None = None

    @property
    def stem(self) -> str:
        return PurePosixPath(self.material).stem


@dataclass(frozen=True)
class Recipe:
    parts: list[Part]
    finishes: dict[str, Settings]
    hidden_mark: str | None
    offsets: dict[str, list[float]] = field(default_factory=dict)

    @classmethod
    def load(cls, plugin: str, model: str) -> Self:
        folder = game.plugin_dir(plugin) / "bake"
        path = folder / f"{model}.json"
        if not path.is_file():
            raise FileNotFoundError(f"no bake recipe {path}")
        recipe, shared = read_json(path), read_json(folder / "defaults.json")
        density = recipe.get("density", TARGET_DENSITY)
        parts = [
            Part(
                name,
                part["material"],
                part["surfaces"],
                part.get("density", density),
                part.get("size", recipe.get("size")),
            )
            for name, part in recipe.get("parts", {}).items()
        ]
        return cls(
            parts=parts,
            finishes=merge_finishes(shared.get("finishes", {}), recipe.get("finishes", {})),
            hidden_mark=recipe.get("hidden_mark"),
            offsets=recipe.get("at", {}),
        )

    @property
    def replaced(self) -> set[str]:
        return {name for part in self.parts for name in part.surfaces}

    @property
    def materials(self) -> set[str]:
        return {part.material for part in self.parts}

    def resolve_finishes(self) -> dict[str, Settings]:
        """The finishes the parts use, each material name replaced by its downloaded maps."""
        used = {finish for part in self.parts for finish in part.surfaces.values()}
        missing = used - set(self.finishes)
        if missing:
            raise ValueError(f"no finish {', '.join(sorted(missing))} in the recipe or defaults")
        resolved = {}
        for name in used:
            finish = self.finishes[name]
            maps = {
                key: library.find_maps(finish[key]) for key in ("base", "under") if key in finish
            }
            resolved[name] = finish | maps
        return resolved
