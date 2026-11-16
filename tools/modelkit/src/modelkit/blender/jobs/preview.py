"""Shows baked texture sets on their materials and renders the model from three sides."""

import os
from typing import Any

import bpy

from modelkit.blender.nodes import show_texture_set
from modelkit.blender.stage import THREE_QUARTER, Stage

# Three quarters from the front left, from the back right, and from above.
SIDES = (THREE_QUARTER, (-1.0, 0.85, 0.3))
ABOVE = (0.4, -0.3, 1.2)


def main(
    textures: dict[str, dict[str, str]], folder: str, at: dict[str, list[float]] | None = None
) -> dict[str, Any]:
    for name, maps in textures.items():
        show_texture_set(bpy.data.materials[name], maps)
    with Stage([s.name for s in bpy.data.scenes], at=at) as stage:
        renders = stage.render_around(SIDES, folder, "view", distance=1.2)
        stage.aim(ABOVE, distance=1.4)
        renders.append(stage.render(os.path.join(folder, f"view_{len(SIDES)}.png")))
    return {"renders": renders}
