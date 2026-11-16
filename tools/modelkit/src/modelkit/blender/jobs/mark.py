"""Finds where each maker's mark lands on a model's own textures, for stamping without a bake."""

from typing import Any

import bpy

from modelkit.blender import bake, stage


def main(marks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each mark with its UV frame on the part's render UVs and the colour image of the material
    there."""
    stage.relink_missing()
    placed = []
    for mark in marks:
        ob = bpy.data.objects[mark["part"]]
        layer = next(uv for uv in ob.data.uv_layers if uv.active_render)
        frame = bake.uv_frame(ob, mark["at"], mark.get("surface"), mark.get("right"), layer.name)
        image = bake.find_color_image(bpy.data.materials[frame["material"]])
        if image is None:
            raise ValueError(f"{frame['material']} has no colour texture for a mark")
        # A repeating texture: the mark goes where the face's UVs wrap to.
        frame["uv"] = [value % 1.0 for value in frame["uv"]]
        placed.append({**mark, **frame, "image": bpy.path.abspath(image.filepath)})
    return placed
