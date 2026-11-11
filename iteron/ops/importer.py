# SPDX-License-Identifier: MIT
"""File ▸ Import ▸ Fractals: Fractalchemy's `.fa` flames and `.fa3d` scenes (flame, camera, lights, world),
Apophysis / flam3 `.flame` files, and `.fafrag` / `.frag` fragments (see ops/fragments.py). Options sit in the file
browser's side panel — no extra window."""

import json
from pathlib import Path

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ImportHelper
from mathutils import Matrix, Vector

from ..bridge import material
from ..flames import formats
from ..flames.flame_xml import read_flame
from .add import add_flame, build_first

FLAME_SPACING = 4.0          # several flames from one file are placed side by side


def import_flames(context, flames: list, all_flames: bool, index: int = 1) -> list:
    """Flame objects for `flames` (all side by side, or the one at 1-based `index`)."""
    if not all_flames:
        flames = [flames[min(max(index, 1), len(flames)) - 1]]
    objects = []
    origin = Vector(context.scene.cursor.location)
    for number, flame in enumerate(flames):
        context.scene.cursor.location = origin + Vector((number * FLAME_SPACING, 0.0, 0.0))
        objects.append(add_flame(context, flame.to_dict()))
    context.scene.cursor.location = origin
    return objects


def import_fa(context, path: Path, all_flames: bool, index: int = 1) -> list:
    return import_flames(context, formats.read_fa(path), all_flames, index)


def import_flame_file(context, path: Path, all_flames: bool, index: int = 1) -> list:
    return import_flames(context, read_flame(path), all_flames, index)


def import_fa3d(context, path: Path, camera: bool, lights: bool, world: bool):
    scene = formats.read_fa3d(path)
    mesh = scene.mesh
    obj = add_flame(context, scene.flame.to_dict(), "MESH" if scene.solid else "POINTS",
                    points=int(mesh.get("points", 1_000_000)), threshold=float(mesh.get("threshold", 0.15)),
                    smoothing=float(mesh.get("smoothing", 1.0)))
    obj.iteron.final_resolution = int(mesh.get("resolution", 256))
    material.set_surface(material.ensure_flame(obj), *scene.surface())
    f = obj.iteron.flame
    f.materials = json.dumps(scene.materials)
    f.per_transform = scene.distinct_materials
    if apply_instancer(f.instancer, scene.instancer()):
        build_first(obj)
    if camera:
        add_camera(context, obj, formats.camera_frame(scene.flame.camera))
    if lights:
        for index, light in enumerate(scene.lights):
            add_light(context, obj, light, index)
    if world:
        set_world(context, scene)
    return obj


SHAPES = {"sphere": "SPHERE", "cube": "CUBE", "icosahedron": "ICOSAHEDRON", "tetrahedron": "TETRAHEDRON",
          "torus": "TORUS", "cylinder": "CYLINDER"}


def apply_instancer(settings, found: dict | None) -> bool:
    """A `.fa3d` instancer as the flame's holons (its own IFS too); mesh-file and DLA assets become spheres."""
    if found is None:
        return False
    settings.mode = "TREE" if found.get("mode") == "tree" else "CHAOS"
    settings.frames = "TRANSLATION" if found.get("frame_mode") == "translation" else "JACOBIAN"
    settings.leaves_only = found.get("tree_levels") == "leaves"
    for key, name, kind in (("count", "count", int), ("depth", "depth", int), ("size", "size", float),
                            ("size_falloff", "falloff", float), ("min_size", "min_size", float),
                            ("max_instances", "cap", int), ("seed", "seed", int)):
        if key in found:
            setattr(settings, name, kind(found[key]))
    settings.shape = SHAPES.get(found.get("primitive") or "", "SPHERE")
    settings.palette = found.get("color_mode", "palette") == "palette"
    settings.source = json.dumps(found["flame"]) if found.get("source") == "own" and found.get("flame") else ""
    settings.enabled = True
    return True


def add_camera(context, obj, frame: formats.CameraFrame):
    data = bpy.data.cameras.new(f"{obj.name} Camera")
    camera = bpy.data.objects.new(data.name, data)
    context.collection.objects.link(camera)
    camera.matrix_world = obj.matrix_world @ Matrix(frame.matrix().tolist())
    if frame.perspective:
        data.type, data.sensor_fit, data.angle = "PERSP", "HORIZONTAL", frame.fov
    else:
        data.type, data.ortho_scale = "ORTHO", frame.ortho_width
    data.clip_start, data.clip_end = max(0.001, frame.distance * 0.01), frame.distance * 100.0
    context.scene.camera = camera
    context.scene.render.resolution_x, context.scene.render.resolution_y = frame.width, frame.height
    return camera


def add_light(context, obj, light: formats.Light, index: int):
    if light.kind == "point":
        data = bpy.data.lights.new(f"{obj.name} Point Light {index + 1}", "POINT")
        data.energy = light.intensity * 50.0 * light.radius ** 2
        data.shadow_soft_size = light.radius * 0.1
        lamp = bpy.data.objects.new(data.name, data)
        lamp.location = obj.matrix_world @ Vector(light.position.tolist())
    else:
        data = bpy.data.lights.new(f"{obj.name} Sun {index + 1}", "SUN")
        data.energy = light.intensity * 3.0
        data.use_shadow = light.shadows
        lamp = bpy.data.objects.new(data.name, data)
        direction = (obj.matrix_world.to_3x3() @ Vector(light.direction.tolist())).normalized()
        lamp.location = obj.matrix_world.translation + direction * 5.0
        lamp.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    data.color = light.colour
    context.collection.objects.link(lamp)
    return lamp


def set_world(context, scene: formats.Scene) -> None:
    world = context.scene.world or bpy.data.worlds.new("World")
    context.scene.world = world
    world.color = scene.background
    if world.node_tree is None and bpy.app.version < (5, 0, 0):
        world.use_nodes = True
    background = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None) if world.node_tree else None
    if background is not None:
        background.inputs["Color"].default_value = (*scene.background, 1.0)
        background.inputs["Strength"].default_value = scene.ambient
    context.scene.render.film_transparent = not scene.background_visible


class ITERON_OT_import_fractalchemy(bpy.types.Operator, ImportHelper):
    """Import flames (Fractalchemy .fa, Apophysis .flame), Fractalchemy 3D scenes (.fa3d) or fragments (.fafrag,
    .frag)"""
    bl_idname = "iteron.import_fractalchemy"
    bl_label = "Import Fractals"
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(default="*.fa;*.fa3d;*.flame;*.fafrag;*.frag", options={"HIDDEN"})
    all_flames: BoolProperty(name="Every Flame in the File", default=True,
                             description=".fa and .flame files: import all their flames side by side")
    flame_index: IntProperty(name="Flame", default=1, min=1,
                             description="Which flame of the file to import when not importing every flame")
    camera: BoolProperty(name="Camera", default=True,
                         description=".fa3d scenes and fragments: add the camera the file was saved with")
    lights: BoolProperty(name="Lights", default=True, description=".fa3d scenes: add the scene's lights")
    world: BoolProperty(name="World", default=True, description=".fa3d scenes: set the world's colour")

    def execute(self, context):
        path = Path(self.filepath)
        suffix = path.suffix.lower()
        try:
            if suffix == ".fa":
                import_fa(context, path, self.all_flames, self.flame_index)
            elif suffix == ".flame":
                import_flame_file(context, path, self.all_flames, self.flame_index)
            elif suffix == ".fa3d":
                import_fa3d(context, path, self.camera, self.lights, self.world)
            elif suffix in (".fafrag", ".frag"):
                from .fragments import import_fragment
                import_fragment(context, path, self.camera)
            else:
                self.report({"ERROR"}, f"Not a file Iteron opens: {path.name}")
                return {"CANCELLED"}
        except (formats.FormatError, ValueError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}


def _menu(self, _context):
    self.layout.operator(ITERON_OT_import_fractalchemy.bl_idname, text="Fractals (.fa, .fa3d, .flame, .frag, .fafrag)")


classes = (ITERON_OT_import_fractalchemy,)


def register_extra() -> None:
    bpy.types.TOPBAR_MT_file_import.append(_menu)


def unregister_extra() -> None:
    bpy.types.TOPBAR_MT_file_import.remove(_menu)


__all__ = ["import_fa", "import_fa3d", "import_flame_file", "import_flames"]
