"""Baking tiled CC0 materials into one unique texture set per part, with the wear a game prop
needs: chipped paint on edges, grime in crevices and low down, dust on top faces, and edges
rounded in the normal map.

A finish is a dict: `base` and `under` are map sets ({"color": path, "normal": ..., ...}) for the
surface and what its worn edges show; `tile` is game units per texture repeat; `hue_shift`
(-0.5 to 0.5) and `saturation` (1 keeps it) recolour the base, then `tint` multiplies it;
`camo` ({"colors": [[r, g, b], ...], "scale": units, "detail": 0-1}) paints a pattern over it,
in linear colour as Blender takes it (sRGB 190, 165, 125 is linear 0.51, 0.38, 0.20);
`metallic` overrides the base's metalness; `wear`, `grime`, `dust` and `streaks` run 0-1, and
`streak_width` and `streak_length` size the streaks in units.
"""

from statistics import NormalDist
from typing import Any

import bmesh
import bpy
from mathutils import Vector
from mathutils.geometry import barycentric_transform, closest_point_on_tri

ATLAS_UV = "atlas"
CHANNELS = ("color", "roughness", "metalness")
GRIME = (0.07, 0.06, 0.045, 1.0)
DUST = (0.52, 0.45, 0.35, 1.0)
STREAK = (0.22, 0.13, 0.07, 1.0)
BEVEL_RADIUS = 0.35

type Socket = bpy.types.NodeSocket
type Value = Socket | float | tuple[float, ...]


def find(sockets: Any, key: str) -> Socket:
    """A socket by identifier, such as "A_Float", or by name when no identifier matches."""
    return next((s for s in sockets if s.identifier == key), None) or sockets[key]


class Nodes:
    """Builds a material's node tree tersely: sockets by identifier, positions ignored."""

    def __init__(self, material: bpy.types.Material) -> None:
        material.use_nodes = True
        self.tree = material.node_tree
        self.tree.nodes.clear()

    def add(self, kind: str, **settings: Any) -> bpy.types.Node:
        node = self.tree.nodes.new(kind)
        for key, value in settings.items():
            setattr(node, key, value)
        return node

    def feed(self, node: bpy.types.Node, socket: str | int, value: Value) -> None:
        target = node.inputs[socket] if isinstance(socket, int) else find(node.inputs, socket)
        if isinstance(value, bpy.types.NodeSocket):
            self.tree.links.new(value, target)
        else:
            target.default_value = value

    def mix(self, kind: str, factor: Value, a: Value, b: Value, blend: str = "MIX") -> Socket:
        """A Mix node of `kind` FLOAT or RGBA."""
        node = self.add("ShaderNodeMix", data_type=kind, blend_type=blend)
        suffix = "Float" if kind == "FLOAT" else "Color"
        self.feed(node, "Factor_Float", factor)
        self.feed(node, f"A_{suffix}", a)
        self.feed(node, f"B_{suffix}", b)
        return find(node.outputs, f"Result_{suffix}")

    def math(self, operation: str, a: Value, b: Value = 0.0, clamp: bool = False) -> Socket:
        node = self.add("ShaderNodeMath", operation=operation, use_clamp=clamp)
        self.feed(node, 0, a)
        self.feed(node, 1, b)
        return node.outputs[0]

    def remap(self, value: Value, low: float, high: float) -> Socket:
        """`value` from `low`-`high` onto 0-1, clamped; low may exceed high to invert."""
        node = self.add("ShaderNodeMapRange", clamp=True)
        self.feed(node, "Value", value)
        node.inputs["From Min"].default_value = low
        node.inputs["From Max"].default_value = high
        return node.outputs["Result"]


def load_image(path: str, data: bool) -> bpy.types.Image:
    image = bpy.data.images.load(path, check_existing=True)
    image.colorspace_settings.name = "Non-Color" if data else "sRGB"
    return image


def paint_camo(n: Nodes, position: Socket, camo: dict[str, Any], paint: Value) -> Socket:
    """Hard-edged blobs of `camo["colors"]`, about `camo["scale"]` units across, with the paint
    texture's grain and scratches overlaid at `camo["detail"]`."""
    colors = camo["colors"]
    blobs = n.add("ShaderNodeTexNoise")
    blobs.inputs["Scale"].default_value = 1.0 / camo.get("scale", 40.0)
    blobs.inputs["Detail"].default_value = 3.0
    blobs.inputs["Distortion"].default_value = camo.get("distortion", 0.6)
    n.feed(blobs, "Vector", position)
    ramp = n.add("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    # Noise gathers around 0.5, so cut at its quantiles for even shares of each colour.
    spread = NormalDist(0.5, 0.075)
    stops = ramp.color_ramp.elements
    while len(stops) < len(colors):
        stops.new(1.0)
    for index, (stop, color) in enumerate(zip(stops, colors)):
        stop.position = spread.inv_cdf(index / len(colors)) if index else 0.0
        stop.color = (*color, 1.0)
    n.feed(ramp, "Fac", blobs.outputs["Fac"])
    # Only the paint's light and dark: painted metal sits near 0.28, so lift it to mid grey.
    grey = n.add("ShaderNodeRGBToBW")
    n.feed(grey, "Color", paint)
    grain = n.math("MULTIPLY", grey.outputs["Val"], camo.get("grain_gain", 1.8), clamp=True)
    detail = camo.get("detail", 0.6)
    return n.mix("RGBA", detail, ramp.outputs["Color"], grain, blend="OVERLAY")


def find_color_image(material: bpy.types.Material) -> bpy.types.Image | None:
    """The image feeding the material's base colour, through any nodes between."""
    if not material.node_tree:
        return None
    shader = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if shader is None:
        return None
    waiting = [link.from_node for link in shader.inputs["Base Color"].links]
    seen = set()
    while waiting:
        node = waiting.pop()
        if node.name in seen:
            continue
        seen.add(node.name)
        if node.type == "TEX_IMAGE" and node.image:
            return node.image
        waiting += [link.from_node for socket in node.inputs for link in socket.links]
    return None


def build_finish(
    material: bpy.types.Material,
    finish: dict[str, Any],
    height: float,
    artwork: tuple[bpy.types.Image, str] | None = None,
) -> None:
    """Turns `material` into the finish's worn surface, with an emission node per channel for
    baking. `height` is the part's height, for grime that gathers low down. `artwork`, an image
    and the UV map it was painted on, replaces the base colour when the finish asks for it, so
    stripes and signs survive the bake."""
    n = Nodes(material)
    coords = n.add("ShaderNodeTexCoord")
    scale = n.add("ShaderNodeMapping")
    scale.inputs["Scale"].default_value = [1.0 / finish["tile"]] * 3
    n.feed(scale, "Vector", coords.outputs["Object"])

    def texture(maps: dict[str, str], role: str, data: bool) -> Socket | None:
        if role not in maps:
            return None
        node = n.add(
            "ShaderNodeTexImage", projection="BOX", projection_blend=finish.get("blend", 0.25)
        )
        node.image = load_image(maps[role], data)
        n.feed(node, "Vector", scale.outputs["Vector"])
        return node.outputs["Color"]

    base, under = finish["base"], finish.get("under", finish["base"])
    base_color: Value = texture(base, "color", False) or (0.4, 0.4, 0.4, 1.0)
    if finish.get("artwork") and artwork:
        painted = n.add("ShaderNodeTexImage")
        painted.image = artwork[0]
        uv = n.add("ShaderNodeUVMap")
        uv.uv_map = artwork[1]
        n.feed(painted, "Vector", uv.outputs["UV"])
        base_color = painted.outputs["Color"]
    if "hue_shift" in finish or "saturation" in finish:
        shift = n.add("ShaderNodeHueSaturation")
        shift.inputs["Hue"].default_value = 0.5 + finish.get("hue_shift", 0.0)
        shift.inputs["Saturation"].default_value = finish.get("saturation", 1.0)
        n.feed(shift, "Color", base_color)
        base_color = shift.outputs["Color"]
    if finish.get("tint"):
        base_color = n.mix("RGBA", 1.0, base_color, (*finish["tint"], 1.0), blend="MULTIPLY")
    if camo := finish.get("camo"):
        base_color = paint_camo(n, coords.outputs["Object"], camo, base_color)
    under_color: Value = texture(under, "color", False) or (0.5, 0.5, 0.5, 1.0)
    base_rough: Value = texture(base, "roughness", True) or 0.6
    under_rough: Value = texture(under, "roughness", True) or 0.35
    base_metal: Value = finish.get("metallic", texture(base, "metalness", True) or 0.0)
    under_metal: Value = texture(under, "metalness", True) or 1.0

    # Edges: where a bevelled normal leaves the true one; noise makes their wear ragged.
    geometry = n.add("ShaderNodeNewGeometry")
    edge_bevel = n.add("ShaderNodeBevel", samples=8)
    edge_bevel.inputs["Radius"].default_value = BEVEL_RADIUS * 2
    dot = n.add("ShaderNodeVectorMath", operation="DOT_PRODUCT")
    n.feed(dot, 0, edge_bevel.outputs["Normal"])
    n.feed(dot, 1, geometry.outputs["True Normal"])
    edge = n.remap(n.math("SUBTRACT", 1.0, find(dot.outputs, "Value")), 0.0, 0.04)
    noise = n.add("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.35
    noise.inputs["Detail"].default_value = 10.0
    noise.inputs["Roughness"].default_value = 0.65
    n.feed(noise, "Vector", coords.outputs["Object"])
    chips = noise.outputs["Fac"]
    wear_amount = finish.get("wear", 0.5)
    ragged = n.math("ADD", n.math("MULTIPLY", edge, 1.2), n.math("MULTIPLY", chips, 0.8))
    wear = n.math(
        "MAXIMUM",
        n.remap(ragged, 1.25 - wear_amount * 0.5, 1.35 - wear_amount * 0.5),
        n.math("MULTIPLY", n.remap(chips, 0.66, 0.70), wear_amount * 0.6),
    )

    # Grime: in crevices, and more of it low down.
    occlusion = n.add("ShaderNodeAmbientOcclusion", only_local=True, samples=16)
    occlusion.inputs["Distance"].default_value = 3.0
    position = n.add("ShaderNodeSeparateXYZ")
    n.feed(position, "Vector", coords.outputs["Object"])
    lowness = n.remap(position.outputs["Z"], height * 0.35, 0.0)
    grime_amount = finish.get("grime", 0.5)
    crevices = n.math("SUBTRACT", 1.0, occlusion.outputs["AO"])
    grime = n.math(
        "ADD",
        n.math("MULTIPLY", crevices, grime_amount * 1.4),
        n.math("MULTIPLY", n.math("MULTIPLY", lowness, chips), grime_amount * 0.4),
        clamp=True,
    )

    # Dust: settled on faces looking up, and kicked up onto the lower third.
    facing = n.add("ShaderNodeSeparateXYZ")
    n.feed(facing, "Vector", geometry.outputs["Normal"])
    dust_amount = finish.get("dust", 0.4)
    patches = n.math("MULTIPLY", n.remap(chips, 0.35, 0.65), dust_amount)
    settled = n.math("MULTIPLY", n.remap(facing.outputs["Z"], 0.55, 0.95), patches)
    kicked = n.math("MULTIPLY", lowness, n.math("MULTIPLY", n.remap(chips, 0.3, 0.6), dust_amount))
    dust = n.math("MAXIMUM", settled, kicked)

    # Streaks: rust and dirt run down the sides, from noise stretched along Z.
    stretch = n.add("ShaderNodeMapping")
    width, length = finish.get("streak_width", 1.5), finish.get("streak_length", 40.0)
    stretch.inputs["Scale"].default_value = (1 / width, 1 / width, 1 / length)
    n.feed(stretch, "Vector", coords.outputs["Object"])
    runs = n.add("ShaderNodeTexNoise")
    runs.inputs["Scale"].default_value = 1.0
    runs.inputs["Detail"].default_value = 4.0
    n.feed(runs, "Vector", stretch.outputs["Vector"])
    sides = n.remap(n.math("ABSOLUTE", facing.outputs["Z"]), 0.5, 0.2)
    streaks = n.math(
        "MULTIPLY",
        n.math("MULTIPLY", n.remap(runs.outputs["Fac"], 0.55, 0.72), sides),
        finish.get("streaks", 0.0),
    )

    color = n.mix("RGBA", wear, base_color, under_color)
    color = n.mix("RGBA", streaks, color, STREAK)
    color = n.mix("RGBA", n.math("MULTIPLY", grime, 0.75), color, GRIME)
    color = n.mix("RGBA", dust, color, DUST)
    roughness = n.mix("FLOAT", wear, base_rough, under_rough)
    roughness = n.mix("FLOAT", n.math("MULTIPLY", grime, 0.6), roughness, 0.92)
    roughness = n.mix("FLOAT", dust, roughness, 0.95)
    metalness = n.mix("FLOAT", wear, base_metal, under_metal)
    dulled = n.math("MAXIMUM", dust, n.math("MULTIPLY", grime, 0.5))
    metalness = n.mix("FLOAT", dulled, metalness, 0.0)

    rounded = n.add("ShaderNodeBevel", samples=8)
    rounded.inputs["Radius"].default_value = BEVEL_RADIUS
    if (base_normal := texture(base, "normal", True)) is not None:
        normal_map = n.add("ShaderNodeNormalMap")
        normal_map.inputs["Strength"].default_value = finish.get("normal_strength", 1.0)
        n.feed(normal_map, "Color", base_normal)
        n.feed(rounded, "Normal", normal_map.outputs["Normal"])

    shader = n.add("ShaderNodeBsdfPrincipled", name="surface")
    n.feed(shader, "Base Color", color)
    n.feed(shader, "Roughness", roughness)
    n.feed(shader, "Metallic", metalness)
    n.feed(shader, "Normal", rounded.outputs["Normal"])
    output = n.add("ShaderNodeOutputMaterial", name="output")
    n.feed(output, "Surface", shader.outputs["BSDF"])
    for channel, value in (("color", color), ("roughness", roughness), ("metalness", metalness)):
        emit = n.add("ShaderNodeEmission", name=f"emit_{channel}")
        n.feed(emit, "Color", value)
    n.tree.nodes.active = n.add("ShaderNodeTexImage", name="bake_target")


class SelectOnly:
    """Makes `ob` the only selected, active object of its scene, for operators."""

    def __init__(self, ob: bpy.types.Object) -> None:
        self.ob = ob
        self.scene = ob.users_scene[0]
        self.override: Any = None

    def __enter__(self) -> bpy.types.Object:
        layer = self.scene.view_layers[0]
        for other in layer.objects:
            other.select_set(other == self.ob, view_layer=layer)
        layer.objects.active = self.ob
        self.override = bpy.context.temp_override(
            scene=self.scene,
            view_layer=layer,
            active_object=self.ob,
            edit_object=self.ob,
            object=self.ob,
            selected_objects=[self.ob],
            selected_editable_objects=[self.ob],
        )
        self.override.__enter__()
        return self.ob

    def __exit__(self, *failure: object) -> None:
        self.override.__exit__(*failure)


def make_atlas(
    ob: bpy.types.Object, materials: set[str], margin: float = 0.004, reserve: float = 0.0
) -> None:
    """Adds the atlas UV layer, made active: faces with `materials` unwrapped and packed into it,
    every other face keeping its old UVs. `reserve` leaves that share of the atlas free along
    its top and right edges, for a hidden mark."""
    mesh = ob.data
    if ATLAS_UV not in mesh.uv_layers:
        source = mesh.uv_layers.active
        layer = mesh.uv_layers.new(name=ATLAS_UV)
        for index, loop in enumerate(source.data):
            layer.data[index].uv = loop.uv
    mesh.uv_layers.active = mesh.uv_layers[ATLAS_UV]
    chosen = {i for i, m in enumerate(mesh.materials) if m and m.name in materials}
    # The UV operators correct for the aspect of an image in the materials, which stretches
    # islands 4:1 or worse on a non-square texture; a blank material has no image.
    saved = list(mesh.materials)
    blank = bpy.data.materials.new("modelkit_unwrap")
    for index in range(len(saved)):
        mesh.materials[index] = blank
    with SelectOnly(ob):
        bpy.ops.object.mode_set(mode="EDIT")
        bm = bmesh.from_edit_mesh(mesh)
        for face in bm.faces:
            face.select_set(face.material_index in chosen)
        bmesh.update_edit_mesh(mesh)
        bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=margin, area_weight=0.0)
        bpy.ops.uv.pack_islands(rotate=True, margin=margin, shape_method="CONCAVE")
        bpy.ops.object.mode_set(mode="OBJECT")
    for index, material in enumerate(saved):
        mesh.materials[index] = material
    bpy.data.materials.remove(blank)
    if reserve:
        shrink_atlas(ob, materials, reserve)


def shrink_atlas(ob: bpy.types.Object, materials: set[str], reserve: float) -> None:
    """Scales the atlas faces with `materials` toward the bottom-left corner, leaving `reserve`
    of the atlas free along its top and right edges."""
    mesh = ob.data
    layer = mesh.uv_layers[ATLAS_UV]
    chosen = {i for i, m in enumerate(mesh.materials) if m and m.name in materials}
    for polygon in mesh.polygons:
        if polygon.material_index in chosen:
            for loop in polygon.loop_indices:
                layer.data[loop].uv *= 1.0 - reserve


def bakeable_copy(ob: bpy.types.Object, materials: set[str]) -> bpy.types.Object:
    """A copy of `ob` holding only the faces to bake, linked into the same scene."""
    copy = ob.copy()
    copy.data = ob.data.copy()
    copy.name = f"{ob.name}_bake"
    ob.users_scene[0].collection.objects.link(copy)
    keep = {i for i, m in enumerate(copy.data.materials) if m and m.name in materials}
    bm = bmesh.new()
    bm.from_mesh(copy.data)
    dropped = [f for f in bm.faces if f.material_index not in keep]
    bmesh.ops.delete(bm, geom=dropped, context="FACES")
    bm.to_mesh(copy.data)
    bm.free()
    return copy


def use_fastest_device(scene: bpy.types.Scene) -> str:
    """Cycles on the first GPU backend that finds a device, else the CPU; returns which."""
    scene.render.engine = "CYCLES"
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
            scene.cycles.device = "GPU"
            return backend
    scene.cycles.device = "CPU"
    return "CPU"


def bake(
    copy: bpy.types.Object, size: int, folder: str, samples: int = 32, ao_samples: int = 128
) -> dict[str, str]:
    """Bakes each channel, the normal map and AO of `copy` into RGBA PNGs in `folder`; pixels no
    face covers stay transparent. Returns the files by channel."""
    scene = copy.users_scene[0]
    scene.render.bake.margin = 12
    scene.render.bake.margin_type = "EXTEND"
    scene.render.bake.use_clear = False
    # Slots whose faces bakeable_copy dropped keep their old material; only finishes bake.
    materials = [m for m in copy.data.materials if m and "bake_target" in m.node_tree.nodes]
    passes = [(c, "EMIT", samples) for c in CHANNELS]
    passes += [("normal", "NORMAL", samples), ("ao", "AO", ao_samples)]
    files = {}
    for channel, kind, count in passes:
        image = bpy.data.images.new(f"bake_{channel}", size, size, alpha=True)
        image.generated_color = (0, 0, 0, 0)
        image.colorspace_settings.name = "sRGB" if channel == "color" else "Non-Color"
        for material in materials:
            nodes = material.node_tree.nodes
            nodes["bake_target"].image = image
            nodes.active = nodes["bake_target"]
            source = nodes[f"emit_{channel}"] if kind == "EMIT" else nodes["surface"]
            material.node_tree.links.new(source.outputs[0], nodes["output"].inputs["Surface"])
        scene.cycles.samples = count
        with SelectOnly(copy):
            if kind == "NORMAL":
                bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", uv_layer=ATLAS_UV)
            else:
                bpy.ops.object.bake(type=kind, uv_layer=ATLAS_UV)
        files[channel] = f"{folder}/{copy.name}_{channel}.png"
        image.filepath_raw = files[channel]
        image.file_format = "PNG"
        image.save()
        bpy.data.images.remove(image)
    return files


def uv_frame(ob: bpy.types.Object, point: list[float]) -> dict[str, Any]:
    """Where the face nearest `point` sits in the atlas: the UV there, and the UV step for one
    unit right and one unit up along the face, for placing a stamp."""
    mesh = ob.data
    layer = mesh.uv_layers[ATLAS_UV]
    target = ob.matrix_world.inverted() @ Vector(point)
    mesh.calc_loop_triangles()

    def corners(tri: bpy.types.MeshLoopTriangle) -> list[Vector]:
        return [mesh.vertices[v].co for v in tri.vertices]

    nearest = min(
        mesh.loop_triangles,
        key=lambda tri: (closest_point_on_tri(target, *corners(tri)) - target).length,
    )
    uvs = [layer.data[loop].uv.to_3d() for loop in nearest.loops]
    right = Vector((0, 0, 1)).cross(nearest.normal)
    right = right.normalized() if right.length > 1e-3 else Vector((1, 0, 0))
    up = nearest.normal.cross(right).normalized()
    on_face = closest_point_on_tri(target, *corners(nearest))

    def to_uv(position: Vector) -> Vector:
        return barycentric_transform(position, *corners(nearest), *uvs).to_2d()

    origin = to_uv(on_face)
    return {
        "uv": list(origin),
        "right": list(to_uv(on_face + right) - origin),
        "up": list(to_uv(on_face + up) - origin),
        "material": mesh.materials[nearest.material_index].name,
    }
