# SPDX-License-Identifier: MIT
"""Fragments' textures (`uniform sampler2D t; file[…]`) and their own colour (`#define providesColor` +
`baseColor(p, n)`): parsed, found on disk, bound and sampled (through moderngl when an OpenGL context exists)."""

import sys

import numpy as np
import pytest

from iteron.fragments.formula import build, texture_paths
from iteron.fragments.preprocess import FragmentError
from iteron.jobs.pipeline import BuildSpec
from iteron.jobs.pipeline import build as build_mesh
from iteron.jobs.steps import run_to_end

TEXTURED = """#include "DE-Raytracer.frag"
uniform sampler2D bumps; file[bumps.png]
uniform float Radius; slider[0.1,0.5,1]
float DE(vec3 p) { return length(p) - Radius * 2.0 * texture2D(bumps, vec2(0.25, 0.75)).r; }
"""
COLOURED = """#define providesColor
#include "DE-Raytracer.frag"
float DE(vec3 p) { return length(p) - 0.6; }
vec3 baseColor(vec3 p, vec3 n) { return n.x > 0.0 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 0.0, 1.0); }
"""


def test_texture_uniforms_are_parsed_and_found(tmp_path):
    entry = build(TEXTURED)
    assert entry.textures == (("bumps", "bumps.png"),) and "Radius" in {p.name for p in entry.params}
    assert entry.kernel_source(entry.values()).samplers == ("bumps",)
    assert "texture(bumps" in entry.code and "uniform sampler2D" not in entry.code
    fragment = tmp_path / "textured.frag"
    fragment.write_text(TEXTURED)
    with pytest.raises(FragmentError, match="bumps.png"):
        texture_paths(entry, fragment)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "bumps.png").write_bytes(b"png")
    assert texture_paths(entry, fragment, (str(tmp_path / "lib"),)) == {"bumps": tmp_path / "lib" / "bumps.png"}


def test_provides_color_needs_the_define_and_the_function():
    assert build(COLOURED).provides_color
    assert not build(COLOURED.replace("#define providesColor", "")).provides_color


@pytest.fixture(scope="module")
def gl():
    if "bpy" in sys.modules:
        pytest.skip("inside Blender: see tests/blender/test_fragments.py")
    from iteron.cli.gl_sampler import context
    ctx = context()
    if ctx is None:
        pytest.skip("no OpenGL 3.3 context (moderngl + EGL/llvmpipe)")
    return ctx


def test_a_textured_fragment_samples_its_texture(gl):
    from iteron.cli.gl_sampler import GlSampler
    entry = build(TEXTURED)
    image = np.zeros((4, 4, 4), np.float32)
    image[2:, :2] = 0.8                                          # the texel at (0.25, 0.75): rows from the bottom
    sampler = GlSampler(gl, {"bumps": image})
    out = run_to_end(sampler.evaluate(entry, entry.values(), np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])))
    assert out[:, 0] == pytest.approx([-0.8, 0.2], abs=1e-5)    # radius 0.5 · 2 · 0.8
    with pytest.raises(RuntimeError, match="bumps"):
        run_to_end(GlSampler(gl).evaluate(entry, entry.values(), np.zeros((1, 3))))


def test_base_color_colours_the_mesh(gl):
    from iteron.cli.gl_sampler import GlSampler
    entry = build(COLOURED)
    result = run_to_end(build_mesh(BuildSpec(entry.id, {}, resolution=40, refine_steps=1, simplify=0.3), GlSampler(gl),
                                   entry))
    assert result.base_colours is not None and result.base_colours.shape == (len(result.vertices), 3)
    right, left = result.vertices[:, 0] > 0.1, result.vertices[:, 0] < -0.1
    assert np.allclose(result.base_colours[right], (1.0, 0.0, 0.0)) and np.allclose(result.base_colours[left],
                                                                                     (0.0, 0.0, 1.0))
    plain = build(COLOURED.replace("#define providesColor", ""))
    assert run_to_end(build_mesh(BuildSpec(plain.id, {}, resolution=24, refine_steps=0), GlSampler(gl),
                                 plain)).base_colours is None


def test_the_command_line_loads_textures_and_writes_base_colours(gl, tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    from iteron.cli import writers
    from iteron.cli.commands import main
    Image.new("RGB", (4, 4), (204, 204, 204)).save(tmp_path / "bumps.png")
    (tmp_path / "textured.frag").write_text(TEXTURED)
    out = tmp_path / "t.ply"
    assert main(["fragment", str(tmp_path / "textured.frag"), "-r", "32", "--refine", "0", "-o", str(out), "-q"]) == 0
    assert writers.read_ply_header(out)["face"] > 100
    (tmp_path / "coloured.frag").write_text(COLOURED)
    obj = tmp_path / "c.obj"
    assert main(["fragment", str(tmp_path / "coloured.frag"), "-r", "32", "--refine", "0", "-o", str(obj), "-q"]) == 0
    colours = np.array([[float(v) for v in line.split()[4:7]] for line in obj.read_text().splitlines()
                        if line.startswith("v ")])
    assert np.allclose(colours[:, 1], 0.0) and np.allclose(colours[:, 0] + colours[:, 2], 1.0, atol=1e-3)
    assert (colours[:, 0] == 1.0).any() and (colours[:, 2] == 1.0).any()     # (simplification blends the seam)
