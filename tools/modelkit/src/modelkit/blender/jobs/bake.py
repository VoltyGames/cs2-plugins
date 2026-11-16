"""Bakes each part of a recipe into its own texture set and gives the part one material over it.

Leaves the result in a scratch .blend for review; the model's own .blend changes only when the
`adopt` job writes it after approval.
"""

from typing import Any

import bpy
import numpy as np

from modelkit.blender import bake, measure


def replace_materials(ob: bpy.types.Object, old: set[str], new: bpy.types.Material) -> None:
    for index, material in enumerate(ob.data.materials):
        if material and material.name in old:
            ob.data.materials[index] = new


def atlas_density(ob: bpy.types.Object, materials: set[str]) -> float:
    """Pixels per unit per texture pixel of width over the baked faces, as measure reports it."""
    mesh = ob.data
    mesh.calc_loop_triangles()
    layer = mesh.uv_layers[bake.ATLAS_UV]
    chosen = {i for i, m in enumerate(mesh.materials) if m and m.name in materials}
    tris = [t for t in mesh.loop_triangles if t.material_index in chosen]
    points = np.array([[mesh.vertices[v].co[:] for v in t.vertices] for t in tris])
    uvs = np.array([[layer.data[loop].uv[:] for loop in t.loops] for t in tris])
    return measure.summarize(points, uvs)["density"]


def main(
    parts: dict[str, dict[str, Any]],
    finishes: dict[str, dict[str, Any]],
    marks: list[dict[str, Any]],
    size: int,
    folder: str,
    save_to: str,
    reserve: float = 0.0,
) -> dict[str, Any]:
    """`parts` maps a part's object to its new `material` and the `surfaces` it replaces, each
    with a finish name. Writes raw RGBA bakes into `folder` and the baked scenes to `save_to`."""
    results = {}
    for object_name, part in parts.items():
        ob = bpy.data.objects[object_name]
        replaced = set(part["surfaces"])
        painted_on = ob.data.uv_layers.active.name
        bake.make_atlas(ob, replaced, reserve=reserve)
        copy = bake.bakeable_copy(ob, replaced)
        for index, material in enumerate(copy.data.materials):
            if material and material.name in replaced:
                working = bpy.data.materials.new(f"bake_{material.name}")
                image = bake.find_color_image(material)
                bake.build_finish(
                    working,
                    finishes[part["surfaces"][material.name]],
                    ob.dimensions.z,
                    (image, painted_on) if image else None,
                )
                copy.data.materials[index] = working
        device = bake.use_fastest_device(copy.users_scene[0])
        files = bake.bake(copy, size, folder)
        bpy.data.objects.remove(copy, do_unlink=True)

        frames = [
            {**mark, **bake.uv_frame(ob, mark["at"])}
            for mark in marks
            if mark.get("part", object_name) == object_name
        ]
        density = atlas_density(ob, replaced)
        target = bpy.data.materials.get(part["material"]) or bpy.data.materials.new(
            part["material"]
        )
        for scene_object in ob.users_scene[0].objects:
            if scene_object.type == "MESH":
                replace_materials(scene_object, replaced, target)
        for layer in [uv for uv in ob.data.uv_layers if uv.name != bake.ATLAS_UV]:
            ob.data.uv_layers.remove(layer)
        ob.data.uv_layers[bake.ATLAS_UV].active_render = True
        results[object_name] = {
            "files": files,
            "frames": frames,
            "density": density,
            "device": device,
        }
    blocks = set(bpy.data.scenes) | set(bpy.data.actions)
    bpy.data.libraries.write(save_to, blocks, path_remap="ABSOLUTE", fake_user=True, compress=True)
    return results
