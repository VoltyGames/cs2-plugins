"""Store cards rendered from the models, listed in plugins/<plugin>/bake/icons.json:

    {
      "size": [384, 256],
      "icons": {"<card>": {"model": "<folder>", "skip": ["<scene>"], "at": {"<scene>": [x, y, z]},
                           "pose": {"<scene>": ["<action>", frame]}, "view": [x, y, z]}}
    }

A part holds its scene's idle at frame 0 unless `pose` names another action and frame.

A card renders at twice its size in Blender, the model on a concrete floor that fades out. It is
laid on a dark studio gradient and downsampled into
plugins/<plugin>/panorama/images/<plugin>/<card>.png.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from modelkit import game, headless, library

SUPERSAMPLE = 2
# The backdrop behind the rendered floor, in sRGB grey: the old cards' charcoal wall, brightest in
# the middle, with blue a little above red and green.
WALL = (14.0, 36.0)
TINT = np.array([0.0, -1.0, 3.0])
GRAIN = 1.2
FLOOR = "polyhaven:concrete_floor_02"


def studio(size: tuple[int, int]) -> Image.Image:
    """The card background the render is laid on; the floor comes from the render itself."""
    width, height = size
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)
    middle = np.clip(1 - np.hypot((x / width - 0.5) * 1.1, (y / height - 0.5) * 1.0), 0, 1)
    grey = WALL[0] + (WALL[1] - WALL[0]) * middle**1.2
    grey += np.random.default_rng(0).normal(0, GRAIN, grey.shape)
    rgb = np.clip(grey[..., None] + TINT, 0, 255)
    return Image.fromarray(rgb.round().astype(np.uint8), "RGB").convert("RGBA")


def read_list(plugin: str) -> dict[str, Any]:
    path = game.plugin_dir(plugin) / "bake" / "icons.json"
    if not path.is_file():
        raise FileNotFoundError(f"no icon list {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def card_path(plugin: str, card: str) -> Path:
    return game.plugin_dir(plugin) / "panorama" / "images" / plugin / f"{card}.png"


def render(plugin: str, card: str, settings: dict[str, Any], size: tuple[int, int]) -> Path:
    blend = game.models_dir(plugin) / settings["model"] / f"{settings['model']}.blend"
    if not blend.is_file():
        raise FileNotFoundError(f"no {blend}")
    scratch = game.REPO / "build" / "icons" / plugin / f"{card}.png"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    optional = {key: settings[key] for key in ("skip", "at", "pose", "view") if key in settings}
    headless.run_job(
        "icon",
        blend,
        path=str(scratch),
        floor_maps=library.find_maps(FLOOR),
        size=[size[0] * SUPERSAMPLE, size[1] * SUPERSAMPLE],
        **optional,
    )
    out = card_path(plugin, card)
    with Image.open(scratch) as image:
        subject = image.convert("RGBA")
    card = Image.alpha_composite(studio(subject.size), subject)
    card.resize(size, Image.Resampling.LANCZOS).save(out, optimize=True)
    return out
