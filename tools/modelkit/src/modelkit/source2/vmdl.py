"""ModelDoc .vmdl models: writing them and reading back what the audits need."""

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from modelkit.source2.kv3 import Parsed, Value, parse, write

type FilePath = str | os.PathLike[str]
type Node = dict[str, Value]
type Triple = tuple[float, float, float]

HEADER = (
    "<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} "
    "format:modeldoc28:version{fb63b6ca-f435-4aa0-a2c7-c66ddc651dca} -->\n"
)


def write_vmdl(
    path: FilePath,
    meshes: Iterable[tuple[str, str]],
    hulls: Sequence[str] = (),
    animations: Sequence[tuple[str, str, bool]] = (),
    material_groups: dict[str, dict[str, str]] | None = None,
    attachments: Sequence[tuple[str, str, Triple, Triple]] = (),
    surface: str = "metal",
    scale: float = 1.0,
) -> FilePath:
    """Writes a model from `meshes` [(name, dmx)], `hulls` [dmx], `animations`
    [(name, dmx, looping)], `material_groups` {group: {from vmat: to vmat}} (the first is the
    default) and `attachments` [(name, bone, origin, angles)].

    `surface` is the hulls' surface property; "metal_barrel" stops bullets however thin the hull.
    """
    nodes = [
        {"_class": "BoneMarkupList", "children": [], "bone_cull_type": "None"},
        make_list("RenderMeshList", [make_render_mesh(*m) for m in meshes]),
    ]
    if material_groups:
        groups = [make_material_group(i, *g) for i, g in enumerate(material_groups.items())]
        nodes.append(make_list("MaterialGroupList", groups))
    if attachments:
        nodes.append(make_list("AttachmentList", [make_attachment(*a) for a in attachments]))
    if animations:
        nodes.append(make_list("AnimationList", [make_animation(*a) for a in animations]))
    if hulls:
        nodes.append(make_list("PhysicsShapeList", [make_hull(h, surface) for h in hulls]))
    if scale != 1.0:
        nodes.append(make_list("ModelModifierList", [make_scale(scale)]))
    root = {"rootNode": {"_class": "RootNode", "children": nodes}}
    with open(path, "w", newline="\n") as f:
        f.write(HEADER + write(root) + "\n")
    return path


def make_list(cls: str, children: list[Node]) -> Node:
    return {"_class": cls, "children": children}


def make_render_mesh(name: str, dmx: str) -> Node:
    return {"_class": "RenderMeshFile", "name": name, "filename": dmx}


def make_material_group(index: int, name: str, remaps: dict[str, str]) -> Node:
    pairs = [{"_class": "BaseMaterialRemap", "from": a, "to": b} for a, b in remaps.items()]
    kind = "DefaultMaterialGroup" if index == 0 else "MaterialGroup"
    return {"_class": kind, "name": name, "remaps": pairs}


def make_attachment(name: str, bone: str, origin: Triple, angles: Triple) -> Node:
    return {
        "_class": "Attachment",
        "name": name,
        "ignore_rotation": False,
        "parent_bone": bone,
        "relative_origin": list(origin),
        "relative_angles": list(angles),
        "weight": 1.0,
    }


def make_animation(name: str, dmx: str, looping: bool) -> Node:
    return {
        "_class": "AnimFile",
        "name": name,
        "source_filename": dmx,
        "fade_in_time": 0.0,
        "fade_out_time": 0.0 if looping else 0.1,
        "looping": looping,
        "delta": False,
        "worldSpace": False,
        "hidden": False,
    }


def make_hull(dmx: str, surface: str) -> Node:
    return {
        "_class": "PhysicsHullFile",
        "filename": dmx,
        "parent_bone": "",
        "surface_prop": surface,
        "collision_tags": "",
        "name": "",
    }


def make_scale(scale: float) -> Node:
    return {
        "_class": "ModelModifier_ScaleAndMirror",
        "scale": float(scale),
        "mirror_x": False,
        "mirror_y": False,
        "mirror_z": False,
        "flip_bone_forward": False,
        "swap_left_and_right_bones": False,
    }


def find_nodes(tree: Parsed, cls: str) -> list[dict[str, Parsed]]:
    """Every node of class `cls` in a parsed ModelDoc tree."""
    found, pending = [], [tree]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            if node.get("_class") == cls:
                found.append(node)
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    return found


@dataclass(frozen=True)
class ModelInfo:
    meshes: list[str]
    """Render mesh DMX paths."""
    scale: float
    swapped: set[str]
    """Material paths a material group remaps, such as team colours."""


def read_vmdl(path: FilePath) -> ModelInfo:
    with open(path, encoding="utf-8") as f:
        tree = parse(f.read())
    scales = find_nodes(tree, "ModelModifier_ScaleAndMirror")
    remaps = find_nodes(tree, "BaseMaterialRemap")
    return ModelInfo(
        meshes=[node["filename"] for node in find_nodes(tree, "RenderMeshFile")],
        scale=float(scales[0].get("scale", 1.0)) if scales else 1.0,
        swapped={node[end] for node in remaps for end in ("from", "to")},
    )
