# SPDX-License-Identifier: MIT
"""Flames in Blender, continued: a material per transform (point clouds and solids, and from `.fa3d` scenes) and
holon instances along a flame (the child object, its Instance on Points modifier, restyling without a rebuild)."""

import json
from pathlib import Path

import numpy as np
import pytest

import bpy
from iteron.bridge import flame_materials, flame_write, holons
from iteron.jobs.scheduler import SCHEDULER
from iteron.ops.importer import import_fa3d
from iteron.ui import panel

from .test_ui import FakeLayout

FA3D = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "fractalchemy" / "3d musk sphere.fa3d"


@pytest.fixture
def pyramid(monkeypatch):
    from iteron.bridge import flame_props
    monkeypatch.setattr(flame_props, "PREVIEW_POINTS", 20_000)
    bpy.ops.iteron.add_flame(flame="sierpinski_pyramid")
    return bpy.context.active_object


def _evaluated_materials(obj):
    """The materials of the point clouds the flame evaluates to (one per part)."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    found = set()
    for instance in depsgraph.object_instances:
        if instance.object.type == "POINTCLOUD" and instance.parent and instance.parent.original == obj:
            found |= {m.name for m in instance.object.data.materials if m}
    return [found]


def test_points_get_a_material_per_transform_and_back(pyramid):
    pyramid.iteron.flame.per_transform = True
    slots = [m.name for m in pyramid.data.materials]
    assert len(slots) == 4 and all(m.get(flame_materials.TRANSFORM_TAG) is not None for m in pyramid.data.materials)
    group = pyramid.modifiers[flame_write.MODIFIER].node_group
    assert group.name.startswith("Iteron Points · ")
    assert sum(n.bl_idname == "GeometryNodeSetMaterial" for n in group.nodes) == 4
    assert _evaluated_materials(pyramid) == [set(slots)]
    pyramid.iteron.flame.per_transform = False
    assert len(pyramid.data.materials) == 1
    assert pyramid.modifiers[flame_write.MODIFIER].node_group.name == flame_write.POINTS_GROUP


def test_a_solid_colours_its_faces_by_transform(pyramid):
    f = pyramid.iteron.flame
    f.output, f.per_transform = "MESH", True
    pyramid.iteron.preview_resolution = 40
    SCHEDULER.run_now(pyramid)
    index = np.zeros(len(pyramid.data.polygons), dtype=np.int32)
    pyramid.data.polygons.foreach_get("material_index", index)
    assert set(np.unique(index)) == {0, 1, 2, 3}


def _scene_with_extras(tmp_path) -> Path:
    data = json.loads(FA3D.read_text())
    scene = data["scene"]
    scene["materials"][0].update({"color_mode": "fixed", "color": [255, 0, 0], "shininess": 180.0})
    scene["assets"] = [{"name": "box", "kind": "primitive", "primitive": "cube", "detail": 1}]
    scene["instancers"] = [{"name": "cubes", "asset": "box", "mode": "tree", "depth": 2, "size": 0.3,
                            "min_size": 0.0, "visible": True}]
    path = tmp_path / "extras.fa3d"
    path.write_text(json.dumps(data))
    return path


def test_fa3d_materials_and_instancers_come_across(tmp_path, monkeypatch):
    from iteron.bridge import flame_props
    monkeypatch.setattr(flame_props, "PREVIEW_POINTS", 20_000)
    obj = import_fa3d(bpy.context, _scene_with_extras(tmp_path), camera=False, lights=False, world=False)
    f = obj.iteron.flame
    assert f.per_transform and len(obj.data.materials) == len(f.flame_dict()["xforms"])
    first = obj.data.materials[0]
    bsdf = next(n for n in first.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    assert not bsdf.inputs["Base Color"].links and tuple(bsdf.inputs["Base Color"].default_value)[:3] == (1.0, 0.0, 0.0)
    assert bsdf.inputs["Roughness"].default_value == pytest.approx(0.1)
    settings = f.instancer
    assert settings.enabled and settings.mode == "TREE" and settings.shape == "CUBE" and settings.depth == 2
    assert settings.holder is not None and len(settings.holder.data.vertices) > 0


def test_holons_live_on_a_child_and_restyle_without_a_rebuild(pyramid):
    settings = pyramid.iteron.flame.instancer
    settings.mode, settings.depth, settings.size, settings.min_size = "TREE", 2, 0.5, 0.0
    settings.enabled = True
    SCHEDULER.run_now(pyramid)
    holder = settings.holder
    assert holder.parent == pyramid and len(holder.data.vertices) == 4 + 16
    for name in (holons.ROTATION, holons.SCALE, holons.COLOUR):
        assert name in holder.data.attributes
    depsgraph = bpy.context.evaluated_depsgraph_get()
    placed = [i for i in depsgraph.object_instances if i.is_instance and i.parent and i.parent.original == holder]
    assert len(placed) == 20
    built, name = pyramid.iteron.built_hash, holder.name
    settings.shape = "TORUS"
    info = next(n for n in holder.modifiers[holons.MODIFIER].node_group.nodes if n.bl_idname == "GeometryNodeObjectInfo")
    assert info.inputs["Object"].default_value.name == "Iteron Torus" and pyramid.iteron.built_hash == built
    settings.enabled = False
    SCHEDULER.run_now(pyramid)
    assert settings.holder is None and name not in bpy.data.objects


def test_every_built_in_shape_is_unit_sized():
    for kind in ("SPHERE", "CUBE", "ICOSAHEDRON", "TETRAHEDRON", "TORUS", "CYLINDER"):
        made = holons.shape(kind)
        size = np.ptp(np.array([v.co for v in made.data.vertices]), axis=0).max()
        assert 0.5 < size <= 1.0 + 1e-6 and made.users_collection[0].name == holons.ASSETS


def test_the_flame_panel_draws_materials_and_instances(pyramid):
    log = []
    panel.draw_fractal(FakeLayout(log), pyramid)
    assert ("prop", "per_transform") in log and ("prop", "enabled") in log and ("prop", "shape") in log
