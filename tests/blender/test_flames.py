# SPDX-License-Identifier: MIT
"""Flame objects in Blender: adding the bundled flames, points and solids, the point-size modifier, staleness, and
importing Fractalchemy's `.fa` and `.fa3d` files."""

from pathlib import Path

import numpy as np
import pytest

import bpy
from iteron.bridge import flame_write, state
from iteron.flames import formats
from iteron.flames.library import bundled
from iteron.jobs.scheduler import SCHEDULER
from iteron.ops.importer import import_fa, import_fa3d
from iteron.ui import flame_panel, panel

from .test_ui import FakeLayout

ROOT = Path(__file__).resolve().parents[2]
FA3D = ROOT / "tests" / "fixtures" / "fractalchemy" / "3d musk sphere.fa3d"
FA = sorted((ROOT / "sample_source" / "Fractalchemy" / "samples").rglob("*.fa"))


@pytest.fixture
def small_flames(monkeypatch):
    """Previews of at most 20 000 points keep these tests quick."""
    from iteron.bridge import flame_props
    monkeypatch.setattr(flame_props, "PREVIEW_POINTS", 20_000)


@pytest.mark.parametrize("key", list(bundled()))
def test_every_bundled_flame_adds_as_a_point_cloud(small_flames, key):
    bpy.ops.iteron.add_flame(flame=key)
    obj = bpy.context.active_object
    mesh = obj.data
    assert obj.iteron.kind == "FLAME" and obj.iteron.is_fractal
    assert len(mesh.vertices) > 15_000 and len(mesh.polygons) == 0
    assert "Col" in mesh.color_attributes and "iteron_xform" in mesh.attributes
    modifier = obj.modifiers[flame_write.MODIFIER]
    assert modifier.node_group.name == flame_write.POINTS_GROUP
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    assert evaluated.data is not None


def test_point_size_reaches_the_modifier(small_flames):
    bpy.ops.iteron.add_flame(flame="sierpinski_pyramid")
    obj = bpy.context.active_object
    obj.iteron.flame.point_radius = 0.0125
    modifier = obj.modifiers[flame_write.MODIFIER]
    values = [modifier[key] for key in modifier.keys() if isinstance(modifier[key], float)]
    assert any(abs(v - 0.0125) < 1e-9 for v in values)


def test_a_solid_flame_is_a_closed_mesh_without_the_points_modifier(small_flames):
    bpy.ops.iteron.add_flame(flame="sierpinski_pyramid")
    obj = bpy.context.active_object
    obj.iteron.preview_resolution = 48
    obj.iteron.flame.output = "MESH"
    SCHEDULER.run_now(obj)
    assert len(obj.data.polygons) > 100 and flame_write.MODIFIER not in obj.modifiers
    assert "iteron_xform" not in obj.data.attributes


def test_changing_the_seed_makes_the_flame_stale(small_flames):
    bpy.ops.iteron.add_flame(flame="julia_bloom")
    obj = bpy.context.active_object
    assert not state.is_stale(obj)
    before = state.shape_hash(obj)
    obj.iteron.flame.seed = 9
    assert state.shape_hash(obj) != before and state.is_stale(obj)


def test_the_flame_panel_draws(small_flames):
    bpy.ops.iteron.add_flame(flame="curl_shell")
    obj = bpy.context.active_object
    log = []
    panel.draw_fractal(FakeLayout(log), obj)
    assert ("prop", "output") in log and ("prop", "point_radius") in log and ("operator", "iteron.build_final") in log
    obj.iteron.flame.output = "MESH"
    log.clear()
    flame_panel.draw_flame(FakeLayout(log), obj, lambda *_: None, lambda layout: layout)
    assert ("prop", "threshold") in log


@pytest.mark.skipif(not FA, reason="Fractalchemy's sample .fa files are not in the checkout")
def test_fa_import_adds_one_object_per_flame(small_flames):
    path = max(FA, key=lambda p: len(formats.read_fa(p)))
    objects = import_fa(bpy.context, path, all_flames=True)
    first_only = import_fa(bpy.context, path, all_flames=False)
    assert len(objects) >= 2 and len(first_only) == 1
    assert all(len(o.data.vertices) > 1000 for o in objects)
    assert len({tuple(o.location) for o in objects}) == len(objects)      # side by side


def test_fa3d_import_builds_the_scene(small_flames):
    obj = import_fa3d(bpy.context, FA3D, camera=True, lights=True, world=True)
    scene = bpy.context.scene
    assert obj.iteron.flame.output == "MESH" and obj.iteron.final_resolution == 128
    assert len(obj.data.polygons) > 50
    camera = scene.camera
    assert camera is not None and camera.type == "CAMERA"
    rotation = np.array(camera.matrix_world.to_3x3())
    assert np.linalg.det(rotation) > 0.99                     # a proper rotation, not a mirror
    forward = -rotation[:, 2]
    centre = np.array(obj.matrix_world.translation)
    to_object = centre - np.array(camera.matrix_world.translation)
    assert forward @ to_object > 0                            # it looks towards the flame
    lamps = sorted(o.data.type for o in bpy.data.objects if o.type == "LIGHT")
    assert lamps == ["POINT", "SUN"]
    assert scene.world is not None


def test_fa3d_import_without_extras_adds_only_the_flame(small_flames):
    import_fa3d(bpy.context, FA3D, camera=False, lights=False, world=False)
    assert [o.type for o in bpy.data.objects] == ["MESH"]


def test_import_operator_reports_bad_files(tmp_path):
    bad = tmp_path / "broken.fa"
    bad.write_text("{}")
    with pytest.raises(RuntimeError):
        bpy.ops.iteron.import_fractalchemy(filepath=str(bad))
