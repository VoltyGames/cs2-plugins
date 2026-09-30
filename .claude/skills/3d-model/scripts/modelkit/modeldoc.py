"""The files the compiler reads: .vmat materials, ModelDoc .vmdl models and .vpcf particle
systems. Needs no Blender."""

HEADER = (
    "<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} "
    "format:modeldoc28:version{fb63b6ca-f435-4aa0-a2c7-c66ddc651dca} -->\n"
)
PARTICLE_HEADER = (
    "<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} "
    "format:vpcf66:version{dd571be4-586e-4f41-8b2d-5bbc969e1c53} -->\n"
)


class Resource(str):
    """A path to another compiled file, such as a particle's texture or child effect."""


def write_vmat(
    path,
    folder,
    color,
    rough,
    normal=None,
    metalness=0.6,
    roughness=0.55,
    glow_mask=None,
    glow=1.0,
    opacity=None,
    cutout=None,
):
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
    body = "".join(f'\t"{k}"\t"{v}"\n' for k, v in keys)
    with open(path, "w", newline="\n") as f:
        f.write(f'"Layer0"\n{{\n{body}}}\n')
    return path


def write_vmdl(
    path,
    meshes,
    hulls=(),
    animations=(),
    material_groups=None,
    attachments=(),
    surface="metal",
    scale=1.0,
):
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
        f.write(HEADER + kv3(root) + "\n")
    return path


def write_vpcf(path, emitters, initializers, operators, renderers, children=(), **fields):
    """Writes a particle system. Each operator is an `op(...)`; `children` are .vpcf paths that
    start with it; `fields` are the system's own, such as m_nMaxParticles or m_ConstantColor.
    A texture is a `Resource`: m_vecTexturesInput=[{"m_hTexture": Resource(path)}].

    The compiler drops a field it doesn't know, so run `particles.py check` on the result.
    """
    system = {"_class": "CParticleSystemDefinition", "m_nBehaviorVersion": 12, **fields}
    system["m_Emitters"] = list(emitters)
    system["m_Initializers"] = list(initializers)
    system["m_Operators"] = list(operators)
    system["m_Renderers"] = list(renderers)
    if children:
        system["m_Children"] = [{"m_ChildRef": Resource(child)} for child in children]
    with open(path, "w", newline="\n") as f:
        f.write(PARTICLE_HEADER + kv3(system) + "\n")
    return path


def op(cls, **fields):
    """One emitter, initializer, operator or renderer, e.g. op("C_OP_Decay")."""
    return {"_class": cls, **fields}


def literal(value):
    """A fixed number where the field takes an input, such as an emitter's particle count."""
    return {"m_nType": "PF_TYPE_LITERAL", "m_flLiteralValue": float(value)}


def vector(x, y, z):
    """A fixed vector where the field takes an input, such as a velocity bound."""
    return {"m_nType": "PVEC_TYPE_LITERAL", "m_vLiteralValue": [float(x), float(y), float(z)]}


def listing(cls, children):
    return {"_class": cls, "children": children}


def render_mesh(name, dmx):
    return {"_class": "RenderMeshFile", "name": name, "filename": dmx}


def material_group(index, name, remaps):
    pairs = [{"_class": "BaseMaterialRemap", "from": a, "to": b} for a, b in remaps.items()]
    kind = "DefaultMaterialGroup" if index == 0 else "MaterialGroup"
    return {"_class": kind, "name": name, "remaps": pairs}


def attachment(name, bone, origin, angles):
    return {
        "_class": "Attachment",
        "name": name,
        "ignore_rotation": False,
        "parent_bone": bone,
        "relative_origin": list(origin),
        "relative_angles": list(angles),
        "weight": 1.0,
    }


def animation(name, dmx, looping):
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


def physics_hull(dmx, surface):
    return {
        "_class": "PhysicsHullFile",
        "filename": dmx,
        "parent_bone": "",
        "surface_prop": surface,
        "collision_tags": "",
        "name": "",
    }


def scale_and_mirror(scale):
    return {
        "_class": "ModelModifier_ScaleAndMirror",
        "scale": float(scale),
        "mirror_x": False,
        "mirror_y": False,
        "mirror_z": False,
        "flip_bone_forward": False,
        "swap_left_and_right_bones": False,
    }


def kv3(value, depth=0):
    pad = "\t" * depth
    if isinstance(value, dict):
        fields = "".join(f"{pad}\t{k} = {kv3(v, depth + 1)}\n" for k, v in value.items())
        return "{\n" + fields + pad + "}"
    if isinstance(value, list):
        if not value:
            return "[  ]"
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
            return "[ " + ", ".join(kv3(v) for v in value) + " ]"
        return "[\n" + "".join(f"{pad}\t{kv3(v, depth + 1)},\n" for v in value) + pad + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        text = f"{value:.6f}".rstrip("0")
        return text + "0" if text.endswith(".") else text
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Resource):
        return f'resource:"{value}"'
    return f'"{value}"'
