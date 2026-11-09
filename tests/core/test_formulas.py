# SPDX-License-Identifier: MIT
"""The formulas compute the sets they claim to, and every preset produces a usable field."""

import numpy as np
import pytest

import iteron.formulas  # noqa: F401
from iteron.core import cpu_eval
from iteron.core.formula import REGISTRY

RNG = np.random.default_rng(7)


def _inside(fid, points, **values):
    entry = REGISTRY[fid]
    return cpu_eval.evaluate(entry, entry.values(values), points)[:, 0] < 0.0


def _menger_member(points, level, drop=lambda ones: ones >= 2):
    """Exact membership: remove a cell when `drop(number of middle ternary digits)` at any level."""
    u = (points + 1.0) / 2.0
    keep = np.all((u >= 0) & (u <= 1), axis=1)
    for _ in range(level):
        u = u * 3.0
        digits = np.floor(u).astype(int) % 3
        keep &= ~drop((digits == 1).sum(axis=1))
        u = u - np.floor(u)
    return keep


def _away_from_cell_walls(points, level, margin=0.01):
    u = (points + 1.0) / 2.0 * 3 ** level
    return np.all(np.abs(u - np.round(u)) > margin * 3 ** level / 27, axis=1)


@pytest.mark.parametrize("level", [1, 2, 3])
def test_menger_matches_exact_membership(level):
    pts = RNG.uniform(-1.05, 1.05, (40000, 3))
    ok = _away_from_cell_walls(pts, level)
    assert (_inside("menger_sponge", pts, iterations=level)[ok] == _menger_member(pts, level)[ok]).mean() > 0.999


@pytest.mark.parametrize("level", [1, 2])
def test_mosely_matches_exact_membership(level):
    # Mosely (centre dropped): a cell goes when its digits are all non-middle (a corner) or all middle (the centre)
    pts = RNG.uniform(-1.05, 1.05, (40000, 3))
    ok = _away_from_cell_walls(pts, level)
    member = _menger_member(pts, level, drop=lambda ones: (ones == 0) | (ones == 3))
    assert (_inside("mosely_snowflake", pts, iterations=level)[ok] == member[ok]).mean() > 0.999


def test_mosely_removed_corners_leave_no_skin():
    # just inside the cube's face, in a removed corner: the nearest solid is a third of the cube away
    entry = REGISTRY["mosely_snowflake"]
    distance = cpu_eval.evaluate(entry, entry.values({"iterations": 1}), np.array([[0.99, 0.9, 0.9]]))[0, 0]
    assert distance > 0.3


def test_mandelbulb_power_2_contains_origin_and_excludes_far_points():
    assert _inside("mandelbulb", np.array([[0.0, 0.0, 0.0], [-0.5, 0.0, 0.0]])).all()
    assert not _inside("mandelbulb", np.array([[1.3, 0.0, 0.0], [0.0, 0.0, 1.3]])).any()


def test_sierpinski_volume_halves_per_level():
    pts = RNG.uniform(-1.0, 1.0, (200000, 3))
    fractions = [_inside("sierpinski_tetrahedron", pts, iterations=n).mean() for n in (1, 2, 3)]
    # a regular tetrahedron fills 1/3 of its bounding cube; each level keeps half the volume
    assert fractions[0] == pytest.approx(1 / 6, rel=0.05)
    assert fractions[1] == pytest.approx(1 / 12, rel=0.07)
    assert fractions[2] == pytest.approx(1 / 24, rel=0.1)


@pytest.mark.parametrize("fid,preset", [(f, p) for f, e in REGISTRY.items() for p in e.presets])
def test_every_preset_has_a_surface(fid, preset):
    entry = REGISTRY[fid]
    b = entry.bounds
    pts = RNG.uniform(-b, b, (20000, 3))
    out = cpu_eval.evaluate(entry, entry.values(entry.presets[preset]), pts)
    assert np.isfinite(out).all()
    near = out[:, 0] < 0.005 * b          # (linear estimates are very conservative far out, so keep this tight)
    assert 0.0005 < near.mean() < 0.98, f"{fid}/{preset}: no surface inside its bounds"
