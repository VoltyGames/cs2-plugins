"""Showing the model: the user's viewport, renders and contact sheets."""

import math
from collections.abc import Iterable

import bpy
import numpy as np
from mathutils import Vector

from modelkit.blender import objects, shapes, surfaces
from modelkit.blender.session import PREVIEW_OBJECTS

type Vec3 = tuple[float, float, float] | Vector


def stage() -> None:
    """Adds a camera, a sun, a grey world and an unexported ground plane when missing.

    Scenes share the preview objects: a second copy would be renamed and lose its lookup name.
    """
    sc = bpy.context.scene
    if "preview_camera" not in bpy.data.objects:
        bpy.data.objects.new("preview_camera", bpy.data.cameras.new("preview_camera"))
    if "preview_sun" not in bpy.data.objects:
        sun = bpy.data.objects.new("preview_sun", bpy.data.lights.new("preview_sun", "SUN"))
        sun.data.energy = 3.5
        sun.rotation_euler = (math.radians(40), math.radians(10), math.radians(30))
    if "preview_ground" not in bpy.data.objects:
        ground = objects.to_object("preview_ground", shapes.box((0, 0, -0.01), (600, 600, 0.01)))
        sc.collection.objects.unlink(ground)
        mat = surfaces.material("preview_ground", metallic=0.0, roughness=0.9)
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (
            0.45,
            0.42,
            0.36,
            1,
        )
        ground.data.materials.append(mat)
        ground.vs.export = False
    for name in PREVIEW_OBJECTS:
        if name not in sc.objects:
            sc.collection.objects.link(bpy.data.objects[name])
    if not sc.world:
        sc.world = bpy.data.worlds.new("preview_world")
    sc.world.use_nodes = True
    background = sc.world.node_tree.nodes["Background"]
    background.inputs[0].default_value = (0.35, 0.37, 0.4, 1)
    background.inputs[1].default_value = 0.6
    sc.camera = sc.objects["preview_camera"]
    sc.render.engine = "BLENDER_EEVEE"


def render(path: str, eye: Vec3, look_at: Vec3, size: tuple[int, int] = (900, 600)) -> str:
    """Renders from `eye` looking at `look_at` to a PNG.

    A player sees a floor prop from about 64 units up and 60 to 80 away.
    """
    sc = bpy.context.scene
    cam = sc.objects["preview_camera"]
    cam.location = eye
    cam.rotation_euler = (Vector(look_at) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def contact_sheet(paths: Iterable[str], out: str, columns: int = 2) -> str:
    """Tiles equally sized renders into one PNG, left to right then top to bottom."""
    tiles = [surfaces.load_pixels(p, size=None) for p in paths]
    while len(tiles) % columns:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i : i + columns]) for i in range(0, len(tiles), columns)]
    sheet = np.vstack(list(reversed(rows)))  # pixel rows run bottom-up
    img = bpy.data.images.new("contact_sheet", sheet.shape[1], sheet.shape[0])
    img.pixels[:] = sheet.ravel()
    img.filepath_raw = out
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return out


def frame_viewport(object_name: str) -> None:
    """Shows the user `object_name` in Material Preview in their 3D view."""
    window = bpy.context.window_manager.windows[0]
    window.scene = bpy.context.scene
    for area in window.screen.areas:
        if area.type != "VIEW_3D":
            continue
        area.spaces.active.shading.type = "MATERIAL"
        region = next(r for r in area.regions if r.type == "WINDOW")
        for ob in bpy.context.scene.objects:
            ob.select_set(ob.name == object_name)
        bpy.context.view_layer.objects.active = bpy.context.scene.objects[object_name]
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.view3d.view_selected()
