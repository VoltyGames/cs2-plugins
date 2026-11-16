"""A throwaway scene for background renders: parts gathered from their scenes, posed at their
idle, lit, with a camera that circles them. Leaving the `with` block removes everything it
added; the parts stay in their own scenes."""

import math
import os
import re
from collections.abc import Iterable, Iterator, Sequence
from typing import Self

import bpy
import numpy as np
from mathutils import Vector

# Objects that never render: collision hulls and the live session's preview rig.
SKIPPED = re.compile("hull|phys|collision|preview", re.IGNORECASE)
PREFIX = "modelkit_stage"
THREE_QUARTER = (1.0, -0.85, 0.38)

type Direction = tuple[float, float, float] | Vector


def find_render_meshes() -> Iterator[tuple[bpy.types.Scene, bpy.types.Object]]:
    """(scene, object) for each mesh that renders, each mesh data once."""
    seen = set()
    for scene in bpy.data.scenes:
        for ob in scene.objects:
            if ob.type == "MESH" and not SKIPPED.search(ob.name) and ob.data.name not in seen:
                seen.add(ob.data.name)
                yield scene, ob


def find_idle(scene_name: str) -> bpy.types.Action | None:
    """The scene's own idle, named after the scene or the end of its name (`level1_idle` for
    scene `turret_level1`), else the file's first idle."""
    idles = {a.name.removesuffix("_idle"): a for a in bpy.data.actions if a.name.endswith("_idle")}
    owners = [name for name in idles if scene_name == name or scene_name.endswith(f"_{name}")]
    if owners:
        return idles[max(owners, key=len)]
    return next((a for a in bpy.data.actions if re.search(r"(^|_)idle$", a.name)), None)


class Stage:
    """`with Stage(scene_names, size) as stage:` then aim and render."""

    def __init__(
        self,
        scene_names: Iterable[str],
        size: tuple[int, int] = (1600, 1000),
        at: dict[str, Sequence[float]] | None = None,
    ) -> None:
        self.scene_names = list(scene_names)
        self.size = size
        self.at = at or {}

    def __enter__(self) -> Self:
        self.scene = bpy.data.scenes.new(PREFIX)
        self.gather()
        self.low, self.high = self.measure_bounds()
        self.light()
        return self

    def __exit__(self, *failure: object) -> None:
        for ob in list(self.scene.objects):
            if ob.name.startswith(PREFIX):
                bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.scenes.remove(self.scene)
        for blocks in (
            bpy.data.meshes,
            bpy.data.materials,
            bpy.data.cameras,
            bpy.data.lights,
            bpy.data.worlds,
        ):
            for block in [b for b in blocks if b.name.startswith(PREFIX)]:
                blocks.remove(block)

    @property
    def parts(self) -> list[str]:
        names = (ob.name for ob in self.scene.objects if ob.type == "MESH")
        return sorted(name for name in names if not name.startswith(PREFIX))

    def gather(self) -> None:
        """Links the scenes' armatures and meshes, each part posed at its own scene's idle;
        `at` moves a part's root."""
        for name in self.scene_names:
            idle = find_idle(name)
            for ob in bpy.data.scenes[name].objects:
                if ob.type not in {"MESH", "ARMATURE"} or SKIPPED.search(ob.name):
                    continue
                if ob.parent is None and name in self.at:
                    ob.location = Vector(self.at[name])
                if ob.name not in self.scene.collection.objects:
                    self.scene.collection.objects.link(ob)
                if ob.type == "ARMATURE" and idle:
                    ob.animation_data_create()
                    ob.animation_data.action = idle
                    if slots := ob.animation_data.action_suitable_slots:
                        ob.animation_data.action_slot = slots[0]
        self.scene.frame_set(0)

    def measure_bounds(self) -> tuple[Vector, Vector]:
        """The posed parts' world-space bounding box."""
        # The stage's own graph: the context's belongs to the file's active scene.
        graph = self.scene.view_layers[0].depsgraph
        graph.update()
        points = []
        for ob in self.scene.objects:
            if ob.type == "MESH":
                evaluated = ob.evaluated_get(graph)
                mesh = evaluated.to_mesh()
                local = np.empty(len(mesh.vertices) * 3)
                mesh.vertices.foreach_get("co", local)
                evaluated.to_mesh_clear()
                matrix = np.array(evaluated.matrix_world)
                points.append(local.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3])
        stacked = np.concatenate(points)
        return Vector(stacked.min(axis=0)), Vector(stacked.max(axis=0))

    def add(self, name: str, data: bpy.types.ID) -> bpy.types.Object:
        ob = bpy.data.objects.new(f"{PREFIX}_{name}", data)
        self.scene.collection.objects.link(ob)
        return ob

    def light(self) -> None:
        """Adds a sun, a sky, a ground and a camera."""
        reach = (self.high - self.low).length * 3
        center = (self.low + self.high) / 2
        camera = self.add("camera", bpy.data.cameras.new(f"{PREFIX}_camera"))
        camera.data.lens = 35
        self.scene.camera = camera
        sun = self.add("sun", bpy.data.lights.new(f"{PREFIX}_sun", "SUN"))
        sun.data.energy, sun.data.color = 4.0, (1.0, 0.95, 0.85)
        sun.data.angle = math.radians(2)
        sun.rotation_euler = (math.radians(50), 0, math.radians(35))
        mesh = bpy.data.meshes.new(f"{PREFIX}_ground")
        corners = [(-reach, -reach, 0), (reach, -reach, 0), (reach, reach, 0), (-reach, reach, 0)]
        mesh.from_pydata(corners, [], [(0, 1, 2, 3)])
        material = bpy.data.materials.new(f"{PREFIX}_ground")
        material.use_nodes = True
        shader = material.node_tree.nodes["Principled BSDF"]
        shader.inputs["Base Color"].default_value = (0.42, 0.36, 0.28, 1)
        shader.inputs["Roughness"].default_value = 0.95
        mesh.materials.append(material)
        self.add("ground", mesh).location = (center.x, center.y, self.low.z)
        world = bpy.data.worlds.new(f"{PREFIX}_world")
        world.use_nodes = True
        background = world.node_tree.nodes["Background"]
        background.inputs[0].default_value = (0.55, 0.62, 0.72, 1)
        background.inputs[1].default_value = 0.9
        self.scene.world = world
        self.scene.render.engine = "BLENDER_EEVEE"
        self.scene.render.resolution_x, self.scene.render.resolution_y = self.size
        self.scene.view_settings.view_transform = "AgX"

    def aim(self, direction: Direction, distance: float = 1.7) -> None:
        """Points the camera at the parts from `direction`, `distance` times their size away."""
        center = (self.low + self.high) / 2
        camera = self.scene.camera
        reach = (self.high - self.low).length * distance
        camera.location = center + Vector(direction).normalized() * reach
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()

    def render(self, path: str) -> str:
        self.scene.render.filepath = path
        bpy.ops.render.render(write_still=True, scene=self.scene.name)
        return path

    def render_around(
        self, directions: Iterable[Direction], folder: str, name: str, distance: float = 1.7
    ) -> list[str]:
        """Renders `<name>_<index>.png` into `folder` from each direction."""
        paths = []
        for index, direction in enumerate(directions):
            self.aim(direction, distance)
            paths.append(self.render(os.path.join(folder, f"{name}_{index}.png")))
        return paths
