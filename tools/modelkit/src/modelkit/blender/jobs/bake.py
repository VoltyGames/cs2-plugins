"""Bakes each part of a recipe into its own texture set and gives the part one material over it.

Leaves the result in a scratch .blend for review; the model's own .blend changes only when the
`adopt` job writes it after approval.
"""

import math
from typing import Any

import bpy
import numpy as np

from modelkit.blender import bake, measure, stage


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


SIZES = (512, 1024, 2048)
# Edges meeting at more than this are shaded sharp; a 16-sided cylinder's are 22.5 degrees.
SHARP_ANGLE = math.radians(30)


def choose_size(density: float, target: float, largest: int) -> int:
    """The smallest atlas size giving `target` pixels per unit, `density` being the atlas's
    pixels per unit per pixel of width; the largest allowed when none does."""
    allowed = [size for size in SIZES if size <= largest] or [largest]
    return next((size for size in allowed if density * size >= target), allowed[-1])


def main(
    parts: dict[str, dict[str, Any]],
    finishes: dict[str, dict[str, Any]],
    marks: list[dict[str, Any]],
    folder: str,
    save_to: str,
    size: int | None = None,
    density: float = 12.0,
    largest: int = 2048,
    reserve: int = 0,
) -> dict[str, Any]:
    """`parts` maps a part's object to its new `material` and the `surfaces` it replaces, each
    with a finish name, and may set its own `size` or target `density`. `reserve` keeps that many
    pixels free along the atlas's top and right edges, for a hidden mark. Without a size, each
    part bakes at the smallest standard size reaching its density. Writes raw RGBA bakes into
    `folder` and the baked scenes to `save_to`."""
    stage.relink_missing()
    objects = [bpy.data.objects[name] for name in parts]
    painted_on = {}
    for ob in objects:
        # An earlier bake's layer: make_atlas would unwrap over the UVs its texture is painted on.
        if ob.data.uv_layers.active.name == bake.ATLAS_UV:
            ob.data.uv_layers.active.name = "painted"
        painted_on[ob.name] = ob.data.uv_layers.active.name
    results = {}
    for ob, (object_name, part) in zip(objects, parts.items(), strict=True):
        replaced = set(part["surfaces"])
        # Hard surface: a smooth-shaded flat panel averages its normals with its side walls, which
        # shades it in dark diagonal halves, in the AO bake and in game alike.
        ob.data.set_sharp_from_angle(angle=SHARP_ANGLE)
        bake.make_atlas(ob, replaced)
        target = part.get("density", density)
        chosen = (
            part.get("size") or size or choose_size(atlas_density(ob, replaced), target, largest)
        )
        if reserve:
            bake.shrink_atlas(ob, replaced, reserve / chosen)
        per_pixel = atlas_density(ob, replaced)
        copy = bake.bakeable_copy(ob, replaced)
        for index, material in enumerate(copy.data.materials):
            if material and material.name in replaced:
                working = bpy.data.materials.new(f"bake_{material.name}")
                image = bake.find_color_image(material)
                bake.build_finish(
                    working,
                    finishes[part["surfaces"][material.name]],
                    ob.dimensions.z,
                    (image, painted_on[object_name]) if image else None,
                )
                copy.data.materials[index] = working
        device = bake.use_fastest_device(copy.users_scene[0])
        files = bake.bake(copy, chosen, folder)
        bpy.data.objects.remove(copy, do_unlink=True)

        frames = [
            {**mark, **bake.uv_frame(ob, mark["at"], mark.get("surface"), mark.get("right"))}
            for mark in marks
            if mark.get("part", object_name) == object_name
        ]
        target = bpy.data.materials.get(part["material"]) or bpy.data.materials.new(
            part["material"]
        )
        for scene_object in ob.users_scene[0].objects:
            # Other parts bake their own surfaces; hulls and the like follow this one.
            if scene_object.type == "MESH" and (
                scene_object == ob or scene_object.name not in parts
            ):
                replace_materials(scene_object, replaced, target)
        for layer in [uv for uv in ob.data.uv_layers if uv.name != bake.ATLAS_UV]:
            ob.data.uv_layers.remove(layer)
        ob.data.uv_layers[bake.ATLAS_UV].active_render = True
        results[object_name] = {
            "files": files,
            "frames": frames,
            "density": per_pixel,
            "size": chosen,
            "device": device,
        }
    blocks = set(bpy.data.scenes) | set(bpy.data.actions)
    bpy.data.libraries.write(save_to, blocks, path_remap="ABSOLUTE", fake_user=True, compress=True)
    return results
