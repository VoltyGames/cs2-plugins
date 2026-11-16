"""A reference render of a whole model, every part posed at its idle, for concept work."""

from collections.abc import Iterable, Sequence
from typing import Any

import bpy

from modelkit.blender.stage import THREE_QUARTER, Stage


def main(
    path: str, skip: Iterable[str] = (), at: dict[str, Sequence[float]] | None = None
) -> dict[str, Any]:
    names = [sc.name for sc in bpy.data.scenes if sc.name not in set(skip)]
    with Stage(names, at=at) as stage:
        stage.aim(THREE_QUARTER)
        stage.render(path)
        return {"path": path, "parts": stage.parts}
