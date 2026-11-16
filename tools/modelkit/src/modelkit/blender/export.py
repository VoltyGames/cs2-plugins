"""Exporting the scene: DMX files for the compiler, and the .blend for later edits."""

import os
import re
import shutil
import tempfile
from collections.abc import Iterable
from typing import Any

import bpy

from modelkit.blender import rig

# The scene property holding what remember() stored.
SETTINGS = "modelkit"


def remember(
    scene_name: str,
    model: str | None = None,
    armature: str | None = None,
    actions: Iterable[str] = (),
    files: dict[str, str] | None = None,
) -> None:
    """Stores how the scene exports, so a later session can re-export it from the .blend alone.

    `model` prefixes the animation files (`<model>_<action>.dmx`); without it each takes its
    action's name. `actions` list the actions, the one to pose after export first; `files` renames
    mesh files ({object: stem}), which otherwise take the object's name.
    """
    bpy.data.scenes[scene_name][SETTINGS] = {
        "model": model or "",
        "armature": armature or "",
        "actions": list(actions),
        "files": dict(files or {}),
    }


def read_settings(scene_name: str) -> dict[str, Any]:
    stored = bpy.data.scenes[scene_name].get(SETTINGS)
    if stored is None:
        raise ValueError(f"scene {scene_name} has no export settings; call remember() first")
    return stored.to_dict()


def write_dmx(scene_name: str, out_dir: str) -> list[str]:
    """Exports the scene's meshes and each remembered action as DMX into `out_dir`.

    Blender Source Tools exports only the current action and leaves object references stale,
    so everything is looked up by name on each pass.
    """
    kept = read_settings(scene_name)
    armature, actions, files = kept["armature"], kept["actions"], kept["files"]
    renamed = [
        m.name
        for ob in bpy.data.scenes[scene_name].objects
        if ob.type == "MESH" and ob.vs.export
        for m in ob.data.materials
        if m and re.search(r"\.\d{3}$", m.name)
    ]
    if renamed:
        raise ValueError(f"materials renamed by Blender would reach the DMX: {renamed}")
    staging = tempfile.mkdtemp(prefix="modelkit_")
    written = []
    try:
        for action in actions or [None]:
            sc = bpy.data.scenes[scene_name]
            bpy.context.window.scene = sc
            sc.vs.export_path = staging
            if armature and action:
                arm = bpy.data.objects[armature]
                arm.data.vs.action_selection = "CURRENT"
                arm.animation_data.action = bpy.data.actions[action]
            sc.frame_set(0)
            bpy.ops.export_scene.smd(export_scene=True)
            if armature and action:
                stem = f"{kept['model']}_{action}" if kept["model"] else action
                target = os.path.join(out_dir, f"{stem}.dmx")
                shutil.copy(os.path.join(staging, "anims", f"{armature}.dmx"), target)
                written.append(target)
        for name in os.listdir(staging):
            stem, ext = os.path.splitext(name)
            if ext == ".dmx" and stem != armature:
                target = os.path.join(out_dir, files.get(stem, stem) + ".dmx")
                shutil.copy(os.path.join(staging, name), target)
                written.append(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        bpy.data.scenes[scene_name].vs.export_path = "//"
        if armature and actions:
            rig.show(bpy.data.objects[armature], actions[0])
    return sorted(written)


def save_blend(scenes: str | Iterable[str], path: str) -> str:
    """Writes `scenes`, one name or a list, and their remembered actions to `path`, image paths
    relative. Other scenes, such as imported references, stay out.

    A model folder keeps one .blend with a scene per part, so the save must include every scene
    the file already holds; otherwise it would drop them.
    """
    names = [scenes] if isinstance(scenes, str) else list(scenes)
    if os.path.exists(path):
        with bpy.data.libraries.load(path) as (held, _):
            dropped = sorted(set(held.scenes) - set(names))
        if dropped:
            raise ValueError(f"{path} also holds {dropped}; open them and save them together")
    blocks = set()
    for name in names:
        blocks.add(bpy.data.scenes[name])
        for action in read_settings(name)["actions"]:
            blocks.add(bpy.data.actions[action])
    bpy.data.libraries.write(path, blocks, path_remap="RELATIVE_ALL", fake_user=True, compress=True)
    return path


def save_everything(path: str, remap: str = "RELATIVE_ALL") -> str:
    """Writes every scene and action to `path`, for headless jobs that own the whole file."""
    blocks = set(bpy.data.scenes) | set(bpy.data.actions)
    bpy.data.libraries.write(path, blocks, path_remap=remap, fake_user=True, compress=True)
    return path
