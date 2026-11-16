"""UV measurements for every render mesh in the open .blend, per scene and material."""

from typing import Any

import bpy
import numpy as np

from modelkit.blender import export, measure
from modelkit.blender.atlas import read_triangles
from modelkit.blender.stage import SKIPPED


def main() -> list[dict[str, Any]]:
    """One row per part and material; an atlas's fill and overlap cover every part using it."""
    rows, atlases = [], {}
    for sc in bpy.data.scenes:
        files = export.read_settings(sc.name).get("files", {}) if sc.get(export.SETTINGS) else {}
        for ob in sc.objects:
            if ob.type != "MESH" or not ob.data.uv_layers or SKIPPED.search(ob.name):
                continue
            points, uvs, slots = read_triangles(ob)
            for index, material in enumerate(ob.data.materials):
                chosen = slots == index
                if not material or not chosen.any():
                    continue
                measured = measure.summarize(points[chosen], uvs[chosen])
                if measured["atlas"]:
                    atlases.setdefault(material.name, []).append(uvs[chosen])
                rows.append(
                    {
                        "scene": sc.name,
                        "object": ob.name,
                        "dmx": files.get(ob.name, ob.name),
                        "material": material.name,
                        **measured,
                    }
                )
    fills = {material: measure.fill(np.concatenate(parts)) for material, parts in atlases.items()}
    for row in rows:
        row["coverage"], row["overlap"] = fills[row["material"]] if row["atlas"] else (None, None)
    return rows
