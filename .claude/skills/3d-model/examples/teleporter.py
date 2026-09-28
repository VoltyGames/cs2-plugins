"""The Stronghold teleporter built with modelkit: glow, team colour and FX animations.

Rebuilds plugins/stronghold/content/models/stronghold/teleporter in the scene "teleporter" from the
committed textures, and draws the well's glow. A rotor turns under the grate over the lit well,
and on each teleport the team-coloured light strip lifts off as a hoop and sweeps past the player.
Run it inside Blender with the repo root as REPO:

    ns = {"REPO": r"<repo>"}
    exec(open(r"<repo>/.claude/skills/3d-model/examples/teleporter.py").read(), ns)

After `source2.export`, `ns["write_modeldoc"]()` writes the .vmat files and the .vmdl.
"""

import math
import os
import sys

import bmesh
import numpy as np
from mathutils import Matrix

sys.path.insert(0, os.path.join(REPO, ".claude", "skills", "3d-model", "scripts"))  # noqa: F821
import modelkit  # noqa: E402

modelkit.reload()
from modelkit import (  # noqa: E402
    modeldoc,
    objects,
    preview,
    rig,
    session,
    shapes,
    source2,
    surfaces,
)

FOLDER = "models/stronghold/teleporter/"
DIR = os.path.join(REPO, "plugins", "stronghold", "content", FOLDER)  # noqa: F821

# The drum is 47.2 across; the light strip rings it at 48, level with the placement box.
DRUM, PANELS, SEAM = 23.6, 8, 0.2
BODY_TOP, STRIP_TOP, TOP = 4.75, 5.25, 7.5
STRIP_IN, STRIP_OUT = 23.62, 24.0
RIM_IN = 21.0
FRAME_IN, FRAME_BOTTOM, FRAME_TOP = 19.6, 6.4, 6.9
GRATE_TOP, BAR, DEPTH, PITCH = 6.75, 0.25, 0.45, 1.9
FLOOR = 1.4
BLADE_ROOT, BLADE_TIP = 2.8, 18.8

session.scene("teleporter", FOLDER)


def texture(name, data=False):
    return surfaces.image(os.path.join(DIR, name), data)


def textured(name, metallic, roughness, normal):
    bump = texture(f"teleporter_{normal}_normal.png", data=True)
    color = texture(f"teleporter_{name}_color.png")
    return surfaces.material(f"teleporter_{name}.vmat", color, bump, metallic, roughness)


# The rim and well colours are the generated body texture at 1.8 and 0.45 brightness; the body 1.4.
BODY = textured("body", 0.45, 0.55, "body")
RIM = textured("rim", 0.5, 0.5, "body")
WELL = textured("well", 0.4, 0.7, "body")
STEEL = textured("steel", 0.85, 0.4, "steel")
# The team colour: the red material group swaps in teleporter_strip_red.vmat.
STRIP = surfaces.material("teleporter_strip.vmat", glow=(0.02, 0.3, 1.0))


def draw_glow(path, size=512):
    """The well's light: brightest at the rotor and fading to dark at the frame, in faint rings."""
    y, x = np.mgrid[0:size, 0:size]
    r = np.hypot((x + 0.5) / size * 2 - 1, (y + 0.5) / size * 2 - 1)
    light = np.clip(1 - (r - 0.15) / 0.9, 0, 1) ** 1.8
    light *= 0.85 + 0.15 * np.cos(r * np.pi * 14) ** 2
    px = np.ones((size, size, 4), dtype=np.float32)
    px[..., :3] = light[..., None] * np.array((0.75, 0.9, 1.0), dtype=np.float32)
    return surfaces.save_pixels(path, px)


# A flat glow this large read as a hot grill in game, so the well is lit from the rotor outwards.
glow = draw_glow(os.path.join(DIR, "teleporter_core_color.png"))
CORE = surfaces.material("teleporter_core.vmat", glow, metallic=0.0, roughness=0.4, glow=True)


def turned(bm, degrees):
    turn = Matrix.Rotation(math.radians(degrees), 3, "Z")
    bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=turn, verts=bm.verts)
    return bm


def polar(radius, degrees):
    a = math.radians(degrees)
    return (radius * math.cos(a), radius * math.sin(a))


def panels(r_in, r_out, z0, z1):
    """A ring cut into the drum's panels, `SEAM` apart at the outer face."""
    half = math.degrees(SEAM / 2 / r_out)
    step = 360 / PANELS
    return shapes.merge(
        shapes.sector(r_in, r_out, i * step + half, (i + 1) * step - half, z0, z1, seg=8)
        for i in range(PANELS)
    )


def part(name, bm, mat, bone="root", **finish):
    return objects.finish(objects.to_object(name, bm), mat, bone, **finish)


def across_well(ob):
    """Maps `ob`'s UVs across the whole well, centred on the rotor."""
    uv = ob.data.uv_layers.active.data
    for loop in ob.data.loops:
        co = ob.data.vertices[loop.vertex_index].co
        uv[loop.index].uv = (0.5 + co.x / (2 * FRAME_IN), 0.5 + co.y / (2 * FRAME_IN))
    return ob


def grate():
    """A square mesh of bars inside the frame ring, leaving the centre lines to the cross."""
    bars = []
    count = int(FRAME_IN // PITCH)
    reach = FRAME_IN + 0.3
    for k in range(-count, count + 1):
        if k == 0:
            continue
        at = k * PITCH
        half = math.sqrt(reach**2 - at**2)
        z = GRATE_TOP - DEPTH / 2
        bars.append(shapes.box((0, at, z), (2 * half, BAR, DEPTH)))
        bars.append(shapes.box((at, 0, z), (BAR, 2 * half, DEPTH)))
    return shapes.merge(bars)


parts = []

# Drum: eight panels under a thick rim, with a core behind the seams and the strip's channel.
parts.append(part("body", panels(22.0, DRUM, 0.0, BODY_TOP), BODY, uv_size=24.0, bevel=0.12))
parts.append(part("rim", panels(RIM_IN, DRUM, STRIP_TOP, TOP), RIM, uv_size=24.0, bevel=0.15))
well = shapes.merge(
    [
        shapes.tube(21.5, DRUM - 0.3, 0.05, TOP - 0.05, seg=64),
        shapes.tube(FRAME_IN, 22.05, FLOOR - 0.4, FRAME_BOTTOM, seg=48),
        shapes.cone(FRAME_IN + 0.1, FRAME_IN + 0.1, 0.0, FLOOR, seg=48),
    ]
)
parts.append(part("well", well, WELL, uv_size=24.0))
bolts = shapes.bolts(22.3, [i * 22.5 + 11.25 for i in range(16)], 0.45, TOP - 0.05, TOP + 0.25)
parts.append(part("bolts", bolts, STEEL, uv_size=8.0))

# Grate: the frame ring, the mesh and the cross, over the well.
frame = shapes.tube(FRAME_IN, RIM_IN + 0.02, FRAME_BOTTOM, FRAME_TOP, seg=48)
parts.append(part("frame", frame, STEEL, uv_size=16.0, bevel=0.08))
parts.append(part("grate", grate(), STEEL, uv_size=16.0))
reach = 2 * (FRAME_IN + 0.3)
cross = shapes.merge(
    [
        shapes.box((0, 0, GRATE_TOP - 0.3), (reach, 1.0, 0.7)),
        shapes.box((0, 0, GRATE_TOP - 0.3), (1.0, reach, 0.7)),
    ]
)
parts.append(part("cross", cross, STEEL, uv_size=16.0, bevel=0.08))

# The lit floor, in rings under the rotor's blades.
bands = ((3.4, 7.2), (8.0, 11.6), (12.4, 16.0), (16.8, 19.0))
rings = shapes.merge(shapes.tube(r0, r1, FLOOR - 0.05, FLOOR + 0.1, seg=48) for r0, r1 in bands)
parts.append(across_well(part("floor_glow", rings, CORE)))

# Rotor: four swept blades on a hub, dark against the glowing floor.
blade = [polar(BLADE_ROOT, -35), polar(BLADE_TIP, 0), polar(BLADE_TIP, 22), polar(BLADE_ROOT, 40)]
blades = shapes.merge(turned(shapes.prism(blade, 2.8, 3.3), 90 * i) for i in range(4))
hub = shapes.merge(
    [shapes.cone(3.0, 3.0, FLOOR, 4.0, seg=32), shapes.cone(2.6, 1.9, 4.0, 4.5, seg=32)]
)
parts.append(part("rotor", shapes.merge([blades, hub]), STEEL, "rotor", uv_size=16.0, bevel=0.1))

# The light strip sits proud of the drum on its own bone, so it can lift off without clipping.
strip = panels(STRIP_IN, STRIP_OUT, BODY_TOP, STRIP_TOP)
parts.append(part("strip", strip, STRIP, "strip", uv_size=8.0))

body = objects.join(parts, "teleporter")

bones = [
    ("root", (0, 0, 0), (0, 0, 3), None),
    ("rotor", (0, 0, FLOOR), (0, 0, FLOOR + 3), "root"),
    ("strip", (0, 0, BODY_TOP), (0, 0, BODY_TOP + 3), "root"),
]
arm = rig.skeleton("teleporter_skeleton", bones, [body])
objects.hull("teleporter_hull", shapes.cone(23.8, 23.8, 0.0, 7.0, seg=24), BODY)

IDLE_SPEED = 6.0  # degrees a frame: half a turn a second


def spin(frames, burst=0.0):
    """Rotor keys over `frames`, sped up early by `burst` extra turns.

    `frames` and `burst` must come to whole turns, so the rotor ends where the idle loop starts.
    """
    pulse = [(f / 4) * math.exp(1 - f / 4) for f in range(frames)]
    extra = [360 * burst * p / sum(pulse) for p in pulse]
    angle, keys = 0.0, []
    for frame in range(frames + 1):
        keys.append((frame, (0, 0, 0), (0, 0, angle)))
        if frame < frames:
            angle += IDLE_SPEED + extra[frame]
    return keys


def lift(keys):
    return [(frame, (0, 0, height), (0, 0, 0)) for frame, height in rig.eased(keys)]


rig.animate(arm, "teleporter_idle", {"rotor": spin(60)})
# The entrance's hoop shoots up past a player's head and drops back into place.
send = [(0, 0.0), (2, 3.0), (5, 22.0), (8, 58.0), (10, 74.0), (11, 76.0), (13, 72.0)]
send += [(17, 44.0), (21, 12.0), (23, 0.0), (25, -0.6), (27, 0.2), (30, 0.0)]
rig.animate(arm, "teleporter_send", {"rotor": spin(30, burst=1.5), "strip": lift(send)})
# The exit's hoop starts overhead and sweeps down over the arriving player.
arrive = [(0, 76.0), (2, 74.0), (6, 52.0), (10, 24.0), (13, 6.0), (15, 0.0), (17, -0.8)]
arrive += [(20, 0.3), (23, 0.0), (30, 0.0)]
rig.animate(arm, "teleporter_arrive", {"rotor": spin(30, burst=1.5), "strip": lift(arrive)})
rig.show(arm, "teleporter_idle")
# Action names are shared by every scene in the session, so they carry the model's name.
source2.remember(
    "teleporter",
    model="teleporter",
    armature="teleporter_skeleton",
    actions=("teleporter_idle", "teleporter_send", "teleporter_arrive"),
    files={"teleporter": "teleporter_teleporter"},
)
preview.stage()


def write_modeldoc():
    """The .vmat files, the strip's team colours and the .vmdl with its red material group."""
    rough, mask = FOLDER + "teleporter_rough.png", "teleporter_glow_mask.png"
    surfaces.solid(os.path.join(DIR, "teleporter_rough.png"), (1, 1, 1))
    surfaces.solid(os.path.join(DIR, mask), (1, 1, 1))
    surfaces.solid(os.path.join(DIR, "teleporter_strip_color.png"), (0.08, 0.45, 1.0))
    surfaces.solid(os.path.join(DIR, "teleporter_strip_red_color.png"), (1.0, 0.18, 0.06))

    def vmat(name, color, normal=None, **look):
        path = os.path.join(DIR, f"teleporter_{name}.vmat")
        return modeldoc.write_vmat(path, FOLDER, color, rough, normal, **look)

    body_normal = "teleporter_body_normal.png"
    vmat("body", "teleporter_body_color.png", body_normal, metalness=0.45, roughness=0.55)
    vmat("rim", "teleporter_rim_color.png", body_normal, metalness=0.5, roughness=0.5)
    vmat("well", "teleporter_well_color.png", body_normal, metalness=0.4, roughness=0.7)
    steel_normal = "teleporter_steel_normal.png"
    vmat("steel", "teleporter_steel_color.png", steel_normal, metalness=0.85, roughness=0.4)
    for name in ("strip", "strip_red", "core"):
        color = f"teleporter_{name}_color.png"
        vmat(name, color, metalness=0.0, roughness=0.4, glow_mask=mask, glow=1.0)

    def at(name):
        return FOLDER + name

    modeldoc.write_vmdl(
        os.path.join(DIR, "teleporter.vmdl"),
        meshes=[("teleporter", at("teleporter_teleporter.dmx"))],
        hulls=[at("teleporter_hull.dmx")],
        animations=[
            ("idle", at("teleporter_teleporter_idle.dmx"), True),
            ("send", at("teleporter_teleporter_send.dmx"), False),
            ("arrive", at("teleporter_teleporter_arrive.dmx"), False),
        ],
        material_groups={
            "blue": {},
            "red": {at("teleporter_strip.vmat"): at("teleporter_strip_red.vmat")},
        },
    )


result = {
    "tris": sum(len(p.vertices) - 2 for p in body.data.polygons),
    "size": [round(v, 2) for v in body.dimensions],
}
