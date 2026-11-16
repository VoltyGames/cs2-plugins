"""Puts finished texture sets on a baked model's materials, then renders it, saves it as the
model's .blend and exports its DMX files, as asked. Export needs Blender Source Tools, so the CLI
runs this with the user's add-ons."""

import os
from typing import Any

import bpy

from modelkit.blender import export, stage

# Three quarters from the front left, the back right, and from above.
VIEWS = ((1.0, -0.85, 0.38), (-1.0, 0.85, 0.3), (0.4, -0.3, 1.2))


def show_textures(material: bpy.types.Material, maps: dict[str, str]) -> None:
    """A preview of the baked set: Blender shows it, the game reads the .vmat."""
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])

    def image(role: str, data: bool) -> bpy.types.NodeSocket:
        node = nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(maps[role], check_existing=True)
        node.image.colorspace_settings.name = "Non-Color" if data else "sRGB"
        return node.outputs["Color"]

    links.new(image("color", False), shader.inputs["Base Color"])
    links.new(image("roughness", True), shader.inputs["Roughness"])
    links.new(image("metalness", True), shader.inputs["Metallic"])
    normal = nodes.new("ShaderNodeNormalMap")
    links.new(image("normal", True), normal.inputs["Color"])
    links.new(normal.outputs["Normal"], shader.inputs["Normal"])


def render_views(folder: str, at: dict[str, list[float]] | None) -> list[str]:
    scene = stage.gather([s.name for s in bpy.data.scenes], at)
    stage.light(scene, (1600, 1000))
    paths = []
    for index, direction in enumerate(VIEWS):
        stage.aim(scene, direction, distance=1.2 if index < 2 else 1.4)
        paths.append(stage.render(scene, os.path.join(folder, f"view_{index}.png")))
    stage.remove(scene)
    return paths


def relink(old: str, new: str) -> None:
    """Points images loaded from `old`, an extracted source folder, at the same names in `new`."""
    old = os.path.normcase(os.path.abspath(old))
    for image in bpy.data.images:
        path = bpy.path.abspath(image.filepath)
        if path and os.path.normcase(os.path.abspath(path)).startswith(old):
            image.filepath = os.path.join(new, os.path.basename(path))


def main(
    textures: dict[str, dict[str, str]],
    render_dir: str | None = None,
    at: dict[str, list[float]] | None = None,
    save: str | None = None,
    export_dir: str | None = None,
    relink_from: str | None = None,
) -> dict[str, Any]:
    for name, maps in textures.items():
        show_textures(bpy.data.materials[name], maps)
    result: dict[str, Any] = {}
    if render_dir:
        result["renders"] = render_views(render_dir, at)
    if save and relink_from:
        relink(relink_from, os.path.dirname(save))
    if save:
        blocks = set(bpy.data.scenes) | set(bpy.data.actions)
        bpy.data.libraries.write(
            save, blocks, path_remap="RELATIVE_ALL", fake_user=True, compress=True
        )
        result["saved"] = save
    if export_dir:
        result["exported"] = [
            path
            for scene in bpy.data.scenes
            if scene.get(export.SETTINGS)
            for path in export.write_dmx(scene.name, export_dir)
        ]
    return result
