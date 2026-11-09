# SPDX-License-Identifier: MIT
"""Tests that run inside Blender: the `bpy` module (pip install bpy) or `blender -b --python tools/run_blender_tests.py`.

The add-on is registered once per session from the repository; every test starts from an empty scene.
"""

import sys
from pathlib import Path

import pytest

bpy = pytest.importorskip("bpy")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session", autouse=True)
def addon():
    import iteron
    iteron.register()
    yield iteron
    iteron.unregister()


@pytest.fixture(autouse=True)
def empty_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for material in list(bpy.data.materials):
        bpy.data.materials.remove(material)
    yield


@pytest.fixture
def fractal():
    """Add a fractal (built on the CPU, synchronously: background mode) and return the object."""
    def add(formula="mandelbulb", resolution=48):
        bpy.context.window_manager  # noqa: B018 - touch the context
        from iteron.jobs.scheduler import SCHEDULER
        bpy.ops.iteron.add_fractal(formula=formula)
        obj = bpy.context.active_object
        if resolution != obj.iteron.preview_resolution:
            obj.iteron.preview_resolution = resolution
            SCHEDULER.run_now(obj)
        return obj
    return add


@pytest.fixture
def gpu_context():
    """Make the `gpu` module usable in background mode (an EEVEE render creates a GPU context); skip if it can't."""
    from iteron.gpu_eval import sampler
    if not sampler.available():
        scene = bpy.context.scene
        camera = bpy.data.objects.new("Iteron Test Camera", bpy.data.cameras.new("Iteron Test Camera"))
        scene.collection.objects.link(camera)
        scene.camera = camera
        engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
        scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
        scene.render.resolution_x = scene.render.resolution_y = 8
        try:
            bpy.ops.render.render()
        except RuntimeError as error:
            pytest.skip(f"no render context: {error}")
        finally:
            bpy.data.objects.remove(camera)
    if not sampler.available():
        pytest.skip("the gpu module cannot draw here")
    return sampler
