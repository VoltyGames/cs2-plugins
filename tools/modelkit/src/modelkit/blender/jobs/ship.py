"""Puts baked texture sets on their materials, saves the model's .blend and exports its DMX
files. Export needs Blender Source Tools, so the CLI runs this with the user's add-ons."""

import os
from typing import Any

import bpy

from modelkit.blender import export
from modelkit.blender.nodes import show_texture_set
from modelkit.blender.session import relink_images


def main(
    textures: dict[str, dict[str, str]], save: str, export_dir: str, relink_from: str
) -> dict[str, Any]:
    for name, maps in textures.items():
        show_texture_set(bpy.data.materials[name], maps)
    relink_images(os.path.dirname(save), moved_from=relink_from)
    saved = export.save_everything(save)
    exported = [
        path
        for scene in bpy.data.scenes
        if scene.get(export.SETTINGS)
        for path in export.write_dmx(scene.name, export_dir)
    ]
    return {"saved": saved, "exported": exported}
