"""The skeleton and its actions."""

import math
from collections.abc import Iterable, Sequence

import bpy
from mathutils import Euler, Matrix, Vector

type Vec3 = tuple[float, float, float] | Vector
type Key = tuple[float, Vec3, tuple[float, float, float]]


def skeleton(
    name: str,
    bones: Iterable[tuple[str, Vec3, Vec3, str | None]],
    meshes: Iterable[bpy.types.Object],
) -> bpy.types.Object:
    """Creates the armature `name` and skins `meshes` to it.

    `bones` is a list of (name, head, tail, parent or None), parents first. A mesh's vertex
    groups name the bones it follows.
    """
    data = bpy.data.armatures.get(name) or bpy.data.armatures.new(name)
    arm = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in list(data.edit_bones):
        data.edit_bones.remove(bone)
    for bone_name, head, tail, parent in bones:
        bone = data.edit_bones.new(bone_name)
        bone.head, bone.tail = head, tail
        if parent:
            bone.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    for ob in meshes:
        ob.parent = arm
        ob.modifiers.new("skeleton", "ARMATURE").object = arm
    data.vs.action_selection = "CURRENT"
    return arm


def animate(arm: bpy.types.Object, name: str, tracks: dict[str, Iterable[Key]]) -> bpy.types.Action:
    """Records the action `name` on `arm`, replacing one of that name, and returns it.

    `tracks` maps a bone to keys (frame, (dx, dy, dz), (rx, ry, rz) degrees): a move and a turn
    about the bone's head, in model axes, relative to rest and to the parent bone. Untracked bones
    stay at rest. A looping action ends on the key it starts with.
    """
    if action := bpy.data.actions.get(name):
        bpy.data.actions.remove(action)
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    arm.animation_data_create()
    arm.animation_data.action = action
    for bone_name, keys in tracks.items():
        pose = arm.pose.bones[bone_name]
        pose.rotation_mode = "QUATERNION"
        rest = pose.bone.matrix_local
        head = rest.to_translation()
        for frame, move, turn in keys:
            rotation = Euler([math.radians(v) for v in turn]).to_matrix().to_4x4()
            delta = Matrix.Translation(Vector(move) + head) @ rotation @ Matrix.Translation(-head)
            pose.matrix_basis = rest.inverted() @ delta @ rest
            for path in ("location", "rotation_quaternion", "scale"):
                pose.keyframe_insert(path, frame=frame)
    return action


def eased(keys: Sequence[tuple[int, float]]) -> list[tuple[int, float]]:
    """(frame, value) for each frame through `keys`, never overshooting them (monotone cubic)."""
    frames, values = zip(*keys)
    steps = [b - a for a, b in zip(frames, frames[1:])]
    slopes = [(b - a) / h for a, b, h in zip(values, values[1:], steps)]
    tangents = [0.0] * len(keys)
    for i in range(1, len(keys) - 1):
        if slopes[i - 1] * slopes[i] > 0:
            w1, w2 = 2 * steps[i] + steps[i - 1], steps[i] + 2 * steps[i - 1]
            tangents[i] = (w1 + w2) / (w1 / slopes[i - 1] + w2 / slopes[i])
    samples = []
    for i, h in enumerate(steps):
        a, b = values[i], values[i + 1]
        ma, mb = tangents[i] * h, tangents[i + 1] * h
        for frame in range(frames[i], frames[i + 1]):
            t = (frame - frames[i]) / h
            ease = (2 * t**3 - 3 * t**2 + 1) * a + (3 * t**2 - 2 * t**3) * b
            samples.append((frame, ease + (t**3 - 2 * t**2 + t) * ma + (t**3 - t**2) * mb))
    samples.append((frames[-1], values[-1]))
    return samples


def show(arm: bpy.types.Object, action: str, frame: int = 0) -> None:
    """Poses `arm` at `frame` of `action`, with the timeline spanning just that action."""
    chosen = bpy.data.actions[action]
    arm.animation_data.action = chosen
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = (int(f) for f in chosen.frame_range)
    sc.frame_set(frame)
