"""UV measurements for every render mesh in the open .blend, per scene and material."""

from typing import Any

import bpy
import numpy as np
from numpy.typing import NDArray

from modelkit.blender import export, measure
from modelkit.blender.stage import SKIPPED


def triangles(
    ob: bpy.types.Object,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int64], list[str]]:
    """World-space points (n, 3, 3), UVs (n, 3, 2) and material indices of a mesh's triangles."""
    mesh = ob.data.copy()
    mesh.transform(ob.matrix_world)
    mesh.calc_loop_triangles()
    count = len(mesh.loop_triangles)
    coords = np.empty(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", coords)
    uv = np.empty(len(mesh.loops) * 2)
    mesh.uv_layers.active.data.foreach_get("uv", uv)
    verts = np.empty(count * 3, dtype=np.int64)
    mesh.loop_triangles.foreach_get("vertices", verts)
    loops = np.empty(count * 3, dtype=np.int64)
    mesh.loop_triangles.foreach_get("loops", loops)
    materials = np.empty(count, dtype=np.int64)
    mesh.loop_triangles.foreach_get("material_index", materials)
    names = [m.name if m else "" for m in mesh.materials]
    bpy.data.meshes.remove(mesh)
    points = coords.reshape(-1, 3)[verts.reshape(-1, 3)]
    return points, uv.reshape(-1, 2)[loops.reshape(-1, 3)], materials, names


def main() -> list[dict[str, Any]]:
    """One row per part and material; an atlas's fill and overlap cover every part using it."""
    rows, atlases = [], {}
    for sc in bpy.data.scenes:
        files = export.read_settings(sc.name).get("files", {}) if sc.get(export.SETTINGS) else {}
        for ob in sc.objects:
            if ob.type != "MESH" or not ob.data.uv_layers or SKIPPED.search(ob.name):
                continue
            points, uvs, materials, names = triangles(ob)
            for index, material in enumerate(names):
                chosen = materials == index
                if not material or not chosen.any():
                    continue
                measured = measure.summarize(points[chosen], uvs[chosen])
                if measured["atlas"]:
                    atlases.setdefault(material, []).append(uvs[chosen])
                rows.append(
                    {
                        "scene": sc.name,
                        "object": ob.name,
                        "dmx": files.get(ob.name, ob.name),
                        "material": material,
                        **measured,
                    }
                )
    fills = {material: measure.fill(np.concatenate(parts)) for material, parts in atlases.items()}
    for row in rows:
        row["coverage"], row["overlap"] = fills[row["material"]] if row["atlas"] else (None, None)
    return rows
