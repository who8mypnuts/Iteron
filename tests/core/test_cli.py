# SPDX-License-Identifier: MIT
"""The command line and its file writers: formulas, flames and (with moderngl) fragments to PLY and OBJ."""

import sys
from pathlib import Path

import numpy as np
import pytest

from iteron.cli import writers
from iteron.cli.commands import main

ROOT = Path(__file__).resolve().parents[2]
FRAGMENT = ROOT / "tests" / "fixtures" / "fractalchemy" / "PseudoKleinian.fafrag"


def test_writers_keep_quads_triangles_colours_and_normals(tmp_path):
    vertices = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
    quads, tris = np.array([[0, 1, 2, 3]]), np.array([[0, 1, 4]])
    colours = np.linspace(0, 1, 15).reshape(5, 3)
    normals = np.tile([0.0, 0.0, 1.0], (5, 1))
    ply = writers.write(tmp_path / "m.ply", vertices, [quads, tris], colours, normals)
    assert writers.read_ply_header(ply) == {"vertex": 5, "face": 2}
    header_end = ply.read_bytes().index(b"end_header\n") + len(b"end_header\n")
    body = ply.read_bytes()[header_end:]
    assert len(body) == 5 * (6 * 4 + 3) + (1 + 4 * 4) + (1 + 3 * 4)
    obj = writers.write(tmp_path / "m.obj", vertices, [quads, tris], colours, normals)
    lines = obj.read_text().splitlines()
    assert sum(l.startswith("v ") for l in lines) == 5 and sum(l.startswith("vn ") for l in lines) == 5
    assert "f 1//1 2//2 3//3 4//4" in lines and "f 1//1 2//2 5//5" in lines
    with pytest.raises(ValueError):
        writers.write(tmp_path / "m.stl", vertices, [quads])


def test_formulas_are_listed(capsys):
    assert main(["formulas"]) == 0
    assert "mandelbulb" in capsys.readouterr().out


def test_a_formula_meshes_to_a_file(tmp_path):
    out = tmp_path / "bulb.ply"
    assert main(["mesh", "mandelbulb", "-s", "power=6", "-r", "40", "--refine", "1", "-o", str(out), "-q"]) == 0
    counts = writers.read_ply_header(out)
    assert counts["vertex"] > 500 and counts["face"] > 500


def test_bad_parameters_are_reported(tmp_path, capsys):
    assert main(["mesh", "mandelbulb", "-s", "nonsense=1", "-o", str(tmp_path / "x.ply"), "-q"]) == 2
    assert "nonsense" in capsys.readouterr().err


def test_a_flame_writes_points_or_a_solid(tmp_path):
    points, solid = tmp_path / "p.ply", tmp_path / "s.obj"
    assert main(["flame", "sierpinski_pyramid", "-n", "20000", "-o", str(points), "-q"]) == 0
    assert writers.read_ply_header(points) == {"vertex": 20000, "face": 0}
    assert main(["flame", "sierpinski_pyramid", "--solid", "-n", "200000", "-r", "40", "-o", str(solid), "-q"]) == 0
    assert any(line.startswith("f ") for line in solid.read_text().splitlines())


def test_a_fragment_meshes_on_the_gpu(tmp_path):
    if "bpy" in sys.modules:
        pytest.skip("inside Blender (moderngl and Blender's OpenGL don't share a process)")
    from iteron.cli.gl_sampler import context
    if context() is None:
        pytest.skip("no OpenGL 3.3 context (moderngl + EGL/llvmpipe)")
    out = tmp_path / "pk.ply"
    assert main(["fragment", str(FRAGMENT), "-r", "40", "--refine", "1", "-o", str(out), "-q"]) == 0
    assert writers.read_ply_header(out)["face"] > 100
