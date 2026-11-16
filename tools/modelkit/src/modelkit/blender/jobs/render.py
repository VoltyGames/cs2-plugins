"""A reference render of a whole model: every part's scene in one, posed at its idle's first
frame, from a three-quarter view at eye level. For concept work."""

from collections.abc import Iterable, Sequence
from typing import Any

import bpy

from modelkit.blender import stage

THREE_QUARTER = (1.0, -0.85, 0.38)


def main(
    path: str,
    skip: Iterable[str] = (),
    at: dict[str, Sequence[float]] | None = None,
    size: tuple[int, int] = (1600, 1000),
) -> dict[str, Any]:
    names = [sc.name for sc in bpy.data.scenes if sc.name not in set(skip)]
    scene = stage.gather(names, at)
    parts = sorted(ob.name for ob in scene.objects if ob.type == "MESH")
    stage.light(scene, size)
    stage.aim(scene, THREE_QUARTER)
    stage.render(scene, path)
    return {"path": path, "parts": parts}
