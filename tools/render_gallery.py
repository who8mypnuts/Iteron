# SPDX-License-Identifier: MIT
"""Render every formula's default with EEVEE into docs/images/ (for the README), one image per formula.

    blender -b --factory-startup --python tools/render_gallery.py -- [resolution] [pixels]
    (or `python tools/render_gallery.py` with the `bpy` module)
"""

import math
import sys
from pathlib import Path

import bpy
import mathutils
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "images"
VIEW = mathutils.Vector((1.0, -1.25, 0.85)).normalized()


def setup_scene(pixels: int):
    scene = bpy.context.scene
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = pixels
    scene.render.film_transparent = False
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
    return scene, camera


def set_background(world, colour) -> None:
    """The world colour, through its Background node when it has one (always in Blender 5)."""
    world.color = colour
    if world.node_tree is None and bpy.app.version < (5, 0, 0):
        world.use_nodes = True
    background = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None) if world.node_tree else None
    if background is not None:
        background.inputs["Color"].default_value = (*colour, 1.0)


def frame(camera, obj) -> None:
    co = np.zeros(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    lo, hi = co.min(axis=0), co.max(axis=0)
    center = mathutils.Vector((lo + hi) / 2)
    camera.data.lens = 50
    camera.location = center + VIEW * float(np.linalg.norm(hi - lo)) * 1.55
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    resolution = int(args[0]) if args else 160
    pixels = int(args[1]) if len(args) > 1 else 480
    import iteron
    iteron.register()
    from iteron.core.formula import REGISTRY
    from iteron.jobs.scheduler import SCHEDULER
    scene, camera = setup_scene(pixels)
    bpy.ops.render.render()                 # creates the GPU context the gpu sampler needs in background mode
    OUT.mkdir(parents=True, exist_ok=True)
    for fid in REGISTRY:
        for obj in [o for o in bpy.data.objects if o.type == "MESH"]:
            bpy.data.objects.remove(obj)
        bpy.ops.iteron.add_fractal(formula=fid)
        obj = bpy.context.active_object
        obj.iteron.final_resolution = resolution
        SCHEDULER.run_now(obj, final=True)
        frame(camera, obj)
        scene.render.filepath = str(OUT / f"{fid}.png")
        bpy.ops.render.render(write_still=True)
        print(f"{fid}: {obj.iteron.built_faces:,} faces on the {obj.iteron.built_device}", flush=True)


if __name__ == "__main__":
    main()
