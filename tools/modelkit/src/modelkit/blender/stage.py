"""A throwaway scene for background renders: parts gathered from their scenes, posed at their
idle, lit, with a camera that can circle them. `remove` leaves the file as it was."""

import math
import re
from collections.abc import Iterable, Sequence

import bpy
from mathutils import Vector

# Objects that never render: collision hulls and the live session's preview rig.
SKIPPED = re.compile("hull|phys|collision|preview", re.IGNORECASE)
PREFIX = "modelkit_stage"


def find_idle(scene_name: str) -> bpy.types.Action | None:
    """The scene's own idle (`<scene>_idle`), else the file's first idle."""
    idles = [a for a in bpy.data.actions if re.search(r"(^|_)idle$", a.name)]
    own = next((a for a in idles if a.name == f"{scene_name}_idle"), None)
    return own or next(iter(idles), None)


def hold(ob: bpy.types.Object, action: bpy.types.Action, frame: float) -> None:
    """Poses `ob` at `frame` of `action` whatever the scene's frame, with a one-frame NLA strip,
    so parts in one stage can each show a different moment."""
    ob.animation_data_create()
    ob.animation_data.action = None
    track = ob.animation_data.nla_tracks.new()
    track.name = PREFIX
    strip = track.strips.new(action.name, 0, action)
    if action.slots:
        strip.action_slot = action.slots[0]
    strip.action_frame_start, strip.action_frame_end = frame, frame + 1
    strip.frame_start, strip.frame_end = -1000, 1000
    strip.extrapolation = "HOLD"


def gather(
    scene_names: Iterable[str],
    at: dict[str, Sequence[float]] | None = None,
    poses: dict[str, tuple[str, float]] | None = None,
) -> bpy.types.Scene:
    """A new scene holding the named scenes' armatures and meshes; `at` moves a part's root.
    Each part holds its scene's idle at frame 0, or the action and frame `poses` names."""
    at, poses = at or {}, poses or {}
    stage = bpy.data.scenes.new(PREFIX)
    for name in scene_names:
        if name in poses:
            action, frame = bpy.data.actions[poses[name][0]], poses[name][1]
        else:
            action, frame = find_idle(name), 0.0
        for ob in bpy.data.scenes[name].objects:
            if ob.type in {"MESH", "ARMATURE"} and not SKIPPED.search(ob.name):
                if ob.parent is None and name in at:
                    ob.location = Vector(at[name])
                if ob.name not in stage.collection.objects:
                    stage.collection.objects.link(ob)
                if ob.type == "ARMATURE" and action:
                    hold(ob, action, frame)
    stage.frame_set(0)
    return stage


def points(stage: bpy.types.Scene) -> list[Vector]:
    """Every vertex of the parts, in world space, as posed."""
    # The stage's own graph: the context's belongs to the file's active scene.
    graph = stage.view_layers[0].depsgraph
    graph.update()
    found = []
    for ob in stage.objects:
        if ob.type == "MESH" and not ob.name.startswith(PREFIX):
            evaluated = ob.evaluated_get(graph)
            mesh = evaluated.to_mesh()
            found += [evaluated.matrix_world @ v.co for v in mesh.vertices]
            evaluated.to_mesh_clear()
    return found


def bounds(stage: bpy.types.Scene) -> tuple[Vector, Vector]:
    found = points(stage)
    lo = Vector(min(p[i] for p in found) for i in range(3))
    hi = Vector(max(p[i] for p in found) for i in range(3))
    return lo, hi


def light(stage: bpy.types.Scene, size: tuple[int, int] = (1600, 1000)) -> bpy.types.Object:
    """Adds a sun, a sky, a ground and a camera; returns the camera."""
    lo, hi = bounds(stage)
    reach = (hi - lo).length * 3
    center = (lo + hi) / 2
    camera = bpy.data.objects.new(f"{PREFIX}_camera", bpy.data.cameras.new(f"{PREFIX}_camera"))
    camera.data.lens = 35
    sun = bpy.data.objects.new(f"{PREFIX}_sun", bpy.data.lights.new(f"{PREFIX}_sun", "SUN"))
    sun.data.energy, sun.data.color = 4.0, (1.0, 0.95, 0.85)
    sun.data.angle = math.radians(2)
    sun.rotation_euler = (math.radians(50), 0, math.radians(35))
    mesh = bpy.data.meshes.new(f"{PREFIX}_ground")
    corners = [(-reach, -reach, 0), (reach, -reach, 0), (reach, reach, 0), (-reach, reach, 0)]
    mesh.from_pydata(corners, [], [(0, 1, 2, 3)])
    ground = bpy.data.objects.new(f"{PREFIX}_ground", mesh)
    ground.location = (center.x, center.y, lo.z)
    material = bpy.data.materials.new(f"{PREFIX}_ground")
    material.use_nodes = True
    shader = material.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = (0.42, 0.36, 0.28, 1)
    shader.inputs["Roughness"].default_value = 0.95
    mesh.materials.append(material)
    for ob in (camera, sun, ground):
        stage.collection.objects.link(ob)
    stage.camera = camera
    world = bpy.data.worlds.new(f"{PREFIX}_world")
    world.use_nodes = True
    background = world.node_tree.nodes["Background"]
    background.inputs[0].default_value = (0.55, 0.62, 0.72, 1)
    background.inputs[1].default_value = 0.9
    stage.world = world
    stage.render.engine = "BLENDER_EEVEE"
    stage.render.resolution_x, stage.render.resolution_y = size
    stage.view_settings.view_transform = "AgX"
    return camera


def aim(
    stage: bpy.types.Scene, direction: tuple[float, float, float] | Vector, distance: float = 1.7
) -> None:
    """Points the camera at the parts from `direction`, `distance` times their size away."""
    lo, hi = bounds(stage)
    center = (lo + hi) / 2
    camera = stage.camera
    camera.location = center + Vector(direction).normalized() * (hi - lo).length * distance
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()


def render(stage: bpy.types.Scene, path: str) -> str:
    stage.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=stage.name)
    return path


def remove(stage: bpy.types.Scene) -> None:
    """Deletes the stage and everything it added; the gathered parts stay in their scenes."""
    for ob in stage.objects:
        if ob.animation_data:
            for track in [t for t in ob.animation_data.nla_tracks if t.name == PREFIX]:
                ob.animation_data.nla_tracks.remove(track)
    for ob in list(stage.objects):
        if ob.name.startswith(PREFIX):
            bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.scenes.remove(stage)
    for collection in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in [b for b in collection if b.name.startswith(PREFIX)]:
            collection.remove(block)
    for world in [w for w in bpy.data.worlds if w.name.startswith(PREFIX)]:
        bpy.data.worlds.remove(world)
