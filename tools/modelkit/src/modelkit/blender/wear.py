"""A recipe finish as a material: tiled CC0 maps worn the way a game prop needs, with chipped
edges, grime in crevices and low down, dust on top, streaks down the sides and rounded edges.

The finish keys are documented with the recipe format in modelkit.recipe.
"""

from statistics import NormalDist
from typing import Any

import bpy

from modelkit.blender.nodes import Nodes, Socket, Value, find_socket

GRIME = (0.07, 0.06, 0.045, 1.0)
DUST = (0.52, 0.45, 0.35, 1.0)
STREAK = (0.22, 0.13, 0.07, 1.0)
BEVEL_RADIUS = 0.35
CHANNELS = ("color", "roughness", "metalness")


class WornMaterial(Nodes):
    """Turns a material into a finish's worn surface, with an `emit_<channel>` node per channel
    and a `bake_target` image node for baking. `height` is the part's height, for grime that
    gathers low down; `artwork`, an image and its UV map, replaces the base colour when the
    finish asks for it."""

    def __init__(
        self,
        material: bpy.types.Material,
        finish: dict[str, Any],
        height: float,
        artwork: tuple[bpy.types.Image, str] | None = None,
    ) -> None:
        super().__init__(material)
        self.finish = finish
        self.base = finish["base"]
        self.under = finish.get("under", finish["base"])
        self.position = self.add("ShaderNodeTexCoord").outputs["Object"]
        self.normal = self.add("ShaderNodeNewGeometry").outputs["Normal"]
        tiling = self.add("ShaderNodeMapping")
        tiling.inputs["Scale"].default_value = [1.0 / finish["tile"]] * 3
        self.feed(tiling, "Vector", self.position)
        self.tiled = tiling.outputs["Vector"]
        self.chips = self.noise(self.position, 0.35, 10.0, Roughness=0.65)
        self.lowness = self.remap(self.split(self.position)["Z"], height * 0.35, 0.0)
        self.build(artwork if finish.get("artwork") else None)

    def texture(self, maps: dict[str, str], role: str, data: bool) -> Socket | None:
        if role not in maps:
            return None
        blend = self.finish.get("blend", 0.25)
        return self.image(maps[role], data, self.tiled, projection="BOX", projection_blend=blend)

    def split(self, vector: Value) -> Any:
        node = self.add("ShaderNodeSeparateXYZ")
        self.feed(node, "Vector", vector)
        return node.outputs

    def base_color(self, artwork: tuple[bpy.types.Image, str] | None) -> Value:
        color: Value = self.texture(self.base, "color", False) or (0.4, 0.4, 0.4, 1.0)
        if artwork:
            painted = self.add("ShaderNodeTexImage")
            painted.image = artwork[0]
            uv = self.add("ShaderNodeUVMap", uv_map=artwork[1])
            self.feed(painted, "Vector", uv.outputs["UV"])
            color = painted.outputs["Color"]
        if "hue_shift" in self.finish or "saturation" in self.finish:
            shift = self.add("ShaderNodeHueSaturation")
            shift.inputs["Hue"].default_value = 0.5 + self.finish.get("hue_shift", 0.0)
            shift.inputs["Saturation"].default_value = self.finish.get("saturation", 1.0)
            self.feed(shift, "Color", color)
            color = shift.outputs["Color"]
        if tint := self.finish.get("tint"):
            color = self.mix("RGBA", 1.0, color, (*tint, 1.0), blend="MULTIPLY")
        if camo := self.finish.get("camo"):
            color = self.paint_camo(camo, color)
        return color

    def paint_camo(self, camo: dict[str, Any], paint: Value) -> Socket:
        """Hard-edged blobs of the camo colours with the paint's grain overlaid."""
        colors = camo["colors"]
        blobs = self.noise(
            self.position,
            1.0 / camo.get("scale", 40.0),
            3.0,
            Distortion=camo.get("distortion", 0.6),
        )
        ramp = self.add("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "CONSTANT"
        # Noise gathers around 0.5, so cut at its quantiles for even shares of each colour.
        spread = NormalDist(0.5, 0.075)
        stops = ramp.color_ramp.elements
        while len(stops) < len(colors):
            stops.new(1.0)
        for index, (stop, color) in enumerate(zip(stops, colors)):
            stop.position = spread.inv_cdf(index / len(colors)) if index else 0.0
            stop.color = (*color, 1.0)
        self.feed(ramp, "Fac", blobs)
        grey = self.add("ShaderNodeRGBToBW")
        self.feed(grey, "Color", paint)
        # Painted metal sits near 0.28 grey: lift it to mid grey so only its grain shows.
        grain = self.math("MULTIPLY", grey.outputs["Val"], camo.get("grain_gain", 1.8), clamp=True)
        return self.mix(
            "RGBA", camo.get("detail", 0.6), ramp.outputs["Color"], grain, blend="OVERLAY"
        )

    def edge_wear(self) -> Socket:
        """Where a bevelled normal leaves the shading one, made ragged by noise."""
        bevel = self.add("ShaderNodeBevel", samples=8)
        bevel.inputs["Radius"].default_value = BEVEL_RADIUS * 2
        dot = self.add("ShaderNodeVectorMath", operation="DOT_PRODUCT")
        self.feed(dot, 0, bevel.outputs["Normal"])
        # Not the true normal: on a smooth-shaded flat face every pixel would read as an edge.
        self.feed(dot, 1, self.normal)
        edge = self.remap(self.math("SUBTRACT", 1.0, find_socket(dot.outputs, "Value")), 0.0, 0.04)
        amount = self.finish.get("wear", 0.5)
        ragged = self.math("ADD", self.scale(edge, 1.2), self.scale(self.chips, 0.8))
        return self.math(
            "MAXIMUM",
            self.remap(ragged, 1.25 - amount * 0.5, 1.35 - amount * 0.5),
            self.scale(self.remap(self.chips, 0.66, 0.70), amount * 0.6),
        )

    def grime(self) -> Socket:
        """In crevices, and more of it low down."""
        occlusion = self.add("ShaderNodeAmbientOcclusion", only_local=True, samples=16)
        occlusion.inputs["Distance"].default_value = 3.0
        amount = self.finish.get("grime", 0.5)
        crevices = self.math("SUBTRACT", 1.0, occlusion.outputs["AO"])
        return self.math(
            "ADD",
            self.scale(crevices, amount * 1.4),
            self.scale(self.math("MULTIPLY", self.lowness, self.chips), amount * 0.4),
            clamp=True,
        )

    def dust(self, facing_up: Socket) -> Socket:
        """Settled on faces looking up, and kicked up onto the lower third."""
        amount = self.finish.get("dust", 0.4)
        patches = self.scale(self.remap(self.chips, 0.35, 0.65), amount)
        settled = self.math("MULTIPLY", self.remap(facing_up, 0.55, 0.95), patches)
        kicked = self.math(
            "MULTIPLY", self.lowness, self.scale(self.remap(self.chips, 0.3, 0.6), amount)
        )
        return self.math("MAXIMUM", settled, kicked)

    def streaks(self, facing_up: Socket) -> Socket:
        """Rust and dirt running down the sides, from noise stretched along Z."""
        stretch = self.add("ShaderNodeMapping")
        width = self.finish.get("streak_width", 1.5)
        length = self.finish.get("streak_length", 40.0)
        stretch.inputs["Scale"].default_value = (1 / width, 1 / width, 1 / length)
        self.feed(stretch, "Vector", self.position)
        runs = self.noise(stretch.outputs["Vector"], 1.0, 4.0)
        sides = self.remap(self.math("ABSOLUTE", facing_up), 0.5, 0.2)
        return self.scale(
            self.math("MULTIPLY", self.remap(runs, 0.55, 0.72), sides),
            self.finish.get("streaks", 0.0),
        )

    def rounded_normal(self) -> Socket:
        rounded = self.add("ShaderNodeBevel", samples=8)
        rounded.inputs["Radius"].default_value = BEVEL_RADIUS
        if (base_normal := self.texture(self.base, "normal", True)) is not None:
            normal_map = self.add("ShaderNodeNormalMap")
            normal_map.inputs["Strength"].default_value = self.finish.get("normal_strength", 0.5)
            self.feed(normal_map, "Color", base_normal)
            self.feed(rounded, "Normal", normal_map.outputs["Normal"])
        return rounded.outputs["Normal"]

    def build(self, artwork: tuple[bpy.types.Image, str] | None) -> None:
        texture = self.texture
        wear, grime = self.edge_wear(), self.grime()
        facing_up = self.split(self.normal)["Z"]
        dust, streaks = self.dust(facing_up), self.streaks(facing_up)

        color = self.mix(
            "RGBA",
            wear,
            self.base_color(artwork),
            texture(self.under, "color", False) or (0.5, 0.5, 0.5, 1.0),
        )
        color = self.mix("RGBA", streaks, color, STREAK)
        color = self.mix("RGBA", self.scale(grime, 0.75), color, GRIME)
        color = self.mix("RGBA", dust, color, DUST)
        base_rough = texture(self.base, "roughness", True) or 0.6
        roughness = self.mix(
            "FLOAT", wear, base_rough, texture(self.under, "roughness", True) or 0.35
        )
        roughness = self.mix("FLOAT", self.scale(grime, 0.6), roughness, 0.92)
        roughness = self.mix("FLOAT", dust, roughness, 0.95)
        base_metal = self.finish.get("metallic", texture(self.base, "metalness", True) or 0.0)
        metalness = self.mix(
            "FLOAT", wear, base_metal, texture(self.under, "metalness", True) or 1.0
        )
        dulled = self.math("MAXIMUM", dust, self.scale(grime, 0.5))
        metalness = self.mix("FLOAT", dulled, metalness, 0.0)

        shader = self.add("ShaderNodeBsdfPrincipled", name="surface")
        self.set(shader, Base_Color=color, Roughness=roughness, Metallic=metalness)
        self.feed(shader, "Normal", self.rounded_normal())
        output = self.add("ShaderNodeOutputMaterial", name="output")
        self.feed(output, "Surface", shader.outputs["BSDF"])
        for channel, value in zip(CHANNELS, (color, roughness, metalness), strict=True):
            self.feed(self.add("ShaderNodeEmission", name=f"emit_{channel}"), "Color", value)
        self.tree.nodes.active = self.add("ShaderNodeTexImage", name="bake_target")
