"""A part's bake atlas: its UV layer, the faces it covers and where a mark lands on it."""

from collections.abc import Collection
from typing import Any

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
from numpy.typing import NDArray

from modelkit.blender import measure

ATLAS_UV = "atlas"

type Floats = NDArray[np.float64]


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


def find_slots(mesh: bpy.types.Mesh, materials: Collection[str]) -> set[int]:
    """The material slot indices holding one of `materials`."""
    return {i for i, m in enumerate(mesh.materials) if m and m.name in materials}


def read_triangles(
    ob: bpy.types.Object, uv_name: str | None = None, world: bool = True
) -> tuple[Floats, Floats, NDArray[np.int64]]:
    """Points (n, 3, 3), UVs (n, 3, 2) and material slots (n) of a mesh's triangles."""
    mesh = ob.data.copy()
    if world:
        mesh.transform(ob.matrix_world)
    mesh.calc_loop_triangles()
    count = len(mesh.loop_triangles)
    coords = np.empty(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", coords)
    uv = np.empty(len(mesh.loops) * 2)
    layer = mesh.uv_layers[uv_name] if uv_name else mesh.uv_layers.active
    layer.data.foreach_get("uv", uv)
    verts = np.empty(count * 3, dtype=np.int64)
    mesh.loop_triangles.foreach_get("vertices", verts)
    loops = np.empty(count * 3, dtype=np.int64)
    mesh.loop_triangles.foreach_get("loops", loops)
    slots = np.empty(count, dtype=np.int64)
    mesh.loop_triangles.foreach_get("material_index", slots)
    bpy.data.meshes.remove(mesh)
    points = coords.reshape(-1, 3)[verts.reshape(-1, 3)]
    return points, uv.reshape(-1, 2)[loops.reshape(-1, 3)], slots


def measure_density(ob: bpy.types.Object, materials: Collection[str]) -> float:
    """The atlas's pixels per Blender unit per pixel of texture width over `materials`' faces."""
    points, uvs, slots = read_triangles(ob, ATLAS_UV, world=False)
    chosen = np.isin(slots, list(find_slots(ob.data, materials)))
    return measure.summarize(points[chosen], uvs[chosen])["density"]


def make_atlas(ob: bpy.types.Object, materials: Collection[str], margin: float = 0.004) -> None:
    """Adds the active atlas UV layer: `materials`' faces unwrapped and packed, every other face
    keeping its old UVs."""
    mesh = ob.data
    if ATLAS_UV not in mesh.uv_layers:
        mesh.uv_layers.new(name=ATLAS_UV)  # starts as a copy of the active layer
    mesh.uv_layers.active = mesh.uv_layers[ATLAS_UV]
    chosen = find_slots(mesh, materials)
    # Without an image in the materials, the UV operators don't stretch islands to its aspect.
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
        # Packing moves only selected UVs; a saved UV selection would leave islands unpacked.
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.pack_islands(rotate=True, margin=margin, shape_method="CONCAVE")
        bpy.ops.object.mode_set(mode="OBJECT")
    for index, material in enumerate(saved):
        mesh.materials[index] = material
    bpy.data.materials.remove(blank)


def shrink_atlas(ob: bpy.types.Object, materials: Collection[str], share: float) -> None:
    """Scales `materials`' atlas faces toward the bottom-left corner, freeing `share` of the
    atlas along its top and right edges."""
    mesh = ob.data
    polygons = {}
    for attribute in ("material_index", "loop_start", "loop_total"):
        polygons[attribute] = np.empty(len(mesh.polygons), dtype=np.int64)
        mesh.polygons.foreach_get(attribute, polygons[attribute])
    chosen = np.isin(polygons["material_index"], list(find_slots(mesh, materials)))
    starts, totals = polygons["loop_start"][chosen], polygons["loop_total"][chosen]
    # Each chosen polygon's loops: its start plus 0..total-1.
    offsets = np.arange(totals.sum()) - np.repeat(np.cumsum(totals) - totals, totals)
    loops = np.repeat(starts, totals) + offsets
    layer = mesh.uv_layers[ATLAS_UV].data
    uv = np.empty(len(mesh.loops) * 2)
    layer.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    uv[loops] *= 1.0 - share
    layer.foreach_set("uv", uv.ravel())


def make_bake_copy(ob: bpy.types.Object, materials: Collection[str]) -> bpy.types.Object:
    """A copy of `ob` holding only `materials`' faces, linked into the same scene."""
    copy = ob.copy()
    copy.data = ob.data.copy()
    copy.name = f"{ob.name}_bake"
    ob.users_scene[0].collection.objects.link(copy)
    keep = find_slots(copy.data, materials)
    bm = bmesh.new()
    bm.from_mesh(copy.data)
    bmesh.ops.delete(
        bm, geom=[f for f in bm.faces if f.material_index not in keep], context="FACES"
    )
    bm.to_mesh(copy.data)
    bm.free()
    return copy


class MarkPlacer:
    """Finds where marks land in one part's UV layer: the UV under a point on the surface, and
    the UV step for one unit right and up along the face there."""

    def __init__(self, ob: bpy.types.Object, uv_name: str = ATLAS_UV) -> None:
        self.ob = ob
        self.mesh = ob.data
        self.layer = self.mesh.uv_layers[uv_name]
        self.mesh.calc_loop_triangles()
        self.trees: dict[str | None, tuple[BVHTree, list[bpy.types.MeshLoopTriangle]]] = {}

    def find_tree(self, surface: str | None) -> tuple[BVHTree, list[bpy.types.MeshLoopTriangle]]:
        if surface not in self.trees:
            tris = [
                tri
                for tri in self.mesh.loop_triangles
                if surface is None or self.mesh.materials[tri.material_index].name == surface
            ]
            if not tris:
                raise ValueError(f"no faces of {surface} on {self.ob.name} for a mark")
            corners = [v.co for v in self.mesh.vertices]
            self.trees[surface] = (BVHTree.FromPolygons(corners, [t.vertices for t in tris]), tris)
        return self.trees[surface]

    def place(
        self, point: list[float], surface: str | None = None, along: list[float] | None = None
    ) -> dict[str, Any]:
        """`surface`, a material name, keeps the mark on its faces; `along` turns the text,
        which otherwise runs level across the face."""
        tree, tris = self.find_tree(surface)
        target = self.ob.matrix_world.inverted() @ Vector(point)
        on_face, _, index, _ = tree.find_nearest(target)
        nearest = tris[index]
        corners = [self.mesh.vertices[v].co for v in nearest.vertices]
        uvs = [self.layer.data[loop].uv.to_3d() for loop in nearest.loops]
        right = Vector(along) if along else Vector((0, 0, 1)).cross(nearest.normal)
        right = right.normalized() if right.length > 1e-3 else Vector((1, 0, 0))
        up = nearest.normal.cross(right).normalized()

        def to_uv(position: Vector) -> Vector:
            return barycentric_transform(position, *corners, *uvs).to_2d()

        origin = to_uv(on_face)
        return {
            "uv": list(origin),
            "right": list(to_uv(on_face + right) - origin),
            "up": list(to_uv(on_face + up) - origin),
            "material": self.mesh.materials[nearest.material_index].name,
        }
