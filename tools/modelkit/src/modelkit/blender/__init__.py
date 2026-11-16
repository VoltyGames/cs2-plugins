"""Blender helpers for Source 2 props. Load inside Blender, through execute_blender_code:

    import sys
    sys.path.insert(0, r"<repo>/tools/modelkit/src")
    import modelkit.blender
    modelkit.blender.reload()
    from modelkit.blender import session, surfaces, shapes, objects, rig, preview, export
    from modelkit.source2 import modeldoc

One Blender unit is one Source unit; +X is the model's forward, +Z is up.
"""

import importlib
import sys

# Dependencies first, so a reload picks up edits in the modules the others import.
MODULES = (
    "modelkit.source2.kv3",
    "modelkit.source2.modeldoc",
    "modelkit.blender.measure",
    "modelkit.blender.session",
    "modelkit.blender.surfaces",
    "modelkit.blender.shapes",
    "modelkit.blender.objects",
    "modelkit.blender.rig",
    "modelkit.blender.preview",
    "modelkit.blender.export",
)


def reload() -> None:
    """Picks up edits to the kit without restarting Blender."""
    for name in MODULES:
        if module := sys.modules.get(name):
            importlib.reload(module)
