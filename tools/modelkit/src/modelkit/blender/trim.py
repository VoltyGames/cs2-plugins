"""Triangles a mesh can lose without looking different: degenerate faces, coplanar faces that
merge without breaking a UV, material, sharp edge or bone weight, and faces nothing can see.

Only faces that move together can hide each other: a part in another scene, or on another bone,
moves away and shows what it covered. The source game culls back faces, so a face counts as
seen only from its front.
"""

import math
from collections.abc import Collection

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

FLAT = math.radians(0.1)
DIRECTIONS = 160
SAMPLES = (0.0, 0.7)  # the face centre, then points 70% of the way to each corner
EPSILON = 1e-3

type WeightsKey = tuple[tuple[int, float], ...]


def triangle_count(bm: bmesh.types.BMesh) -> int:
    return sum(len(f.verts) - 2 for f in bm.faces)


def directions(count: int = DIRECTIONS) -> list[Vector]:
    """Evenly spread unit vectors over the sphere (a Fibonacci lattice)."""
    golden = math.pi * (3 - math.sqrt(5))
    out = []
    for i in range(count):
        z = 1 - 2 * (i + 0.5) / count
        r = math.sqrt(1 - z * z)
        out.append(Vector((r * math.cos(golden * i), r * math.sin(golden * i), z)))
    return out


def weights_key(bm: bmesh.types.BMesh, vert: bmesh.types.BMVert) -> WeightsKey:
    layer = bm.verts.layers.deform.active
    if layer is None:
        return ()
    return tuple(sorted((g, round(w, 3)) for g, w in vert[layer].items() if w > 0))


def rigid_key(bm: bmesh.types.BMesh, face: bmesh.types.BMFace) -> WeightsKey | None:
    """What the face moves with: its vertices' shared bone weights, or None when they differ,
    as on a bending part."""
    keys = {weights_key(bm, v) for v in face.verts}
    return keys.pop() if len(keys) == 1 else None


def find_hidden(bm: bmesh.types.BMesh) -> list[bmesh.types.BMFace]:
    """Faces no camera outside the mesh can see the front of."""
    bm.faces.ensure_lookup_table()
    groups = {}
    for face in bm.faces:
        key = rigid_key(bm, face)
        if key is not None:
            groups.setdefault(key, []).append(face)
    hidden = []
    sphere = directions()
    for faces in groups.values():
        index_of = {face.index: i for i, face in enumerate(faces)}
        verts = sorted({v for f in faces for v in f.verts}, key=lambda v: v.index)
        position = {v.index: i for i, v in enumerate(verts)}
        tree = BVHTree.FromPolygons(
            [v.co for v in verts], [[position[v.index] for v in f.verts] for f in faces]
        )
        lo = Vector(min(v.co[i] for v in verts) for i in range(3))
        hi = Vector(max(v.co[i] for v in verts) for i in range(3))
        reach = (hi - lo).length + 1.0
        for face in faces:
            if face.calc_area() < 1e-8:
                continue
            centre = face.calc_center_median()
            points = [centre.lerp(v.co, t) for v in face.verts for t in SAMPLES if t] + [centre]
            if not any(
                seen(tree, index_of[face.index], p, face.normal, sphere, reach) for p in points
            ):
                hidden.append(face)
    return hidden


def seen(
    tree: BVHTree,
    target: int,
    point: Vector,
    normal: Vector,
    sphere: list[Vector],
    reach: float,
) -> bool:
    lifted = point + normal * EPSILON
    for d in sphere:
        if d.dot(normal) <= 0.05:
            continue
        _, _, index, distance = tree.ray_cast(lifted + d * reach, -d, reach * 2)
        if index is None or index == target or distance >= reach - EPSILON * 10:
            return True
    return False


def mark_weight_borders(bm: bmesh.types.BMesh) -> list[bmesh.types.BMEdge]:
    """Seams on edges whose ends follow different bones, so a dissolve keeps them; returns the
    edges marked, to clear after."""
    marked = []
    for edge in bm.edges:
        a, b = edge.verts
        if not edge.seam and weights_key(bm, a) != weights_key(bm, b):
            edge.seam = True
            marked.append(edge)
    return marked


def merge_coplanar(bm: bmesh.types.BMesh) -> None:
    """Dissolves coplanar faces into polygons, then triangulates those again."""
    marked = mark_weight_borders(bm)
    delimit = {"NORMAL", "MATERIAL", "SEAM", "SHARP", "UV"}
    bmesh.ops.dissolve_limit(
        bm, angle_limit=FLAT, verts=list(bm.verts), edges=list(bm.edges), delimit=delimit
    )
    for edge in marked:
        if edge.is_valid:
            edge.seam = False
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    bmesh.ops.triangulate(bm, faces=ngons, quad_method="BEAUTY", ngon_method="BEAUTY")


def trim(mesh: bpy.types.Mesh, operations: Collection[str]) -> dict[str, int]:
    """Applies `operations` ("degenerate", "coplanar", "hidden") to `mesh`; returns the
    triangles each removed."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    removed = {}
    if "degenerate" in operations:
        before = triangle_count(bm)
        bmesh.ops.dissolve_degenerate(bm, dist=1e-4, edges=list(bm.edges))
        removed["degenerate"] = before - triangle_count(bm)
    if "hidden" in operations:
        before = triangle_count(bm)
        bmesh.ops.delete(bm, geom=find_hidden(bm), context="FACES_ONLY")
        loose = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
        removed["hidden"] = before - triangle_count(bm)
    if "coplanar" in operations and not mesh.has_custom_normals:
        before = triangle_count(bm)
        merge_coplanar(bm)
        removed["coplanar"] = before - triangle_count(bm)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return removed
