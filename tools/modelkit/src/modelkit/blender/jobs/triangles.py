"""Triangles each part can lose without looking different. With `apply`, trims them, keeping a
part's trim only if renders from all round match before and after, and saves the .blend."""

import math
from collections.abc import Collection
from typing import Any

import bmesh
import bpy
import numpy as np
from numpy.typing import NDArray

from modelkit.blender import export, trim
from modelkit.blender.stage import Stage, find_render_meshes

# Eight views round at eye level, one from above and one looking down steeply.
VIEWS = [
    (math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))
    for e, count in ((math.radians(20), 8), (math.radians(55), 1), (math.radians(85), 1))
    for a in (math.radians(i * 360 / count + 22.5) for i in range(count))
]
VIEW_SIZE = (800, 500)
# A view changed when more than ALLOWED_SHARE of its pixels moved by more than CHANGED.
CHANGED = 10 / 255
ALLOWED_SHARE = 0.0005


def count_triangles(mesh: bpy.types.Mesh) -> int:
    return sum(len(p.vertices) - 2 for p in mesh.polygons)


def render_views(scene_name: str, folder: str, tag: str) -> list[str]:
    with Stage([scene_name], VIEW_SIZE) as stage:
        return stage.render_around(VIEWS, folder, f"{scene_name}_{tag}")


def read_pixels(path: str) -> NDArray[np.float32]:
    image = bpy.data.images.load(path)
    values = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(values)
    bpy.data.images.remove(image)
    return values.reshape(-1, 4)[:, :3]


def measure_change(before: str, after: str) -> float:
    """The share of pixels that differ by more than CHANGED in any channel."""
    difference = np.abs(read_pixels(before) - read_pixels(after)).max(axis=1)
    return float((difference > CHANGED).mean())


def copy_geometry(source: bpy.types.Mesh, target: bpy.types.Mesh) -> None:
    """Replaces `target`'s geometry in place, so every object sharing it follows."""
    bm = bmesh.new()
    bm.from_mesh(source)
    bm.to_mesh(target)
    bm.free()
    target.update()


def main(
    operations: Collection[str], apply: bool = False, views_dir: str | None = None
) -> list[dict[str, Any]]:
    rows = []
    for scene, ob in find_render_meshes():
        trial = ob.data.copy()
        row = {
            "scene": scene.name,
            "object": ob.name,
            "triangles": count_triangles(ob.data),
            "removed": trim.trim(trial, operations),
        }
        rows.append(row)
        if apply:
            row["applied"] = False
        if apply and count_triangles(trial) < row["triangles"]:
            backup = ob.data.copy()
            before = render_views(scene.name, views_dir, "before")
            copy_geometry(trial, ob.data)
            after = render_views(scene.name, views_dir, "after")
            row["changed"] = max(measure_change(a, b) for a, b in zip(before, after, strict=True))
            row["applied"] = row["changed"] <= ALLOWED_SHARE
            if not row["applied"]:
                copy_geometry(backup, ob.data)
            bpy.data.meshes.remove(backup)
        bpy.data.meshes.remove(trial)
    if apply and any(row["applied"] for row in rows):
        export.save_everything(bpy.data.filepath)
    return rows
