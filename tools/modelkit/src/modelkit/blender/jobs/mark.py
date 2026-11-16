"""Finds where each maker's mark lands on a model's own textures, for stamping without a bake."""

import os
from typing import Any

import bpy

from modelkit.blender.atlas import MarkPlacer
from modelkit.blender.nodes import find_image
from modelkit.blender.session import relink_images


def main(marks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each mark with its frame on the part's render UVs and the colour image there."""
    relink_images(os.path.dirname(bpy.data.filepath))
    placers: dict[str, MarkPlacer] = {}
    placed = []
    for mark in marks:
        ob = bpy.data.objects[mark["part"]]
        if ob.name not in placers:
            render_uv = next(uv for uv in ob.data.uv_layers if uv.active_render)
            placers[ob.name] = MarkPlacer(ob, render_uv.name)
        frame = placers[ob.name].place(mark["at"], mark.get("surface"), mark.get("right"))
        image = find_image(bpy.data.materials[frame["material"]])
        if image is None:
            raise ValueError(f"{frame['material']} has no colour texture for a mark")
        # A repeating texture: the mark goes where the face's UVs wrap to.
        frame["uv"] = [value % 1.0 for value in frame["uv"]]
        placed.append({**mark, **frame, "image": bpy.path.abspath(image.filepath)})
    return placed
