"""Building and reading material node trees."""

from typing import Any

import bpy

from modelkit.blender.surfaces import image

type Socket = bpy.types.NodeSocket
type Value = Socket | float | tuple[float, ...]


def find_socket(sockets: Any, key: str) -> Socket:
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
        target = (
            node.inputs[socket] if isinstance(socket, int) else find_socket(node.inputs, socket)
        )
        if isinstance(value, bpy.types.NodeSocket):
            self.tree.links.new(value, target)
        else:
            target.default_value = value

    def set(self, node: bpy.types.Node, **inputs: Value) -> bpy.types.Node:
        """Feeds inputs by name, spaces written as underscores: set(node, From_Min=0.2)."""
        for name, value in inputs.items():
            self.feed(node, name.replace("_", " "), value)
        return node

    def image(self, path: str, data: bool, vector: Socket | None = None, **settings: Any) -> Socket:
        node = self.add("ShaderNodeTexImage", **settings)
        node.image = image(path, data)
        if vector is not None:
            self.feed(node, "Vector", vector)
        return node.outputs["Color"]

    def mix(self, kind: str, factor: Value, a: Value, b: Value, blend: str = "MIX") -> Socket:
        """A Mix node of `kind` FLOAT or RGBA."""
        node = self.add("ShaderNodeMix", data_type=kind, blend_type=blend)
        suffix = "Float" if kind == "FLOAT" else "Color"
        self.feed(node, "Factor_Float", factor)
        self.feed(node, f"A_{suffix}", a)
        self.feed(node, f"B_{suffix}", b)
        return find_socket(node.outputs, f"Result_{suffix}")

    def math(self, operation: str, a: Value, b: Value = 0.0, clamp: bool = False) -> Socket:
        node = self.add("ShaderNodeMath", operation=operation, use_clamp=clamp)
        self.feed(node, 0, a)
        self.feed(node, 1, b)
        return node.outputs[0]

    def scale(self, value: Value, factor: float) -> Socket:
        return self.math("MULTIPLY", value, factor)

    def remap(self, value: Value, low: float, high: float) -> Socket:
        """`value` from `low`-`high` onto 0-1, clamped; low may exceed high to invert."""
        node = self.add("ShaderNodeMapRange", clamp=True)
        self.feed(node, "Value", value)
        node.inputs["From Min"].default_value = low
        node.inputs["From Max"].default_value = high
        return node.outputs["Result"]

    def noise(self, vector: Value, scale: float, detail: float, **inputs: float) -> Socket:
        node = self.set(self.add("ShaderNodeTexNoise"), Scale=scale, Detail=detail, **inputs)
        self.feed(node, "Vector", vector)
        return node.outputs["Fac"]


def find_image(material: bpy.types.Material, socket: str = "Base Color") -> bpy.types.Image | None:
    """The image feeding a Principled BSDF input, through any nodes between."""
    if not material.node_tree:
        return None
    shader = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if shader is None:
        return None
    waiting = [link.from_node for link in shader.inputs[socket].links]
    seen = set()
    while waiting:
        # Breadth first, in input order: an old bake mixes its AO map in as the second colour.
        node = waiting.pop(0)
        if node.name in seen:
            continue
        seen.add(node.name)
        if node.type == "TEX_IMAGE" and node.image:
            return node.image
        waiting += [link.from_node for socket in node.inputs for link in socket.links]
    return None


def show_texture_set(material: bpy.types.Material, maps: dict[str, str]) -> None:
    """Rebuilds `material` over a baked set, for Blender's preview; the game reads the .vmat."""
    n = Nodes(material)
    shader = n.add("ShaderNodeBsdfPrincipled")
    normal = n.add("ShaderNodeNormalMap")
    n.feed(normal, "Color", n.image(maps["normal"], True))
    n.set(
        shader,
        Base_Color=n.image(maps["color"], False),
        Roughness=n.image(maps["roughness"], True),
        Metallic=n.image(maps["metalness"], True),
        Normal=normal.outputs["Normal"],
    )
    n.feed(n.add("ShaderNodeOutputMaterial"), "Surface", shader.outputs["BSDF"])
