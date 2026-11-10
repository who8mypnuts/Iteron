# SPDX-License-Identifier: MIT
"""The formulas added in the last round, against what their mathematics promises: volumes of the IFS solids,
the icosahedral fold's symmetry, known members of the hypercomplex sets, and chunks that stay in their box."""

import numpy as np
import pytest

import iteron.formulas  # noqa: F401
from iteron.core import cpu_eval, vec
from iteron.core.formula import REGISTRY, by_family
from iteron.formulas.polyhedra import MIRRORS, icosahedral_fold

RNG = np.random.default_rng(11)


def _inside(fid, points, level=0.0, **values):
    entry = REGISTRY[fid]
    return cpu_eval.evaluate(entry, entry.values(values), points)[:, 0] < level


def test_there_are_at_least_thirty_five_formulas_in_seven_families():
    assert len(REGISTRY) >= 35
    assert [family for family, _entries in by_family()] == ["Bulbs", "Boxes", "Sponges & Cubes", "Kaleidoscopic IFS",
                                                              "Hypercomplex", "Inversions", "Hybrids"]


def test_the_icosahedral_fold_is_invariant_under_the_group():
    normals = [np.array(m) / np.linalg.norm(m) for m in MIRRORS] + list(np.eye(3))
    points = RNG.normal(size=(3000, 3))
    images = points.copy()
    for _ in range(9):
        n = normals[RNG.integers(len(normals))]
        images = images - 2.0 * (images @ n)[:, None] * n
    a = icosahedral_fold(vec.make(*points.T)).a
    b = icosahedral_fold(vec.make(*images.T)).a
    assert np.abs(a - b).max() < 1e-9


@pytest.mark.parametrize("fid,values,fraction", [
    ("cantor_dust", {"iterations": 1}, 8 / 27),
    ("vicsek_cube", {"iterations": 1}, 7 / 27),
    ("vicsek_cube", {"iterations": 1, "pattern": "CORNERS"}, 9 / 27),
    ("sierpinski_square_pyramid", {"iterations": 1}, 5 / 8 / 3),     # the pyramid fills a third of its cube
])
def test_one_level_keeps_the_right_volume(fid, values, fraction):
    points = RNG.uniform(-1.0, 1.0, (200_000, 3))
    assert _inside(fid, points, **values).mean() == pytest.approx(fraction, rel=0.05)


def test_the_koch_cube_grows_from_the_cube():
    points = RNG.uniform(-0.99, 0.99, (5000, 3))
    assert _inside("koch_cube", points).all()
    assert _inside("koch_cube", np.array([[1.2, 0.0, 0.0], [0.0, -1.2, 0.0]])).all()     # children on the faces
    assert not _inside("koch_cube", np.array([[1.2, 1.2, 1.2]])).any()


def test_the_tetrabrot_slice_through_the_complex_plane_is_the_mandelbrot_set():
    members, outsiders = np.array([[-0.9, 0.0, 0.0], [-0.1, 0.2, 0.0], [0.25, 0.0, 0.0]]), np.array([[0.5, 0.0, 0.0],
                                                                                                   [-2.1, 0.0, 0.0]])
    for fid in ("tetrabrot", "quaternion_mandelbrot"):
        assert _inside(fid, members, iterations=40).all()
        assert not _inside(fid, outsiders, iterations=40).any()


@pytest.mark.parametrize("fid", ["apollonian_packing", "pseudo_kleinian", "sphere_inversion_ifs"])
def test_inversion_sets_are_cut_out_as_chunks(fid):
    outside = RNG.uniform(-2.0, 2.0, (4000, 3))
    outside = outside[np.abs(outside).max(axis=1) > 1.05]
    assert not _inside(fid, outside, level=0.02, extent=1.0).any()
    assert _inside(fid, RNG.uniform(-1.0, 1.0, (20000, 3)), level=0.02, extent=1.0).any()    # (estimates ≥ 0 here)


@pytest.mark.parametrize("fid", ["cosine_mandelbulb", "mandelbar_bulb", "burning_ship_bulb"])
def test_bulb_variants_are_their_own_shapes(fid):
    points = RNG.uniform(-1.2, 1.2, (20000, 3))
    power = {"power": 8.0}
    assert (_inside(fid, points, **power) != _inside("mandelbulb", points, **power)).mean() > 0.01


def test_the_catalogue_is_documented():
    """Thumbnails, the README's table and THIRD_PARTY.md follow the registry (tools/check_catalogue.py)."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    try:
        from check_catalogue import problems
    finally:
        sys.path.pop(0)
    assert problems() == []
