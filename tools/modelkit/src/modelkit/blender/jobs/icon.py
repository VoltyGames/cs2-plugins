"""A store card's subject: the model posed at its idle, a warm key and a cool rim light, the
camera fitted to its bounds from a three-quarter view. The background is transparent but for the
model's floor shadow; `modelkit.icons` paints the studio behind it."""

from collections.abc import Iterable, Sequence
from typing import Any

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

from modelkit.blender import bake, stage

THREE_QUARTER = (1.0, -1.0, 0.24)
# The share of the card's width and height the model may fill, and where its middle sits
# vertically, a little low so the floor shows under it.
# Glow is turned down for the card: at full strength a lamp or strip blooms into a pale blob
# at card size. Only the render's in-memory copy changes.
GLOW = 0.35
FILL = (0.78, 0.72)
RISE = 0.47
# Darkens the concrete to the old cards' charcoal floor.
FLOOR_TINT = (0.2, 0.2, 0.215, 1.0)


def area_light(
    scene: bpy.types.Scene,
    name: str,
    at: Vector,
    target: Vector,
    power: float,
    size: float,
    color: tuple[float, float, float],
    shadow: bool = True,
    only: bpy.types.Collection | None = None,
) -> None:
    """An area light aimed at `target`; `only` limits what it lights, by light linking."""
    light = bpy.data.lights.new(f"{stage.PREFIX}_{name}", "AREA")
    light.energy, light.color, light.size = power, color, size
    light.use_shadow = shadow
    ob = bpy.data.objects.new(f"{stage.PREFIX}_{name}", light)
    ob.location = at
    ob.rotation_euler = (target - at).to_track_quat("-Z", "Y").to_euler()
    if only is not None:
        ob.light_linking.receiver_collection = only
    scene.collection.objects.link(ob)


def dim_glow(scene: bpy.types.Scene) -> None:
    lit = {slot.material for ob in scene.objects if ob.type == "MESH" for slot in ob.material_slots}
    for material in filter(None, lit):
        for node in material.node_tree.nodes if material.node_tree else ():
            if node.type == "BSDF_PRINCIPLED":
                node.inputs["Emission Strength"].default_value *= GLOW


def floor(scene: bpy.types.Scene, lo: Vector, hi: Vector, maps: dict[str, str]) -> None:
    """Dark concrete under the model that takes its shadow and a faint sheen, fading out with
    distance so the painted backdrop shows through where it ends."""
    span = (hi - lo).length
    center = (lo + hi) / 2
    reach = span * 4
    mesh = bpy.data.meshes.new(f"{stage.PREFIX}_floor")
    corners = [(-reach, -reach, 0), (reach, -reach, 0), (reach, reach, 0), (-reach, reach, 0)]
    mesh.from_pydata(corners, [], [(0, 1, 2, 3)])
    material = bpy.data.materials.new(f"{stage.PREFIX}_floor")
    material.use_nodes = True
    n = bake.Nodes(material)
    coords = n.add("ShaderNodeTexCoord")
    tiling = n.add("ShaderNodeMapping")
    tiling.inputs["Scale"].default_value = [1.0 / (span * 0.45)] * 3
    n.feed(tiling, "Vector", coords.outputs["Object"])

    def texture(role: str, data: bool) -> bpy.types.NodeSocket:
        node = n.add("ShaderNodeTexImage")
        node.image = bake.load_image(maps[role], data)
        n.feed(node, "Vector", tiling.outputs["Vector"])
        return node.outputs["Color"]

    color = n.mix("RGBA", 1.0, texture("color", False), FLOOR_TINT, blend="MULTIPLY")
    surface = n.add("ShaderNodeBsdfPrincipled")
    n.feed(surface, "Base Color", color)
    sheen = n.math("MULTIPLY", texture("roughness", True), 0.2)
    n.feed(surface, "Roughness", n.math("ADD", sheen, 0.72))
    normal = n.add("ShaderNodeNormalMap")
    normal.inputs["Strength"].default_value = 0.6
    n.feed(normal, "Color", texture("normal", True))
    n.feed(surface, "Normal", normal.outputs["Normal"])
    distance = n.add("ShaderNodeVectorMath", operation="LENGTH")
    n.feed(distance, 0, coords.outputs["Object"])
    fade = n.math("POWER", n.remap(distance.outputs["Value"], span * 0.2, span * 1.3), 0.8)
    clear = n.add("ShaderNodeBsdfTransparent")
    blend = n.add("ShaderNodeMixShader")
    n.feed(blend, "Fac", fade)
    n.feed(blend, 1, surface.outputs["BSDF"])
    n.feed(blend, 2, clear.outputs["BSDF"])
    output = n.add("ShaderNodeOutputMaterial")
    n.feed(output, "Surface", blend.outputs["Shader"])
    mesh.materials.append(material)
    ob = bpy.data.objects.new(f"{stage.PREFIX}_floor", mesh)
    ob.location = (center.x, center.y, lo.z)
    scene.collection.objects.link(ob)


def frame(
    scene: bpy.types.Scene, model: list[Vector], direction: Sequence[float], lens: float
) -> None:
    """Aims the camera along `direction`, then sets its distance and lens shift from the model's
    projected vertices, so the model fills FILL of the card and sits at its centre."""
    lo = Vector(min(p[i] for p in model) for i in range(3))
    hi = Vector(max(p[i] for p in model) for i in range(3))
    center = (lo + hi) / 2
    name = f"{stage.PREFIX}_camera"
    camera = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    camera.data.lens = lens
    # The default 1000-unit far clip cuts a model as wide as the net down to its nearest post.
    camera.data.clip_end = (hi - lo).length * 100
    scene.collection.objects.link(camera)
    scene.camera = camera
    offset = Vector(direction).normalized()
    camera.rotation_euler = (-offset).to_track_quat("-Z", "Y").to_euler()
    aspect = scene.render.resolution_y / scene.render.resolution_x
    sample = model[:: max(1, len(model) // 4000)]

    def extent(distance: float) -> tuple[float, float, float, float] | None:
        """The model's projected left, right, bottom and top from `distance`, or None when
        part of it is behind the camera."""
        camera.location = center + offset * distance
        scene.view_layers[0].update()
        projected = [world_to_camera_view(scene, camera, p) for p in sample]
        if min(p.z for p in projected) <= camera.data.clip_start:
            return None
        xs, ys = [p.x for p in projected], [p.y for p in projected]
        return min(xs), max(xs), min(ys), max(ys)

    def fits(distance: float) -> bool:
        bounds = extent(distance)
        return bounds is not None and (
            bounds[1] - bounds[0] <= FILL[0] and bounds[3] - bounds[2] <= FILL[1]
        )

    # Bisect for the nearest distance that fits: perspective makes a scaled guess overshoot
    # on wide, flat models until near parts pass behind the camera.
    near, far = 0.0, (hi - lo).length
    while not fits(far):
        near, far = far, far * 2
    for _ in range(24):
        middle = (near + far) / 2
        near, far = (near, middle) if fits(middle) else (middle, far)
    left, right, bottom, top = extent(far)
    # Shift is in widths on a landscape card; heights scale by the aspect.
    camera.data.shift_x = (left + right) / 2 - 0.5
    camera.data.shift_y = ((bottom + top) / 2 - RISE) * aspect


def main(
    path: str,
    floor_maps: dict[str, str],
    skip: Iterable[str] = (),
    at: dict[str, Sequence[float]] | None = None,
    pose: dict[str, tuple[str, float]] | None = None,
    view: Sequence[float] = THREE_QUARTER,
    size: tuple[int, int] = (768, 512),
    lens: float = 55.0,
    samples: int = 128,
) -> dict[str, Any]:
    names = [sc.name for sc in bpy.data.scenes if sc.name not in set(skip)]
    scene = stage.gather(names, at, pose)
    parts = sorted(ob.name for ob in scene.objects if ob.type == "MESH")
    model_points = stage.points(scene)
    scene.render.resolution_x, scene.render.resolution_y = size
    lo, hi = stage.bounds(scene)
    center, span = (lo + hi) / 2, (hi - lo).length
    model = bpy.data.collections.new(f"{stage.PREFIX}_model")
    for ob in scene.objects:
        if ob.type == "MESH":
            model.objects.link(ob)
    dim_glow(scene)
    floor(scene, lo, hi, floor_maps)
    # Lights sit relative to the view, so every card is lit alike: a broad key in front, above
    # and to the camera's right, the fill low on its left, the rim behind the model.
    toward = Vector((view[0], view[1], 0)).normalized()
    right = Vector((-toward.y, toward.x, 0))
    up = Vector((0, 0, 1))

    def around(forward: float, side: float, height: float) -> Vector:
        return center + (toward * forward + right * side + up * height) * span

    area_light(
        scene,
        "key",
        around(1.4, 0.5, 0.7),
        center,
        power=22 * span**2,
        size=span * 1.6,
        color=(1.0, 0.93, 0.82),
    )
    # Only the key casts a shadow and lights the floor: the rim, behind the model, would throw
    # a shadow and a pool of light toward the camera.
    area_light(
        scene,
        "rim",
        around(-1.1, -0.7, 0.9),
        center,
        power=50 * span**2,
        size=span * 0.5,
        color=(0.78, 0.86, 1.0),
        shadow=False,
        only=model,
    )
    area_light(
        scene,
        "fill",
        around(1.3, -0.9, 0.3),
        center,
        power=5 * span**2,
        size=span * 1.2,
        color=(0.9, 0.92, 1.0),
        shadow=False,
        only=model,
    )
    # A dim world lights what the key misses; the transparent film keeps it out of the picture.
    world = bpy.data.worlds.new(f"{stage.PREFIX}_world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.056, 1)
    scene.world = world
    frame(scene, model_points, view, lens)
    device = bake.use_fastest_device(scene)
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    stage.render(scene, path)
    return {"path": path, "parts": parts, "device": device}
