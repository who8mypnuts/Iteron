# SPDX-License-Identifier: MIT
"""The add-on inside Blender: registration, adding and building, staleness, presets, saving, exporting."""

import numpy as np
import pytest

import bpy
from iteron.bridge import colors, material
from iteron.bridge.props import group, read_values
from iteron.bridge.state import is_stale, shape_hash
from iteron.core.formula import REGISTRY
from iteron.jobs.scheduler import SCHEDULER


def test_reregister(addon):
    addon.unregister()
    addon.register()
    assert hasattr(bpy.types.Object, "iteron")
    assert hasattr(bpy.ops.iteron, "add_fractal")


@pytest.mark.parametrize("fid", list(REGISTRY))
def test_every_formula_builds(fractal, fid):
    obj = fractal(fid, resolution=40)
    mesh, s = obj.data, obj.iteron
    assert s.is_fractal and s.formula == fid
    assert len(mesh.polygons) > 100 and all(len(p.vertices) == 4 for p in mesh.polygons[:50])
    assert s.built_faces == len(mesh.polygons) and s.built_device == "CPU" and not s.message
    assert not is_stale(obj)
    for name in ("iteron_trap", "iteron_iterations", "iteron_radius"):
        values = np.zeros(len(mesh.vertices), dtype=np.float32)
        mesh.attributes[name].data.foreach_get("value", values)
        assert 0.0 <= values.min() and values.max() <= 1.0
    assert material.find(obj) is not None and mesh.color_attributes.active_color.name == colors.COLOR_ATTRIBUTE


def test_mesh_is_closed_and_outward(fractal):
    import bmesh
    obj = fractal("menger_sponge", resolution=40)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    assert all(e.is_manifold for e in bm.edges)
    assert bm.calc_volume(signed=True) > 0
    bm.free()


def test_parameter_change_makes_stale_and_rebuild_clears_it(fractal):
    obj = fractal("mandelbulb", resolution=32)
    before = len(obj.data.vertices)
    group(obj.iteron).power = 4.0
    assert is_stale(obj)
    SCHEDULER.run_now(obj)
    assert not is_stale(obj) and len(obj.data.vertices) != before


def test_presets_and_reset(fractal):
    obj = fractal("mandelbulb", resolution=32)
    bpy.ops.iteron.apply_preset(preset="Juliabulb")
    values = read_values(obj.iteron)
    assert values["julia"] and values["julia_c"] == pytest.approx((0.35, 0.45, -0.3))
    bpy.ops.iteron.reset_formula()
    assert read_values(obj.iteron) == REGISTRY["mandelbulb"].values()


def test_switching_formula_keeps_each_formulas_values(fractal):
    obj = fractal("mandelbulb", resolution=32)
    group(obj.iteron).power = 5.0
    obj.iteron.formula = "menger_sponge"
    obj.iteron.formula = "mandelbulb"
    assert group(obj.iteron).power == 5.0


def test_build_final_and_materials_survive(fractal):
    obj = fractal("sierpinski_tetrahedron", resolution=32)
    obj.iteron.final_resolution = 64
    preview_faces = obj.iteron.built_faces
    bpy.ops.iteron.build_final()
    assert obj.iteron.built_final and obj.iteron.built_resolution == 64 and obj.iteron.built_faces > preview_faces
    assert material.find(obj) is not None


def test_color_mode_switches_attribute_and_rebakes(fractal):
    obj = fractal("mandelbulb", resolution=32)
    before = np.zeros(len(obj.data.vertices) * 4, dtype=np.float32)
    obj.data.color_attributes["Col"].data.foreach_get("color", before)
    obj.iteron.color_mode = "ITERATIONS"
    node = material.find(obj).node_tree.nodes[material.ATTRIBUTE_NODE]
    assert node.attribute_name == "iteron_iterations"
    after = np.zeros_like(before)
    obj.data.color_attributes["Col"].data.foreach_get("color", after)
    assert not np.allclose(before, after)


def test_apply_as_plain_mesh(fractal):
    obj = fractal("octahedral_kifs", resolution=32)
    faces = len(obj.data.polygons)
    bpy.ops.iteron.apply_mesh()
    assert not obj.iteron.is_fractal and len(obj.data.polygons) == faces
    assert not bpy.ops.iteron.rebuild.poll()


def test_save_and_reopen_keeps_everything_without_rebuilding(fractal, tmp_path):
    obj = fractal("quaternion_julia", resolution=32)
    group(obj.iteron).slice = 0.1
    SCHEDULER.run_now(obj)
    digest, faces = shape_hash(obj), len(obj.data.polygons)
    path = str(tmp_path / "fractal.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    obj = bpy.data.objects["Quaternion Julia"]
    assert obj.iteron.is_fractal and group(obj.iteron).slice == pytest.approx(0.1)
    assert obj.iteron.built_hash == digest == shape_hash(obj) and len(obj.data.polygons) == faces
    assert not SCHEDULER.busy()


def test_gltf_export_carries_colours(fractal, tmp_path):
    import json
    import struct
    fractal("mandelbulb", resolution=32)
    path = tmp_path / "bulb.glb"
    options = {"filepath": str(path), "use_selection": True}
    rna = bpy.ops.export_scene.gltf.get_rna_type().properties
    if "export_vertex_color" in rna:           # Blender 4.2+: export the active colour attribute
        options["export_vertex_color"] = "ACTIVE"
    else:
        options["export_colors"] = True
    bpy.ops.export_scene.gltf(**options)
    data = path.read_bytes()
    length = struct.unpack_from("<I", data, 12)[0]
    document = json.loads(data[20:20 + length])
    attributes = document["meshes"][0]["primitives"][0]["attributes"]
    assert "COLOR_0" in attributes


def test_linked_duplicates_share_the_rebuilt_mesh(fractal):
    obj = fractal("menger_sponge", resolution=32)
    twin = obj.copy()
    bpy.context.collection.objects.link(twin)
    group(obj.iteron).scale = 2.5
    SCHEDULER.run_now(obj)
    assert twin.data is obj.data and len(twin.data.polygons) == obj.iteron.built_faces
