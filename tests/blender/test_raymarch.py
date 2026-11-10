# SPDX-License-Identifier: MIT
"""The live ray-marched preview: shaders compile, hits land where the numpy estimator puts the surface (with the right
depth), and the preview modes hide and restore the mesh."""

import numpy as np
import pytest

import bpy
from iteron.bridge.props import group
from iteron.core import cpu_eval
from iteron.core.formula import REGISTRY
from iteron.jobs.scheduler import SCHEDULER


def _perspective(fov_y, aspect, near, far):
    f = 1.0 / np.tan(fov_y / 2.0)
    return np.array([[f / aspect, 0, 0, 0], [0, f, 0, 0],
                     [0, 0, (far + near) / (near - far), 2 * far * near / (near - far)], [0, 0, -1, 0]])


def _look_at(eye, target, up=(0.0, 0.0, 1.0)):
    eye, target, up = (np.asarray(v, dtype=np.float64) for v in (eye, target, up))
    f = target - eye
    f /= np.linalg.norm(f)
    s = np.cross(f, up)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    view = np.eye(4)
    view[0, :3], view[1, :3], view[2, :3] = s, u, -f
    view[:3, 3] = -view[:3, :3] @ eye
    return view


@pytest.mark.parametrize("fid", list(REGISTRY))
def test_every_formula_compiles_its_preview_shader(gpu_context, fid):
    from iteron.gpu_eval import raymarch
    entry = REGISTRY[fid]
    raymarch.shader(entry, entry.values())


def test_the_preview_hits_the_surface_at_the_right_depth(gpu_context):
    import gpu
    from iteron.gpu_eval import raymarch
    entry = REGISTRY["mandelbulb"]
    values = entry.values()
    size, near, far, eye = 64, 0.1, 20.0, np.array([0.0, -3.0, 0.0])
    projection = _perspective(np.radians(40.0), 1.0, near, far)
    mvp = projection @ _look_at(eye, (0.0, 0.0, 0.0))
    lut = np.repeat(np.linspace(0.0, 1.0, 256, dtype=np.float32)[:, None], 4, axis=1)
    offscreen = gpu.types.GPUOffScreen(size, size, format="RGBA32F")
    try:
        with offscreen.bind():
            framebuffer = gpu.state.active_framebuffer_get()
            framebuffer.clear(color=(0.0, 0.0, 0.0, 0.0), depth=1.0)
            gpu.state.viewport_set(0, 0, size, size)
            raymarch.draw(entry, values, mvp, (0, 0, size, size), (np.full(3, -1.4), np.full(3, 1.4)), lut, "TRAP",
                          ((0.0,) * 3, (1.0,) * 3))
            colour = np.asarray(framebuffer.read_color(0, 0, size, size, 4, 0, "FLOAT").to_list()).reshape(size, size, 4)
            depth = np.asarray(framebuffer.read_depth(0, 0, size, size).to_list()).reshape(size, size)
    finally:
        offscreen.free()
    centre, corner = size // 2, 1
    assert colour[centre, centre, 3] == 1.0 and colour[corner, corner, 3] == 0.0
    assert depth[corner, corner] == 1.0 and depth[centre, centre] < 1.0
    # the same ray, marched in numpy (float64): the first point where the estimate drops below the pixel's footprint
    # at that distance (what the shader stops at)
    t = np.linspace(0.0, 3.0, 30001)
    points = eye + t[:, None] * np.array([0.0, 1.0, 0.0])
    distance = cpu_eval.evaluate(entry, values, points)[:, 0]
    footprint = t * 2.0 * np.tan(np.radians(20.0)) / size
    hit = t[np.argmax(distance < footprint)]
    clip = mvp @ np.array([*(eye + hit * np.array([0.0, 1.0, 0.0])), 1.0])
    assert depth[centre, centre] == pytest.approx(clip[2] / clip[3] * 0.5 + 0.5, abs=2e-3)


def test_auto_preview_hides_the_stale_mesh_until_the_rebuild(fractal):
    obj = fractal("mandelbulb", resolution=24)
    original = obj.display_type
    group(obj.iteron).power = 6.0
    assert obj.display_type == "BOUNDS" and obj.iteron.saved_display == original
    SCHEDULER.run_now(obj)
    assert obj.display_type == original and not obj.iteron.saved_display


def test_raymarch_mode_shows_no_mesh_and_does_not_rebuild(fractal, monkeypatch):
    obj = fractal("mandelbulb", resolution=24)
    requests = []
    monkeypatch.setattr(SCHEDULER, "request", lambda *a, **k: requests.append(a))
    obj.iteron.preview = "RAYMARCH"
    group(obj.iteron).power = 5.0
    assert obj.display_type == "BOUNDS" and not requests
    obj.iteron.preview = "MESH"
    assert obj.display_type != "BOUNDS"


def test_saving_keeps_the_objects_own_display_type(fractal, tmp_path):
    obj = fractal("mandelbulb", resolution=24)
    obj.display_type = "SOLID"
    obj.iteron.preview = "RAYMARCH"
    assert obj.display_type == "BOUNDS"
    path = str(tmp_path / "preview.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    assert obj.display_type == "BOUNDS"                 # re-applied after saving
    bpy.ops.wm.open_mainfile(filepath=path)
    reopened = bpy.data.objects["Mandelbulb"]
    assert reopened.iteron.saved_display == "SOLID"     # the file held SOLID; loading put the preview back on
