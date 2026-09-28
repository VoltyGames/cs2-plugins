"""The Stronghold jump pad built with modelkit: a skinned, animated scissor lift.

Rebuilds plugins/stronghold/content/models/stronghold/jump_pad in the scene "jump_pad" from the
committed textures. Run it inside Blender with the repo root as REPO:

    ns = {"REPO": r"<repo>"}
    exec(open(r"<repo>/.claude/skills/3d-model/examples/jump_pad.py").read(), ns)
"""

import math
import os
import sys

import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.join(REPO, ".claude", "skills", "3d-model", "scripts"))  # noqa: F821
import modelkit  # noqa: E402

modelkit.reload()
from modelkit import objects, preview, rig, session, shapes, source2, surfaces  # noqa: E402

FOLDER = "models/stronghold/jump_pad/"
DIR = os.path.join(REPO, "plugins", "stronghold", "content", FOLDER)  # noqa: F821

# The deck is 38 x 30 with its top 14.5 up; +X, the launch direction, runs along its length.
DECK_X, DECK_Y, DECK_TOP, DECK_BOTTOM = 19.0, 15.0, 14.5, 11.5
PLATE_Z = DECK_TOP - 0.5
BORDER = 2.8
INSIDE_X, INSIDE_Y = DECK_X - BORDER, DECK_Y - BORDER
RIM_X, RIM_Y = (DECK_X + INSIDE_X) / 2, (DECK_Y + INSIDE_Y) / 2
RAIL_IN, RAIL_OUT = 11.6, 13.8

# Each side has an X of two arms. The inner arm pivots on the base at the rear and rolls under
# the deck at the front; the outer arm pivots on the deck at the rear and rolls on the base.
REAR, SPAN = -14.0, 28.0
FRONT = REAR + SPAN
BASE_PIN_Z, DECK_PIN_Z = 2.8, 10.2
ARM = math.hypot(SPAN, DECK_PIN_Z - BASE_PIN_Z)
INNER_Y, OUTER_Y, ARM_WIDTH, ARM_DEPTH = 9.6, 10.9, 1.0, 1.9
WHEEL = 1.0

# Two telescopic rams push the inner arms up, from a base cross member to a tube on the arms.
RAM_Y = 6.0
RAM_BASE = Vector((-4.7, 0.0, 2.2))
RAM_ON_ARM = 18.6
EYE = 0.8
LOWEST, HIGHEST = -1.0, 19.5

session.scene("jump_pad", FOLDER)


def texture(name, data=False):
    return surfaces.image(os.path.join(DIR, name), data)


def textured(name, metallic, roughness, normal=True):
    bump = texture(f"jump_pad_{name}_normal.png", data=True) if normal else None
    color = texture(f"jump_pad_{name}_color.png")
    return surfaces.material(f"jump_pad_{name}.vmat", color, bump, metallic, roughness)


FRAME = textured("frame", 0.2, 0.6)
STEEL = textured("steel", 0.8, 0.45)
CHROME = textured("chrome", 1.0, 0.2, normal=False)
DECK = textured("deck", 0.7, 0.5)
HAZARD = textured("hazard", 0.2, 0.6)
ARROW = textured("arrow", 0.2, 0.6)


def arm_angle(lift):
    return math.asin((DECK_PIN_Z - BASE_PIN_Z + lift) / ARM)


def arm_point(distance, lift):
    """The point `distance` along the inner arm from its base pivot, in the XZ plane."""
    angle = arm_angle(lift)
    x, z = distance * math.cos(angle), distance * math.sin(angle)
    return Vector((REAR + x, 0.0, BASE_PIN_Z + z))


def ram_length(lift):
    return (arm_point(RAM_ON_ARM, lift) - RAM_BASE).length


# A body and two stages; a stage shows 1.0 at the shortest and keeps 1.2 inside at the longest.
BODY = ram_length(LOWEST) - 2 * EYE - 2.0
STAGE = (ram_length(HIGHEST) - 2 * EYE - BODY) / 2 + 1.2
SHOWING = (ram_length(0.0) - 2 * EYE - BODY) / 2


def mirrored(make):
    """`make(side)` for side +1 and -1, merged."""
    return shapes.merge([make(1), make(-1)])


def at_corners(make):
    """`make(sx, sy)` at the four corners, merged."""
    return shapes.merge([make(sx, sy) for sx in (1, -1) for sy in (1, -1)])


def along_y(bm, x, z):
    """Lays a part built along Z onto the Y axis, through (x, z)."""
    turn = Matrix.Rotation(math.radians(-90), 3, "X")
    bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=turn, verts=bm.verts)
    return shapes.moved(bm, (x, 0, z))


def pin(x, z, radius, y0, y1, seg=16):
    return along_y(shapes.cone(radius, radius, y0, y1, seg), x, z)


def pins(x, z, radius, y0, y1, seg=16):
    """A pin on each side from |y| = `y0` to `y1`."""
    return mirrored(lambda s: pin(x, z, radius, *sorted((s * y0, s * y1)), seg))


def bar(p0, p1, depth, y0, y1):
    """A flat bar between (x, z) points, `depth` thick in that plane, from `y0` to `y1`."""
    length = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    bm = shapes.box((0, (y0 + y1) / 2, 0), (length, y1 - y0, depth))
    angle = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    turn = Matrix.Rotation(-angle, 3, "Y")
    bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=turn, verts=bm.verts)
    return shapes.moved(bm, ((p0[0] + p1[0]) / 2, 0, (p0[1] + p1[1]) / 2))


def rod(p0, p1, radius, seg=16):
    """A cylinder from point `p0` to `p1`."""
    axis = Vector(p1) - Vector(p0)
    bm = shapes.cone(radius, radius, 0.0, axis.length, seg)
    turn = Vector((0, 0, 1)).rotation_difference(axis.normalized()).to_matrix()
    bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=turn, verts=bm.verts)
    return shapes.moved(bm, p0)


def nut(x, y):
    return shapes.moved(shapes.cone(0.45, 0.45, 0.5, 0.85, seg=6), (x, y, 0))


def chevron(x):
    """A painted arrow head pointing +X, the way the pad throws, with its tip at `x` + 4.5."""
    width, half, tip = 1.8, 6.0, x + 4.5
    left = [(tip, 0), (tip - width, 0), (x - width, half), (x, half)]
    right = [(tip, 0), (x, -half), (x - width, -half), (tip - width, 0)]
    top = DECK_TOP + 0.04
    return shapes.merge([shapes.prism(left, DECK_TOP, top), shapes.prism(right, DECK_TOP, top)])


def part(name, bm, mat, bone, **finish):
    return objects.finish(objects.to_object(name, bm), mat, bone, **finish)


def arm_pair(name, p0, p1, y, bone):
    """Mirrored arms from (x, z) `p0` to `p1` at |y| = `y`, with rounded ends."""
    y0, y1 = y - ARM_WIDTH / 2, y + ARM_WIDTH / 2
    bars = mirrored(lambda s: bar(p0, p1, ARM_DEPTH, *sorted((s * y0, s * y1))))
    ends = [pins(x, z, ARM_DEPTH / 2, y0, y1, 20) for x, z in (p0, p1)]
    return part(name, shapes.merge([bars, *ends]), FRAME, bone, uv_size=24.0, bevel=0.12)


parts = []

# Base: rails on corner blocks with bolted feet, end members, the rams' cross member and clevises.
base = shapes.merge(
    [
        mirrored(lambda s: shapes.box((0, s * 12.7, 2.0), (30.4, RAIL_OUT - RAIL_IN, 2.8))),
        mirrored(lambda s: shapes.box((s * 16.4, 0, 2.0), (2.0, 2 * RAIL_IN, 2.8))),
        at_corners(lambda sx, sy: shapes.box((sx * 16.5, sy * 12.7, 1.95), (2.6, 2.6, 3.9))),
        at_corners(lambda sx, sy: shapes.box((sx * 19.0, sy * 12.7, 0.25), (3.2, 3.0, 0.5))),
        shapes.box((RAM_BASE.x, 0, 1.05), (1.6, 2 * RAIL_IN, 0.9)),
        mirrored(lambda s: shapes.box((RAM_BASE.x, s * (RAM_Y - 0.9), 2.2), (1.6, 0.3, 1.4))),
        mirrored(lambda s: shapes.box((RAM_BASE.x, s * (RAM_Y + 0.9), 2.2), (1.6, 0.3, 1.4))),
    ]
)
parts.append(part("base", base, FRAME, "root", uv_size=24.0, bevel=0.15))
base_steel = shapes.merge(
    [
        at_corners(lambda sx, sy: nut(sx * 19.6, sy * 12.7)),
        mirrored(lambda s: shapes.box((6.0, s * 10.5, 1.6), (20.0, 2.2, 0.4))),
        pin(REAR, BASE_PIN_Z, 0.45, -RAIL_IN, RAIL_IN),
        pins(RAM_BASE.x, RAM_BASE.z, 0.3, RAM_Y - 1.2, RAM_Y + 1.2),
    ]
)
parts.append(part("base_steel", base_steel, STEEL, "root", uv_size=16.0))

# Deck: worn plate with orange arrows inside a hazard-striped rim, over a steel skirt.
plate = shapes.box((0, 0, PLATE_Z), (2 * INSIDE_X, 2 * INSIDE_Y, 1.0))
parts.append(part("deck_plate", plate, DECK, "deck", uv_size=32.0, bevel=0.1))
arrows = shapes.merge([chevron(-4.5), chevron(1.5)])
parts.append(part("arrows", arrows, ARROW, "deck", uv_size=12.0))
rim = shapes.merge(
    [
        mirrored(lambda s: shapes.box((s * RIM_X, 0, PLATE_Z), (BORDER, 2 * DECK_Y, 1.0))),
        mirrored(lambda s: shapes.box((0, s * RIM_Y, PLATE_Z), (2 * INSIDE_X, BORDER, 1.0))),
    ]
)
parts.append(part("rim", rim, HAZARD, "deck", uv_size=12.0, bevel=0.1))
skirt_height = PLATE_Z - 0.5 - DECK_BOTTOM
skirt_z = DECK_BOTTOM + skirt_height / 2
underside = shapes.merge(
    [
        shapes.box((0, 0, skirt_z), (2 * DECK_X - 0.6, 2 * DECK_Y - 0.6, skirt_height)),
        at_corners(lambda sx, sy: shapes.box((sx * 17.95, sy * 13.95, 12.425), (2.3, 2.3, 2.15))),
        mirrored(lambda s: shapes.box((REAR, s * 10.1, 10.45), (2.2, 0.4, 2.1))),
        mirrored(lambda s: shapes.box((REAR, s * 11.7, 10.45), (2.2, 0.4, 2.1))),
        mirrored(lambda s: shapes.box((5.0, s * 10.75, 11.35), (22.0, 1.1, 0.3))),
        pin(REAR, DECK_PIN_Z, 0.45, -11.9, 11.9),
    ]
)
parts.append(part("skirt", underside, STEEL, "deck", uv_size=16.0, bevel=0.12))

# Inner arms, the rams' cross tube, the centre pins and the rollers under the deck.
parts.append(arm_pair("inner_arms", (REAR, BASE_PIN_Z), (FRONT, DECK_PIN_Z), INNER_Y, "arm_a"))
ram_top = arm_point(RAM_ON_ARM, 0.0)
inner_steel = shapes.merge(
    [
        pin(ram_top.x, ram_top.z, 0.55, -(INNER_Y - 0.5), INNER_Y - 0.5),
        pins(REAR + SPAN / 2, (BASE_PIN_Z + DECK_PIN_Z) / 2, 0.5, INNER_Y - 0.7, OUTER_Y + 0.7),
        pin(FRONT, DECK_PIN_Z, 0.4, -11.1, 11.1),
        pins(FRONT, DECK_PIN_Z, WHEEL, 10.4, 11.1, 20),
    ]
)
parts.append(part("inner_steel", inner_steel, STEEL, "arm_a", uv_size=16.0, bevel=0.08))

# Outer arms with the rollers that run on the base ledges.
parts.append(arm_pair("outer_arms", (REAR, DECK_PIN_Z), (FRONT, BASE_PIN_Z), OUTER_Y, "arm_b"))
rollers = shapes.merge(
    [
        pins(FRONT, BASE_PIN_Z, WHEEL, 9.5, 10.3, 20),
        pins(FRONT, BASE_PIN_Z, 0.4, 9.5, 11.5),
    ]
)
parts.append(part("outer_steel", rollers, STEEL, "arm_b", uv_size=16.0, bevel=0.08))

# Rams: a body on the base, a middle stage and a rod whose eye sits on the inner arms' tube.
axis = (ram_top - RAM_BASE).normalized()
middle_top = RAM_BASE + axis * (EYE + BODY + SHOWING)
rod_top = ram_top - axis * EYE


def up_ram(distance):
    return RAM_BASE + axis * distance


def ram(make):
    """`make(at)` for each ram, where `at` moves a point of the XZ plane onto that ram's side."""
    return mirrored(lambda s: make(lambda point: Vector((point.x, s * RAM_Y, point.z))))


barrel = ram(lambda at: rod(at(up_ram(EYE)), at(up_ram(EYE + BODY)), 1.1, 20))
parts.append(part("ram_body", barrel, FRAME, "ram", uv_size=16.0, bevel=0.1))
barrel_steel = shapes.merge(
    [
        ram(lambda at: rod(at(RAM_BASE), at(up_ram(EYE)), 0.55)),
        ram(lambda at: rod(at(up_ram(EYE + BODY - 0.35)), at(up_ram(EYE + BODY + 0.05)), 1.2, 20)),
        pins(RAM_BASE.x, RAM_BASE.z, 0.6, RAM_Y - 0.7, RAM_Y + 0.7),
    ]
)
parts.append(part("ram_body_steel", barrel_steel, STEEL, "ram", uv_size=16.0, bevel=0.06))
middle = ram(lambda at: rod(at(middle_top - axis * STAGE), at(middle_top), 0.75, 20))
parts.append(part("ram_middle", middle, CHROME, "ram_middle", uv_size=8.0))
collar = ram(lambda at: rod(at(middle_top - axis * 0.25), at(middle_top + axis * 0.05), 0.85, 20))
parts.append(part("ram_collar", collar, STEEL, "ram_middle", uv_size=16.0, bevel=0.05))
stage = ram(lambda at: rod(at(rod_top - axis * STAGE), at(rod_top), 0.48, 20))
parts.append(part("ram_rod", stage, CHROME, "ram_rod", uv_size=8.0))
eye = shapes.merge(
    [
        ram(lambda at: rod(at(rod_top), at(ram_top), 0.45)),
        pins(ram_top.x, ram_top.z, 0.6, RAM_Y - 0.7, RAM_Y + 0.7),
    ]
)
parts.append(part("ram_eye", eye, STEEL, "ram_rod", uv_size=16.0, bevel=0.05))

body = objects.join(parts, "jump_pad")


def bone(name, head, toward):
    return (name, tuple(head), tuple(Vector(head) + Vector(toward).normalized() * 3.0), "root")


rest_angle = arm_angle(0.0)
bones = [
    ("root", (0, 0, 0), (0, 0, 3), None),
    bone("deck", (0, 0, DECK_BOTTOM), (0, 0, 1)),
    bone("arm_a", (REAR, 0, BASE_PIN_Z), (math.cos(rest_angle), 0, math.sin(rest_angle))),
    bone("arm_b", (REAR, 0, DECK_PIN_Z), (math.cos(rest_angle), 0, -math.sin(rest_angle))),
    bone("ram", RAM_BASE, axis),
    bone("ram_middle", middle_top, axis),
    bone("ram_rod", ram_top, axis),
]
arm = rig.skeleton("jump_pad_skeleton", bones, [body])
hull = shapes.box((0, 0, DECK_TOP / 2), (2 * DECK_X, 2 * DECK_Y, DECK_TOP))
objects.hull("jump_pad_hull", hull, FRAME)


def pose(lift):
    """(move, turn) per moving bone with the deck `lift` above rest; the linkage stays shut."""
    turn = math.degrees(arm_angle(lift) - rest_angle)
    top = arm_point(RAM_ON_ARM, lift)
    toward = (top - RAM_BASE).normalized()
    tilt = math.degrees(math.atan2(toward.z, toward.x) - math.atan2(axis.z, axis.x))
    stretch = ((top - RAM_BASE).length - (ram_top - RAM_BASE).length) / 2
    stage_top = RAM_BASE + toward * (EYE + BODY + SHOWING + stretch)
    return {
        "deck": ((0, 0, lift), (0, 0, 0)),
        "arm_a": ((0, 0, 0), (0, -turn, 0)),
        "arm_b": ((0, 0, lift), (0, turn, 0)),
        "ram": ((0, 0, 0), (0, -tilt, 0)),
        "ram_middle": (tuple(stage_top - middle_top), (0, -tilt, 0)),
        "ram_rod": (tuple(top - ram_top), (0, -tilt, 0)),
    }


def tracks(lifts):
    keys = {}
    for frame, lift in lifts:
        for name, (move, turn) in pose(lift).items():
            keys.setdefault(name, []).append((frame, move, turn))
    return keys


idle = [(frame, 0.5 - 0.5 * math.cos(math.pi * frame / 30)) for frame in range(61)]
rig.animate(arm, "jump_pad_idle", tracks(idle))
# The plugin throws the player on first contact, so the deck kicks from the first frame.
launch = [(0, 0.0), (1, 7.0), (2, 14.5), (3, 18.5), (4, HIGHEST), (7, 16.8), (10, 17.6)]
launch += [(13, 16.5), (18, 6.0), (21, 0.0), (23, LOWEST), (26, 0.6), (29, -0.2), (32, 0.0)]
rig.animate(arm, "jump_pad_launch", tracks(rig.eased(launch)))
rig.show(arm, "jump_pad_idle")
# Action names are shared by every scene in the session, so they carry the model's name.
source2.remember(
    "jump_pad",
    model="jump_pad",
    armature="jump_pad_skeleton",
    actions=("jump_pad_idle", "jump_pad_launch"),
    files={"jump_pad": "jump_pad_jump_pad"},
)
preview.stage()

result = {
    "tris": sum(len(p.vertices) - 2 for p in body.data.polygons),
    "size": [round(v, 2) for v in body.dimensions],
}
