# SPDX-License-Identifier: MIT
"""Fragments without Blender: the document (presets, metadata, camera), annotations, the preprocessor's include
rules, the GLSL compatibility pass, and the acceptance set — every 3D fragment of Fractalchemy's own collection
builds from Iteron's shims alone and has a surface (sampled through moderngl when an OpenGL context exists)."""

import sys
from pathlib import Path

import numpy as np
import pytest

from iteron.core.grid import cube_plan
from iteron.fragments import annotations, compat, document, preprocess
from iteron.fragments.formula import build, embeddable
from iteron.fragments.preprocess import FragmentError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "fractalchemy" / "PseudoKleinian.fafrag"
LIBRARY = ROOT / "sample_source" / "Fractalchemy" / "fractalchemy" / "fragments" / "library"
COLLECTION = sorted((LIBRARY / "Examples" / "Fractalchemy Collection").glob("3D - *.frag"))
MINIMAL = """#include "MathUtils.frag"
#include "DE-Raytracer.frag"
#group Shape
// The ball's radius
uniform float Radius; slider[0.1,1,2]
uniform vec3 Offset; slider[(-1,-1,-1),(0,0,0),(1,1,1)]
uniform int Steps; slider[1,3,10]
uniform bool Hollow; checkbox[true]
float DE(vec3 p) { orbitTrap = min(orbitTrap, vec4(abs(p), dot(p, p))); return length(p - Offset) - Radius; }
#preset Default
Radius = 0.75
Offset = 0.1,0,0
Eye = 0,0,-4
Target = 0,0,0
Up = 0,1,0
FOV = 0.5
#endpreset
#preset KeyFrame.001
Eye = 1,1,1
#endpreset
"""


def test_presets_metadata_and_camera_are_read():
    text = MINIMAL + "\n/*[fractalchemy]\n{\"version\": 1}\n[/fractalchemy]*/\n"
    stripped = document.strip_metadata(text)
    assert "fractalchemy" not in stripped
    presets = document.presets(stripped)
    assert list(presets) == ["Default"] and presets["Default"]["Offset"] == "0.1,0,0"
    camera = document.camera(presets["Default"])
    assert camera.eye == (0.0, 0.0, -4.0) and camera.distance == pytest.approx(4.0)
    assert camera.vertical_angle == pytest.approx(2 * np.arctan(0.5))


@pytest.mark.parametrize("line,kind,default", [
    ("uniform float Power; slider[1,8,16]", "float", 8.0),
    ("uniform double Power; slider[1,8,16] Logarithmic Locked", "float", 8.0),
    ("uniform vec2 Fold; slider[(0,0),(1,0.5),(3,3)]", "vec2", (1.0, 0.5)),
    ("uniform vec3 C; slider[(-2,-2,-2),(0.3,0.5,-0.3),(2,2,2)]", "vec3", (0.3, 0.5, -0.3)),
    ("uniform vec4 Q; slider[(0,0,0,0),(1,2,3,4),(5,5,5,5)]", "vec4", (1.0, 2.0, 3.0, 4.0)),
    ("uniform vec3 Tint; color[1,0.5,0]", "vec3", (1.0, 0.5, 0.0)),
    ("uniform vec4 Glow; color[0,0.2,1,1,0.5,0]", "vec4", (1.0, 0.5, 0.0, 0.2)),
    ("uniform int Iterations; slider[1,12,100]", "int", 12),
    ("uniform int Mode; menu[1, Alpha;Beta;Gamma]", "enum", "1"),
    ("uniform bool Julia; checkbox[true]", "bool", True),
])
def test_annotations_become_parameters(line, kind, default):
    param = annotations.parse(line, "Group", "tip")
    assert param.kind == kind and param.coerce(param.default) == default
    assert param.group == "Group" and param.description == "tip"


def test_plain_uniforms_are_not_parameters():
    assert annotations.parse("uniform float time;", "", "") is None


def test_host_includes_use_the_shim_and_library_includes_prefer_your_folders(tmp_path):
    (tmp_path / "MathUtils.frag").write_text("// mine\n")
    resolve = preprocess.resolver([tmp_path])
    assert preprocess.is_shim(resolve("DE-Raytracer-v0.9.10.frag", None))
    assert resolve("MathUtils.frag", None) == tmp_path / "MathUtils.frag"
    assert preprocess.is_shim(preprocess.resolver([tmp_path], prefer_shims=True)("MathUtils.frag", None))
    assert preprocess.is_shim(preprocess.resolver([])("Triplex.frag", None))
    with pytest.raises(FragmentError, match="Nowhere.frag"):
        resolve("Nowhere.frag", None)


def test_shims_are_included_once_and_user_includes_are_inlined(tmp_path):
    (tmp_path / "mine.frag").write_text('#include "MathUtils.frag"\nfloat helper() { return 1.0; }\n')
    main = tmp_path / "main.frag"
    main.write_text('#include "MathUtils.frag"\n#include "mine.frag"\n' + MINIMAL)
    merged = preprocess.expand(main.read_text(), main, preprocess.resolver([]))
    assert merged.count("mat3 rotationMatrix3(") == 1 and "float helper()" in merged
    stored = embeddable(main)
    assert '#include "MathUtils.frag"' in stored and "float helper()" in stored and '#include "mine.frag"' not in stored


def test_parse_handles_directives_groups_and_replacements():
    parsed = preprocess.parse('#info A test\n#vertex\nvarying vec2 x;\n#endvertex\n#replace "FOO" "1.0"\n'
                              "#group Shape\nuniform float A; slider[0,FOO,2]\nfloat DE(vec3 p) { return FOO; }")
    assert parsed.info == ["A test"] and [p.name for p in parsed.params] == ["A"]
    assert parsed.params[0].group == "Shape" and parsed.params[0].default == 1.0
    assert "varying" not in parsed.code.replace("// varying", "") and "return 1.0;" in parsed.code


def test_compat_turns_uniforms_into_globals_and_reports_textures():
    code, problems = compat.convert("uniform float A;\nuniform float time;\nuniform float time;\n"
                                    "uniform sampler2D tex;\nuniform dvec3 D;\nvoid main() { gl_FragColor = vec4(1.0LF); }",
                                    [annotations.parse("uniform float A; slider[0,1,2]", "", "")])
    assert "\nfloat A;" in code and "float time = 0.0;" in code and code.count("float time = 0.0;") == 1
    assert "vec3 D = vec3(0.0);" in code and "void iteron_fragment_main()" in code
    assert "iteron_frag_color = vec4(1.0)" in code and problems == ["textures (tex)"]


def test_a_fragment_becomes_a_formula_with_presets_and_the_cut():
    entry = build(MINIMAL, name="Ball")
    names = [p.name for p in entry.params]
    assert names[:4] == ["Radius", "Offset", "Steps", "Hollow"] and "cut" in names
    assert entry.presets["Default"] == {"Radius": 0.75, "Offset": (0.1, 0.0, 0.0)}
    assert entry.id == "fragment_ball" and entry.camera is not None
    source = entry.kernel_source(entry.values())
    assert "Radius = iteron_u.v[" in source.kernel and "vec4 iteron_kernel(vec3 pos)" in source.kernel


def test_a_fragment_that_writes_no_orbit_trap_is_told_apart():
    assert build(MINIMAL).uses_trap
    plain = MINIMAL.replace("orbitTrap = min(orbitTrap, vec4(abs(p), dot(p, p))); ", "")
    assert not build(plain).uses_trap


def test_fragments_iteron_cannot_run_say_why():
    with pytest.raises(FragmentError, match="2D"):
        build('#include "2D.frag"\nvec3 color(vec2 p) { return vec3(0.0); }\n')
    with pytest.raises(FragmentError, match="DE"):
        build('#include "DE-Raytracer.frag"\nfloat Distance(vec3 p) { return 1.0; }\n')
    with pytest.raises(FragmentError, match="textures"):
        build("uniform sampler2D tex; file[t.png]\nfloat DE(vec3 p) { return length(p) - 1.0; }\n")


def test_the_fafrag_fixture_builds():
    entry = build(FIXTURE.read_text(), FIXTURE)
    assert {"MI", "Size", "CSize", "C", "TThickness"} <= {p.name for p in entry.params}
    assert {"Default", "P3", "Kleinian Forest"} <= set(entry.presets)


# --- on a GPU (moderngl), when one is available -----------------------------------------------------------------------
@pytest.fixture(scope="module")
def ctx():
    if "bpy" in sys.modules:
        pytest.skip("inside Blender: see tests/blender/test_fragments.py")
    from .gl_harness import context
    created = context()
    if created is None:
        pytest.skip("no OpenGL 3.3 context (moderngl + EGL/llvmpipe)")
    return created


def test_a_ball_samples_as_a_ball(ctx):
    from .gl_harness import sample
    entry = build(MINIMAL)
    values = entry.values({"Radius": 0.5, "Offset": (0.0, 0.0, 0.0)})
    plan = cube_plan((0.0, 0.0, 0.0), 1.0, 16)
    out = sample(ctx, entry, values, plan)
    points = plan.slab_points(0, plan.shape[2]).reshape(plan.shape + (3,))
    assert np.allclose(out[..., 0], np.linalg.norm(points, axis=-1) - 0.5, atol=1e-5)
    assert np.allclose(out[..., 1], np.linalg.norm(points, axis=-1), atol=1e-4)        # √(orbit trap w)


def test_the_cut_applies_to_fragments(ctx):
    from .gl_harness import sample
    entry = build(MINIMAL)
    values = entry.values({"Radius": 0.5, "Offset": (0.0, 0.0, 0.0), "cut": True, "cut_axis": "X"})
    plan = cube_plan((0.0, 0.0, 0.0), 1.0, 16)
    points = plan.slab_points(0, plan.shape[2]).reshape(plan.shape + (3,))
    out = sample(ctx, entry, values, plan)
    assert np.allclose(out[..., 0], np.maximum(np.linalg.norm(points, axis=-1) - 0.5, points[..., 0]), atol=1e-5)


@pytest.mark.skipif(not COLLECTION, reason="Fractalchemy's fragment library is not in the checkout")
@pytest.mark.parametrize("path", COLLECTION, ids=lambda p: p.stem)
def test_every_collection_fragment_builds_from_the_shims_and_has_a_surface(ctx, path):
    from .gl_harness import sample
    entry = build(embeddable(path), path.stem, prefer_shims=True)
    values = entry.values(next(iter(entry.presets.values()), {}))
    plan = cube_plan(entry.camera.target if entry.camera else (0, 0, 0), entry.bounds, 32)
    distance = sample(ctx, entry, values, plan)[..., 0]
    assert np.isfinite(distance).mean() > 0.99
    assert (distance < plan.spacing).any() and (distance > plan.spacing).any()


def test_the_mathutils_shim_matches_fragm_conventions(ctx):
    """rotationMatrix3 is written from the formula; FragM's convention (m * p turns by −angle) must hold."""
    from .gl_harness import sample
    text = ('#include "MathUtils.frag"\n#include "DE-Raytracer.frag"\n'
            "float DE(vec3 p) { vec3 q = rotationMatrixXYZ(vec3(90.0, 0.0, 0.0)) * vec3(0.0, 1.0, 0.0);\n"
            "orbitTrap = vec4(q.z, 0.0, 0.0, 0.0); return q.y; }\n")
    entry = build(text)
    out = sample(ctx, entry, entry.values(), cube_plan((0.0, 0.0, 0.0), 1.0, 2))
    assert np.allclose(out[..., 0], 0.0, atol=1e-6)        # y → −z: rotating (0,1,0) by −90° about x
    assert np.allclose(out[..., 2], -1.0, atol=1e-6)
