"""Shapes as bmesh parts, before they become objects."""

import math
from collections.abc import Iterable, Sequence

import bmesh
import bpy
from mathutils import Matrix, Vector

type Vec3 = tuple[float, float, float] | Vector


def cone(r0: float, r1: float, z0: float, z1: float, seg: int = 64) -> bmesh.types.BMesh:
    """A capped cylinder or frustum from `z0` to `z1`."""
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=seg,
        radius1=r0,
        radius2=r1,
        depth=z1 - z0,
        matrix=Matrix.Translation((0, 0, (z0 + z1) / 2)),
    )
    return bm


def tube(r_in: float, r_out: float, z0: float, z1: float, seg: int = 64) -> bmesh.types.BMesh:
    """A closed ring."""
    return sector(r_in, r_out, 0.0, 360.0, z0, z1, seg, closed=True)


def sector(
    r_in: float,
    r_out: float,
    a0: float,
    a1: float,
    z0: float,
    z1: float,
    seg: int = 6,
    closed: bool = False,
) -> bmesh.types.BMesh:
    """A curved block between angles `a0` and `a1` degrees."""
    bm = bmesh.new()
    count = seg if closed else seg + 1
    angles = [math.radians(a0 + (a1 - a0) * i / seg) for i in range(count)]
    rings = [
        [bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for a in angles]
        for r, z in ((r_out, z0), (r_out, z1), (r_in, z1), (r_in, z0))
    ]
    for k in range(4):
        a, b = rings[k], rings[(k + 1) % 4]
        for i in range(seg):
            j = (i + 1) % count
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if not closed:
        for index in (0, -1):
            face = [rings[k][index] for k in range(4)]
            bm.faces.new(face if index else list(reversed(face)))
    return bm


def prism(points: Sequence[tuple[float, float]], z0: float, z1: float) -> bmesh.types.BMesh:
    """A convex outline of (x, y) points extruded from `z0` to `z1`."""
    bm = bmesh.new()
    bottom = [bm.verts.new((x, y, z0)) for x, y in points]
    top = [bm.verts.new((x, y, z1)) for x, y in points]
    bm.faces.new(top)
    bm.faces.new(list(reversed(bottom)))
    for i in range(len(points)):
        j = (i + 1) % len(points)
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    return bm


def box(center: Vec3, size: Vec3, yaw: float = 0.0) -> bmesh.types.BMesh:
    """A box of `size` (x, y, z) at `center`, turned `yaw` degrees about Z."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    turn = Matrix.Rotation(math.radians(yaw), 3, "Z")
    bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=turn, verts=bm.verts)
    bmesh.ops.translate(bm, vec=center, verts=bm.verts)
    return bm


def radial_box(
    radius: float, angle: float, size: tuple[float, float], z0: float, z1: float
) -> bmesh.types.BMesh:
    """A box centred `radius` out along `angle` degrees; `size` is (radial, tangential)."""
    a = math.radians(angle)
    center = (radius * math.cos(a), radius * math.sin(a), (z0 + z1) / 2)
    return box(center, (size[0], size[1], z1 - z0), angle)


def moved(bm: bmesh.types.BMesh, offset: Vec3) -> bmesh.types.BMesh:
    bmesh.ops.translate(bm, vec=offset, verts=bm.verts)
    return bm


def around(radius: float, angles: Iterable[float]) -> list[tuple[float, float, float]]:
    """(x, y, 0) offsets at `radius` for each angle in degrees."""
    return [
        (radius * math.cos(math.radians(a)), radius * math.sin(math.radians(a)), 0) for a in angles
    ]


def bolts(
    radius: float, angles: Iterable[float], size: float, z0: float, z1: float
) -> bmesh.types.BMesh:
    """Hex bolt heads of radius `size` on a circle, one per angle in degrees."""
    return merge(moved(cone(size, size, z0, z1, seg=6), at) for at in around(radius, angles))


def merge(bms: Iterable[bmesh.types.BMesh]) -> bmesh.types.BMesh:
    out = bmesh.new()
    for bm in bms:
        mesh = bpy.data.meshes.new("merge")
        bm.to_mesh(mesh)
        out.from_mesh(mesh)
        bpy.data.meshes.remove(mesh)
        bm.free()
    return out


def spring(
    radius: float,
    wire: float,
    turns: int,
    z0: float,
    z1: float,
    steps_per_turn: int = 32,
    sides: int = 8,
) -> tuple[bmesh.types.BMesh, list[float]]:
    """A coil, and per vertex how far along it the vertex is (0 bottom, 1 top), for bind_along."""
    bm = bmesh.new()
    along = []
    steps = turns * steps_per_turn
    rings = []
    up = Vector((0, 0, 1))
    for i in range(steps + 1):
        t = i / steps
        a = 2 * math.pi * turns * t
        centre = Vector((radius * math.cos(a), radius * math.sin(a), z0 + (z1 - z0) * t))
        outward = Vector((math.cos(a), math.sin(a), 0))
        circle = (2 * math.pi * k / sides for k in range(sides))
        rings.append(
            [
                bm.verts.new(centre + wire * (math.cos(s) * outward + math.sin(s) * up))
                for s in circle
            ]
        )
        along += [t] * sides
    for a, b in zip(rings, rings[1:]):
        for k in range(sides):
            bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    return bm, along
