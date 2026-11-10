# SPDX-License-Identifier: MIT
"""What the render tools share: a lit EEVEE scene, a camera that frames a mesh, and building a formula's default."""

import math
import sys
from pathlib import Path

import bpy
import mathutils
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
VIEW = mathutils.Vector((1.0, -1.25, 0.85)).normalized()


def setup_scene(pixels: int, transparent: bool = True):
    """An empty scene with EEVEE, two sun lights and a camera; renders once so the `gpu` module can draw."""
    scene = bpy.context.scene
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = pixels
    scene.render.film_transparent = transparent
    scene.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    scene.world = scene.world or bpy.data.worlds.new("World")
    set_background(scene.world, (0.012, 0.012, 0.02))
    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    for name, energy, angles in (("Key", 4.0, (50, 0, 35)), ("Fill", 1.2, (70, 0, -120))):
        light = bpy.data.objects.new(name, bpy.data.lights.new(name, "SUN"))
        light.data.energy = energy
        light.rotation_euler = tuple(math.radians(a) for a in angles)
        scene.collection.objects.link(light)
    bpy.ops.render.render()
    return scene, camera


def set_background(world, colour) -> None:
    """The world colour, through its Background node when it has one (always in Blender 5)."""
    world.color = colour
    if world.node_tree is None and bpy.app.version < (5, 0, 0):
        world.use_nodes = True
    background = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None) if world.node_tree else None
    if background is not None:
        background.inputs["Color"].default_value = (*colour, 1.0)


def frame(camera, obj, distance: float = 1.55) -> None:
    """Point the camera at the mesh from `VIEW`, far enough to see all of it."""
    co = np.zeros(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    lo, hi = co.min(axis=0), co.max(axis=0)
    center = mathutils.Vector((lo + hi) / 2)
    camera.data.lens = 50
    camera.location = center + VIEW * float(np.linalg.norm(hi - lo)) * distance
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()


def build_default(formula_id: str, resolution: int):
    """Add the formula's default fractal and build it at `resolution` (final quality)."""
    from iteron.jobs.scheduler import SCHEDULER
    for obj in [o for o in bpy.data.objects if o.type == "MESH"]:
        bpy.data.objects.remove(obj)
    bpy.ops.iteron.add_fractal(formula=formula_id)
    obj = bpy.context.active_object
    obj.iteron.final_resolution = resolution
    SCHEDULER.run_now(obj, final=True)
    return obj
