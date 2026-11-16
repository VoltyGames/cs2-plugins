"""Baking WornMaterial channels to PNGs with Cycles."""

import bpy

from modelkit.blender.atlas import ATLAS_UV, SelectOnly
from modelkit.blender.wear import CHANNELS

SAMPLES = 32
MARGIN = 12


def use_fastest_device() -> str:
    """Picks the first GPU backend that finds a device, else the CPU; returns which."""
    preferences = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            preferences.compute_device_type = backend
        except TypeError:
            continue
        preferences.get_devices()
        if any(d.type != "CPU" for d in preferences.devices):
            for device in preferences.devices:
                device.use = device.type != "CPU"
            return backend
    return "CPU"


def bake_texture_set(copy: bpy.types.Object, size: int, folder: str, device: str) -> dict[str, str]:
    """Bakes each channel and the tangent normal of `copy` into RGBA PNGs in `folder`, pixels no
    face covers left transparent; returns the files by channel."""
    scene = copy.users_scene[0]
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU" if device == "CPU" else "GPU"
    scene.cycles.samples = SAMPLES
    scene.render.bake.margin = MARGIN
    scene.render.bake.margin_type = "EXTEND"
    scene.render.bake.use_clear = False
    # Only finishes bake; the slots of dropped faces keep their old material.
    materials = [m for m in copy.data.materials if m and "emit_color" in m.node_tree.nodes]
    # No AO pass: the game shadows the model itself, and baked AO darkened panels in patches.
    files = {}
    for channel in (*CHANNELS, "normal"):
        image = bpy.data.images.new(f"bake_{channel}", size, size, alpha=True)
        image.generated_color = (0, 0, 0, 0)
        image.colorspace_settings.name = "sRGB" if channel == "color" else "Non-Color"
        for material in materials:
            nodes = material.node_tree.nodes
            nodes["bake_target"].image = image
            nodes.active = nodes["bake_target"]
            source = nodes["surface"] if channel == "normal" else nodes[f"emit_{channel}"]
            material.node_tree.links.new(source.outputs[0], nodes["output"].inputs["Surface"])
        with SelectOnly(copy):
            if channel == "normal":
                bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", uv_layer=ATLAS_UV)
            else:
                bpy.ops.object.bake(type="EMIT", uv_layer=ATLAS_UV)
        files[channel] = f"{folder}/{copy.name}_{channel}.png"
        image.filepath_raw = files[channel]
        image.file_format = "PNG"
        image.save()
        bpy.data.images.remove(image)
    return files
