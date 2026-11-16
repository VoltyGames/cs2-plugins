"""Bakes each part of a recipe into its own texture set under one new material, and saves the
result to a scratch .blend; the model's own .blend changes only when `ship` writes it."""

import math
import os
from typing import Any

import bpy

from modelkit.blender import atlas, export
from modelkit.blender.cycles import bake_texture_set, use_fastest_device
from modelkit.blender.nodes import find_image
from modelkit.blender.session import relink_images
from modelkit.blender.wear import WornMaterial

# Edges meeting at more than this are shaded sharp; a 16-sided cylinder's are 22.5 degrees.
SHARP_ANGLE = math.radians(30)


def choose_size(density: float, target: float, sizes: list[int]) -> int:
    """The smallest atlas size giving `target` pixels per unit, `density` being the atlas's
    pixels per unit per pixel of width; the largest when none does."""
    return next((size for size in sizes if density * size >= target), sizes[-1])


class PartBake:
    def __init__(
        self, name: str, part: dict[str, Any], finishes: dict[str, dict[str, Any]]
    ) -> None:
        self.ob = bpy.data.objects[name]
        self.part = part
        self.surfaces = set(part["surfaces"])
        self.finishes = {old: finishes[finish] for old, finish in part["surfaces"].items()}
        # An earlier bake's layer: make_atlas would unwrap over the UVs its texture is painted on.
        if self.ob.data.uv_layers.active.name == atlas.ATLAS_UV:
            self.ob.data.uv_layers.active.name = "painted"
        self.painted_uv = self.ob.data.uv_layers.active.name

    def unwrap(self, sizes: list[int], reserve: int) -> tuple[int, float]:
        """Makes the atlas; returns its size and its pixels per unit per pixel of width."""
        # A smooth-shaded flat panel averages its normals with its side walls and shades dark.
        self.ob.data.set_sharp_from_angle(angle=SHARP_ANGLE)
        atlas.make_atlas(self.ob, self.surfaces)
        density = atlas.measure_density(self.ob, self.surfaces)
        size = self.part.get("size") or choose_size(density, self.part["density"], sizes)
        if reserve:
            atlas.shrink_atlas(self.ob, self.surfaces, reserve / size)
            density *= 1.0 - reserve / size
        return size, density

    def bake(self, size: int, folder: str, device: str) -> dict[str, str]:
        copy = atlas.make_bake_copy(self.ob, self.surfaces)
        for index, material in enumerate(copy.data.materials):
            if material and material.name in self.surfaces:
                working = bpy.data.materials.new(f"bake_{material.name}")
                image = find_image(material)
                artwork = (image, self.painted_uv) if image else None
                WornMaterial(working, self.finishes[material.name], self.ob.dimensions.z, artwork)
                copy.data.materials[index] = working
        files = bake_texture_set(copy, size, folder, device)
        bpy.data.objects.remove(copy, do_unlink=True)
        return files

    def place_marks(self, marks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        placer = atlas.MarkPlacer(self.ob)
        mine = [mark for mark in marks if mark.get("part", self.ob.name) == self.ob.name]
        return [
            {**mark, **placer.place(mark["at"], mark.get("surface"), mark.get("right"))}
            for mark in mine
        ]

    def adopt_material(self, others: set[str]) -> None:
        """Gives the baked faces the part's new material and keeps only the atlas UVs. Hulls
        and other unbaked objects in the scene follow; other parts bake their own surfaces."""
        name = self.part["material"]
        target = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        for ob in self.ob.users_scene[0].objects:
            if ob.type == "MESH" and (ob == self.ob or ob.name not in others):
                for index, material in enumerate(ob.data.materials):
                    if material and material.name in self.surfaces:
                        ob.data.materials[index] = target
        for layer in [uv for uv in self.ob.data.uv_layers if uv.name != atlas.ATLAS_UV]:
            self.ob.data.uv_layers.remove(layer)
        self.ob.data.uv_layers[atlas.ATLAS_UV].active_render = True


def main(
    parts: dict[str, dict[str, Any]],
    finishes: dict[str, dict[str, Any]],
    marks: list[dict[str, Any]],
    folder: str,
    save_to: str,
    sizes: list[int],
    reserve: int,
) -> dict[str, Any]:
    """Writes raw RGBA bakes into `folder`. Each part bakes at its `size`, else the smallest of
    `sizes` reaching its `density`; `reserve` keeps that many pixels free along the
    atlas's top and right edges for the hidden mark."""
    relink_images(os.path.dirname(bpy.data.filepath))
    bakes = [PartBake(name, part, finishes) for name, part in parts.items()]
    device = use_fastest_device()
    results = {}
    for bake in bakes:
        size, per_pixel = bake.unwrap(sizes, reserve)
        results[bake.ob.name] = {
            "files": bake.bake(size, folder, device),
            "frames": bake.place_marks(marks),
            "pixels_per_unit": per_pixel * size,
        }
        bake.adopt_material(set(parts))
    export.save_everything(save_to, remap="ABSOLUTE")
    return {"device": device, "parts": results}
