# SPDX-License-Identifier: MIT
"""Fragment objects in Blender: opening `.frag` / `.fafrag` files, building on the GPU, parameters as typed items
(presets, keyframes, staleness), editing the source, saving and reopening, and the live preview's shader."""

import math
from pathlib import Path

import numpy as np
import pytest

import bpy
from iteron.bridge import fragment_props, state
from iteron.bridge.kinds import FragmentKind
from iteron.fragments.preprocess import FragmentError
from iteron.jobs.scheduler import SCHEDULER
from iteron.ops.fragments import import_fragment
from iteron.ui import panel

from .test_ui import FakeLayout

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "fractalchemy" / "PseudoKleinian.fafrag"
COLLECTION = ROOT / "sample_source" / "Fractalchemy" / "fractalchemy" / "fragments" / "library" / "Examples" / \
    "Fractalchemy Collection"
BALL = """#include "MathUtils.frag"
#include "DE-Raytracer.frag"
#group Ball
uniform float Radius; slider[0.1,0.8,2]
uniform int Bumps; slider[0,0,8]
float DE(vec3 p) { orbitTrap = min(orbitTrap, vec4(abs(p), dot(p, p)));
    return length(p) - Radius - 0.05 * float(Bumps) * sin(10.0 * p.x); }
#preset Default
Radius = 0.6
Eye = 0,0,-3
Target = 0,0,0
Up = 0,1,0
FOV = 0.5
#endpreset
#preset Big
Radius = 1.2
#endpreset
"""


@pytest.fixture
def ball(gpu_context, tmp_path):
    path = tmp_path / "Ball.frag"
    path.write_text(BALL)

    def add(camera=False):
        obj = import_fragment(bpy.context, path, camera=camera)
        obj.iteron.preview_resolution = 40
        SCHEDULER.run_now(obj)
        return obj
    return add


def test_a_fragment_imports_and_builds_on_the_gpu(ball):
    obj = ball()
    s = obj.iteron
    assert s.kind == "FRAGMENT" and s.fragment.text is not None and s.fragment.name == "Ball"
    assert s.built_device == "GPU" and len(obj.data.polygons) > 200, s.message
    radius = np.linalg.norm(np.array([v.co for v in obj.data.vertices]), axis=1)
    assert abs(np.median(radius) - 0.6) < 0.06                    # the Default preset was applied
    assert obj.rotation_euler.x == pytest.approx(math.pi / 2)      # y-up fragment stood upright


def test_parameters_are_typed_items_with_presets_and_keyframes(ball):
    obj = ball()
    params = obj.iteron.fragment.params
    assert params["Radius"].kind == "float" and params["Bumps"].kind == "int"
    assert not state.is_stale(obj)
    params["Radius"].value[0] = 0.9
    assert state.is_stale(obj)
    bpy.ops.iteron.apply_preset(preset="Big")
    assert FragmentKind.read(obj)["Radius"] == pytest.approx(1.2)
    assert obj.keyframe_insert('iteron.fragment.params["Radius"].value', index=0, frame=1)


def test_editing_the_source_adds_parameters_on_rebuild(ball):
    obj = ball()
    text = obj.iteron.fragment.text
    text.from_string(text.as_string().replace("#group Ball", "#group Ball\nuniform float Extra; slider[0,0.5,1]"))
    assert state.is_stale(obj)
    SCHEDULER.run_now(obj)
    assert obj.iteron.fragment.params["Extra"].value[0] == pytest.approx(0.5)
    assert obj.iteron.fragment.params["Radius"].value[0] == pytest.approx(0.6)   # kept


def test_a_broken_source_is_reported_not_raised(ball):
    obj = ball()
    obj.iteron.fragment.text.from_string('#include "Nowhere.frag"\n')
    SCHEDULER.run_now(obj)
    assert "Nowhere.frag" in obj.iteron.message
    log = []
    panel.draw_fractal(FakeLayout(log), obj)
    assert any("Nowhere.frag" in text for kind, text in log if kind == "label")


def test_the_camera_looks_at_the_target(ball):
    obj = ball(camera=True)
    camera = bpy.context.scene.camera
    assert camera is not None and camera.data.sensor_fit == "VERTICAL"
    assert camera.data.angle_y == pytest.approx(2 * math.atan(0.5))
    forward = -np.array(camera.matrix_world.to_3x3())[:, 2]
    to_target = np.array(obj.matrix_world.translation) - np.array(camera.matrix_world.translation)
    assert forward @ to_target / np.linalg.norm(to_target) > 0.999


def test_the_panel_draws_fragment_parameters(ball):
    obj = ball()
    log = []
    panel.draw_fractal(FakeLayout(log), obj)
    shown = [name for kind, name in log if kind == "prop"]
    assert "value" in shown and "integer" in shown and ("operator", "iteron.build_final") in log


def test_the_preview_shader_compiles_for_a_fragment(ball):
    from iteron.gpu_eval import raymarch
    obj = ball()
    entry = FragmentKind.entry(obj)
    compiled, _batch = raymarch.shader(entry, entry.values(FragmentKind.read(obj)))
    assert compiled is not None


def test_without_a_gpu_fragments_say_so(ball):
    with pytest.raises(FragmentError, match="GPU"):
        FragmentKind.sampler(None, force_cpu=True)


def test_the_fixture_and_the_source_survive_save_and_reload(ball, tmp_path):
    obj = import_fragment(bpy.context, FIXTURE, camera=False)
    obj.iteron.preview_resolution = 32
    SCHEDULER.run_now(obj)
    assert len(obj.data.polygons) > 100, obj.iteron.message
    faces, name = len(obj.data.polygons), obj.name
    blend = tmp_path / "fragment.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    again = bpy.data.objects[name]
    assert len(again.data.polygons) == faces and not state.is_stale(again)
    assert {"MI", "Size", "CSize"} <= set(again.iteron.fragment.params.keys())


@pytest.mark.skipif(not COLLECTION.is_dir(), reason="Fractalchemy's fragment library is not in the checkout")
@pytest.mark.parametrize("name", ["3D - Juliabulb", "3D - Koch Tetrahedron", "3D - Mosely Snowflake"])
def test_collection_fragments_mesh_in_blender(gpu_context, name):
    obj = import_fragment(bpy.context, COLLECTION / f"{name}.frag", camera=False)
    obj.iteron.preview_resolution = 48
    SCHEDULER.run_now(obj)
    assert len(obj.data.polygons) > 500, obj.iteron.message
    assert fragment_props.read(obj.iteron.fragment, FragmentKind.entry(obj).params)
    assert obj.iteron.color_mode == ("TRAP" if FragmentKind.entry(obj).uses_trap else "RADIUS")


TEXTURED = """#define providesColor
#include "DE-Raytracer.frag"
uniform sampler2D bumps; file[bumps.png]
float DE(vec3 p) { return length(p) - 1.2 * texture2D(bumps, vec2(0.5, 0.5)).r; }
vec3 baseColor(vec3 p, vec3 n) { return p.z > 0.0 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0); }
"""


@pytest.fixture
def textured(gpu_context, tmp_path):
    image = bpy.data.images.new("bumps", 4, 4)
    image.pixels[:] = [0.5, 0.5, 0.5, 1.0] * 16
    image.filepath_raw = str(tmp_path / "bumps.png")
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)
    path = tmp_path / "Textured.frag"
    path.write_text(TEXTURED)
    obj = import_fragment(bpy.context, path, camera=False)
    obj.iteron.preview_resolution = 40
    SCHEDULER.run_now(obj)
    return obj


def test_a_textured_fragment_packs_and_samples_its_image(textured):
    [item] = textured.iteron.fragment.textures
    assert item.name == "bumps" and item.image.packed_file is not None
    assert item.image.colorspace_settings.name == "Non-Color"
    assert len(textured.data.vertices) > 100, textured.iteron.message
    radius = np.linalg.norm(np.array([v.co for v in textured.data.vertices]), axis=1)
    assert abs(np.median(radius) - 0.6) < 0.05                      # 1.2 × the texture's 0.5


def test_a_fragment_with_its_own_colour_uses_it(textured):
    assert textured.iteron.color_mode == "BASE"
    mesh = textured.data
    colours = np.zeros(len(mesh.vertices) * 4, dtype=np.float32)
    mesh.color_attributes["Col"].data.foreach_get("color", colours)
    colours = colours.reshape(-1, 4)
    z = np.array([v.co.z for v in mesh.vertices])
    assert np.allclose(colours[z > 0.1, :3], (1.0, 0.0, 0.0), atol=1e-3)
    assert np.allclose(colours[z < -0.1, :3], (0.0, 1.0, 0.0), atol=1e-3)
    from iteron.bridge import material
    bsdf = next(n for n in material.find(textured).node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    assert bsdf.inputs["Base Color"].links[0].from_node.name == material.ATTRIBUTE_NODE
    textured.iteron.color_mode = "TRAP"
    assert bsdf.inputs["Base Color"].links[0].from_node.name == material.RAMP_NODE


def test_the_preview_shader_binds_the_texture(textured):
    from iteron.gpu_eval import raymarch
    entry = FragmentKind.entry(textured)
    raymarch.shader(entry, entry.values(FragmentKind.read(textured)))
    assert set(FragmentKind.textures(textured)) == {"bumps"}


def test_a_missing_texture_file_is_reported(gpu_context, tmp_path):
    path = tmp_path / "Lonely.frag"
    path.write_text(TEXTURED)
    with pytest.raises(FragmentError, match="bumps.png"):
        import_fragment(bpy.context, path, camera=False)
