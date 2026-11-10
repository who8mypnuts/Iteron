# SPDX-License-Identifier: MIT
"""Detail features inside Blender: simplified meshes with triangles, field normals as custom normals, shading modes,
recommended offsets, Frame View's region."""

import math

import numpy as np
import pytest

import bpy
from mathutils import Matrix, Vector

from iteron.core.formula import REGISTRY
from iteron.ops.region import view_region


def test_final_build_with_simplification_writes_quads_and_triangles(fractal):
    obj = fractal("menger_sponge", resolution=32)
    obj.iteron.final_resolution = 72
    obj.iteron.simplify = 0.15
    bpy.ops.iteron.build_final()
    sizes = np.zeros(len(obj.data.polygons), dtype=np.int32)
    obj.data.polygons.foreach_get("loop_total", sizes)
    assert set(np.unique(sizes)) == {3, 4} and obj.iteron.built_faces == len(sizes)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    assert all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True) > 0
    bm.free()


def test_field_normals_are_custom_normals_and_other_shading_drops_them(fractal):
    obj = fractal("mandelbulb", resolution=32)
    assert obj.data.has_custom_normals
    obj.iteron.shading = "FLAT"
    assert not any(p.use_smooth for p in obj.data.polygons)
    obj.iteron.shading = "SMOOTH"
    assert all(p.use_smooth for p in obj.data.polygons)


def test_each_formula_brings_its_recommended_surface_offset(fractal):
    obj = fractal("mandelbox", resolution=24)
    assert obj.iteron.surface_offset == pytest.approx(REGISTRY["mandelbox"].surface_offset)
    obj.iteron.formula = "menger_sponge"
    assert obj.iteron.surface_offset == pytest.approx(REGISTRY["menger_sponge"].surface_offset)


def test_frame_view_covers_the_pivot_at_the_current_zoom():
    view = type("R3D", (), {"view_distance": 4.0, "view_location": Vector((1.0, 2.0, 3.0))})()
    space = type("Space", (), {"lens": 50.0})()
    world = Matrix.Translation((1.0, 0.0, 0.0)) @ Matrix.Scale(2.0, 4)
    center, half = view_region(view, space, world)
    assert tuple(center) == pytest.approx((0.0, 1.0, 1.5))
    assert half == pytest.approx(4.0 * 18.0 / 50.0 * 1.2 / 2.0)
    assert math.isfinite(half)


def test_reset_region(fractal):
    obj = fractal("mandelbulb", resolution=24)
    obj.iteron.auto_fit, obj.iteron.size = False, 0.3
    bpy.ops.iteron.reset_region()
    assert obj.iteron.auto_fit and obj.iteron.size == 0.0
