"""The files the compiler reads: .vmat materials, ModelDoc .vmdl models and .vpcf particle
systems. Needs no Blender."""

import os
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from modelkit.source2.kv3 import Parsed, Resource, Value, parse, write

type FilePath = str | os.PathLike[str]
type Node = dict[str, Value]
type Triple = tuple[float, float, float]

HEADER = (
    "<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} "
    "format:modeldoc28:version{fb63b6ca-f435-4aa0-a2c7-c66ddc651dca} -->\n"
)
PARTICLE_HEADER = (
    "<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} "
    "format:vpcf66:version{dd571be4-586e-4f41-8b2d-5bbc969e1c53} -->\n"
)


def write_vmat(
    path: FilePath,
    folder: str,
    color: str,
    rough: str,
    normal: str | None = None,
    metalness: float = 0.6,
    roughness: float = 0.55,
    glow_mask: str | None = None,
    glow: float = 1.0,
    opacity: float | None = None,
    cutout: str | None = None,
) -> FilePath:
    """Writes a csgo_complex material; texture names are files in `folder`, e.g. "models/x/y/".

    `rough` is the addon path of a flat white roughness texture, scaled by `roughness`.
    With `glow_mask` the material glows at `glow` times its colour where the mask is white.
    With `opacity` it is see-through, such as glass, and casts no shadow.
    With `cutout`, a mask texture, it has holes where the mask is black and shows both faces,
    such as a net or a fence.
    """
    keys = [("shader", "csgo_complex.vfx")]
    if glow_mask:
        keys.append(("F_SELF_ILLUM", "1"))
    if opacity is not None:
        keys += [("F_TRANSLUCENT", "1"), ("F_DO_NOT_CAST_SHADOWS", "1")]
    if cutout:
        keys += [("F_ALPHA_TEST", "1"), ("F_RENDER_BACKFACES", "1")]
    keys += [("g_flMetalness", f"{metalness:g}"), ("g_flRoughnessScaleFactor", f"{roughness:g}")]
    if glow_mask:
        keys.append(("g_flSelfIllumScale", f"{glow:g}"))
    if opacity is not None:
        keys += [
            ("g_flOpacityScale", f"{opacity:g}"),
            ("TextureTranslucency", "[1.000000 1.000000 1.000000 0.000000]"),
        ]
    if cutout:
        keys += [("g_flAlphaTestReference", "0.5"), ("TextureTranslucency", folder + cutout)]
    keys += [
        ("g_vColorTint", "[1.000000 1.000000 1.000000 0.000000]"),
        ("TextureAmbientOcclusion", "materials/default/default_ao.tga"),
        ("TextureColor", folder + color),
        ("TextureNormal", folder + normal if normal else "materials/default/default_normal.tga"),
        ("TextureRoughness", rough),
    ]
    if glow_mask:
        keys.append(("TextureSelfIllumMask", folder + glow_mask))
    return write_layer(path, keys)


def write_baked_vmat(path: FilePath, folder: str, stem: str) -> FilePath:
    """Writes a csgo_complex material over a baked texture set in `folder`: <stem>_color,
    _normal, _rough and _metal PNGs; occlusion is left to the game's own shadows."""
    keys = [
        ("shader", "csgo_complex.vfx"),
        ("F_METALNESS_TEXTURE", "1"),
        ("g_vColorTint", "[1.000000 1.000000 1.000000 0.000000]"),
        ("TextureAmbientOcclusion", "materials/default/default_ao.tga"),
        ("TextureColor", f"{folder}{stem}_color.png"),
        ("TextureMetalness", f"{folder}{stem}_metal.png"),
        ("TextureNormal", f"{folder}{stem}_normal.png"),
        ("TextureRoughness", f"{folder}{stem}_rough.png"),
    ]
    return write_layer(path, keys)


def write_layer(path: FilePath, keys: list[tuple[str, str]]) -> FilePath:
    body = "".join(f'\t"{k}"\t"{v}"\n' for k, v in keys)
    with open(path, "w", newline="\n") as f:
        f.write(f'"Layer0"\n{{\n{body}}}\n')
    return path


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
    """Writes a ModelDoc .vmdl.

    `meshes`: [(name, dmx)]. `hulls`: [dmx]. `animations`: [(name, dmx, looping)]; a prop plays
    none until an input starts one. `material_groups`: {group: {from vmat: to vmat}}, the first
    being the default. `attachments`: [(name, bone, (x, y, z), (pitch, yaw, roll))].
    `surface` is the hulls' surface property; "metal_barrel" stops bullets however thin the hull.
    `scale` resizes the whole model: meshes, hulls and animations.
    """
    nodes = [
        {"_class": "BoneMarkupList", "children": [], "bone_cull_type": "None"},
        listing("RenderMeshList", [render_mesh(*m) for m in meshes]),
    ]
    if material_groups:
        groups = [material_group(i, *g) for i, g in enumerate(material_groups.items())]
        nodes.append(listing("MaterialGroupList", groups))
    if attachments:
        nodes.append(listing("AttachmentList", [attachment(*a) for a in attachments]))
    if animations:
        nodes.append(listing("AnimationList", [animation(*a) for a in animations]))
    if hulls:
        nodes.append(listing("PhysicsShapeList", [physics_hull(h, surface) for h in hulls]))
    if scale != 1.0:
        nodes.append(listing("ModelModifierList", [scale_and_mirror(scale)]))
    root = {"rootNode": {"_class": "RootNode", "children": nodes}}
    with open(path, "w", newline="\n") as f:
        f.write(HEADER + write(root) + "\n")
    return path


def write_vpcf(
    path: FilePath,
    emitters: Iterable[Node],
    initializers: Iterable[Node],
    operators: Iterable[Node],
    renderers: Iterable[Node],
    children: Sequence[str] = (),
    **fields: Value,
) -> FilePath:
    """Writes a particle system. Each operator is an `op(...)`; `children` are .vpcf paths that
    start with it; `fields` are the system's own, such as m_nMaxParticles or m_ConstantColor.
    A texture is a `Resource`: m_vecTexturesInput=[{"m_hTexture": Resource(path)}].

    The compiler drops a field it doesn't know, so run `modelkit particles check` on the result.
    """
    system = {"_class": "CParticleSystemDefinition", "m_nBehaviorVersion": 12, **fields}
    system["m_Emitters"] = list(emitters)
    system["m_Initializers"] = list(initializers)
    system["m_Operators"] = list(operators)
    system["m_Renderers"] = list(renderers)
    if children:
        system["m_Children"] = [{"m_ChildRef": Resource(child)} for child in children]
    with open(path, "w", newline="\n") as f:
        f.write(PARTICLE_HEADER + write(system) + "\n")
    return path


def op(cls: str, **fields: Value) -> Node:
    """One emitter, initializer, operator or renderer, e.g. op("C_OP_Decay")."""
    return {"_class": cls, **fields}


def literal(value: float) -> Node:
    """A fixed number where the field takes an input, such as an emitter's particle count."""
    return {"m_nType": "PF_TYPE_LITERAL", "m_flLiteralValue": float(value)}


def vector(x: float, y: float, z: float) -> Node:
    """A fixed vector where the field takes an input, such as a velocity bound."""
    return {"m_nType": "PVEC_TYPE_LITERAL", "m_vLiteralValue": [float(x), float(y), float(z)]}


def listing(cls: str, children: list[Node]) -> Node:
    return {"_class": cls, "children": children}


def render_mesh(name: str, dmx: str) -> Node:
    return {"_class": "RenderMeshFile", "name": name, "filename": dmx}


def material_group(index: int, name: str, remaps: dict[str, str]) -> Node:
    pairs = [{"_class": "BaseMaterialRemap", "from": a, "to": b} for a, b in remaps.items()]
    kind = "DefaultMaterialGroup" if index == 0 else "MaterialGroup"
    return {"_class": kind, "name": name, "remaps": pairs}


def attachment(name: str, bone: str, origin: Triple, angles: Triple) -> Node:
    return {
        "_class": "Attachment",
        "name": name,
        "ignore_rotation": False,
        "parent_bone": bone,
        "relative_origin": list(origin),
        "relative_angles": list(angles),
        "weight": 1.0,
    }


def animation(name: str, dmx: str, looping: bool) -> Node:
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


def physics_hull(dmx: str, surface: str) -> Node:
    return {
        "_class": "PhysicsHullFile",
        "filename": dmx,
        "parent_bone": "",
        "surface_prop": surface,
        "collision_tags": "",
        "name": "",
    }


def scale_and_mirror(scale: float) -> Node:
    return {
        "_class": "ModelModifier_ScaleAndMirror",
        "scale": float(scale),
        "mirror_x": False,
        "mirror_y": False,
        "mirror_z": False,
        "flip_bone_forward": False,
        "swap_left_and_right_bones": False,
    }


def read_vmat(path: FilePath) -> dict[str, str]:
    """A .vmat's keys and values, such as {"TextureColor": "models/x/x_color.png"}."""
    with open(path, encoding="utf-8") as f:
        return dict(re.findall(r'^\s*"(\w+)"\s+"([^"]*)"', f.read(), re.MULTILINE))


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
    """What the ScaleAndMirror modifier applies; 1.0 without one."""
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
