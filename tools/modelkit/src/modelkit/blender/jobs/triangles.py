"""Triangles each part can lose without looking different. With `apply`, trims them, renders
the part from all round before and after, keeps the trim only where no view changed, and saves
the .blend."""

import math
import os
from collections.abc import Collection
from typing import Any

import bmesh
import bpy
import numpy as np
from numpy.typing import NDArray

from modelkit.blender import stage, trim
from modelkit.blender.stage import SKIPPED

OPERATIONS = ("degenerate", "coplanar", "hidden")
# Eight views round at eye level, one from above and one looking down steeply.
VIEWS = [
    (math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))
    for e, count in ((math.radians(20), 8), (math.radians(55), 1), (math.radians(85), 1))
    for a in (math.radians(i * 360 / count + 22.5) for i in range(count))
]
VIEW_SIZE = (800, 500)
# A view changed when more than this share of its pixels moved by more than CHANGED.
CHANGED = 10 / 255
ALLOWED_SHARE = 0.0005


def parts() -> list[tuple[str, bpy.types.Object]]:
    """(scene, object) for each render mesh, each mesh once."""
    seen, found = set(), []
    for sc in bpy.data.scenes:
        for ob in sc.objects:
            if ob.type == "MESH" and not SKIPPED.search(ob.name) and ob.data.name not in seen:
                seen.add(ob.data.name)
                found.append((sc.name, ob))
    return found


def triangle_count(mesh: bpy.types.Mesh) -> int:
    return sum(len(p.vertices) - 2 for p in mesh.polygons)


def render_views(scene_name: str, folder: str, tag: str) -> list[str]:
    scene = stage.gather([scene_name])
    stage.light(scene, VIEW_SIZE)
    paths = []
    for index, direction in enumerate(VIEWS):
        stage.aim(scene, direction)
        paths.append(stage.render(scene, os.path.join(folder, f"{scene_name}_{index}_{tag}.png")))
    stage.remove(scene)
    return paths


def pixels(path: str) -> NDArray[np.float32]:
    image = bpy.data.images.load(path)
    values = np.array(image.pixels[:], dtype=np.float32).reshape(-1, 4)[:, :3]
    bpy.data.images.remove(image)
    return values


def changed_share(before: str, after: str) -> float:
    """The share of pixels that differ by more than CHANGED in any channel."""
    return float((np.abs(pixels(before) - pixels(after)).max(axis=1) > CHANGED).mean())


def restore(mesh: bpy.types.Mesh, backup: bpy.types.Mesh) -> None:
    bm = bmesh.new()
    bm.from_mesh(backup)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def save(path: str) -> None:
    """Writes every scene and action back, as export.save_blend does, without the UI."""
    blocks = set(bpy.data.scenes) | set(bpy.data.actions)
    bpy.data.libraries.write(path, blocks, path_remap="RELATIVE_ALL", fake_user=True, compress=True)


def main(
    apply: bool = False, operations: Collection[str] = OPERATIONS, views_dir: str | None = None
) -> list[dict[str, Any]]:
    rows = []
    for scene_name, ob in parts():
        before = triangle_count(ob.data)
        row = {"scene": scene_name, "object": ob.name, "triangles": before}
        if not apply:
            trial = ob.data.copy()
            row["removed"] = trim.trim(trial, operations)
            bpy.data.meshes.remove(trial)
            rows.append(row)
            continue
        backup = ob.data.copy()
        views_before = render_views(scene_name, views_dir, "before")
        row["removed"] = trim.trim(ob.data, operations)
        if triangle_count(ob.data) == before:
            row["applied"] = False
        else:
            views_after = render_views(scene_name, views_dir, "after")
            worst = max(changed_share(a, b) for a, b in zip(views_before, views_after))
            row["changed"] = worst
            row["applied"] = worst <= ALLOWED_SHARE
            if not row["applied"]:
                restore(ob.data, backup)
        bpy.data.meshes.remove(backup)
        rows.append(row)
    if apply and any(row["applied"] for row in rows):
        save(bpy.data.filepath)
    return rows
