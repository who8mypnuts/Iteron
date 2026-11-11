# SPDX-License-Identifier: MIT
"""Holons (instances along a flame with frames from the transforms' Jacobians), per-transform regions of a flame
solid, and both through the flame pipeline — checked on flames whose answers are known, and against Fractalchemy's
own holons (read from the sample sources at test time)."""

import sys
from pathlib import Path

import numpy as np
import pytest

from iteron.flames import chaos, density, holon, library
from iteron.flames.model import Flame, XForm
from iteron.jobs.flame_pipeline import MESH, POINTS, FlameSpec, InstanceSpec, build
from iteron.jobs.steps import run_to_end

ROOT = Path(__file__).resolve().parents[2]
PYRAMID = library.bundled()["sierpinski_pyramid"]


def _rotations(n, rng):
    q, _r = np.linalg.qr(rng.normal(size=(n, 3, 3)))
    q[np.linalg.det(q) < 0, :, 0] *= -1
    return q


def test_the_tree_of_a_similarity_flame_has_every_level_at_its_scale():
    tree = holon.tree_instances(Flame.from_dict(PYRAMID), depth=3)
    assert len(tree) == 4 + 16 + 64
    assert sorted(set(np.round(tree.scales, 6))) == [0.125, 0.25, 0.5]
    assert np.allclose(np.linalg.det(tree.rotations), 1.0)
    assert len(holon.tree_instances(Flame.from_dict(PYRAMID), depth=3, leaves_only=True)) == 64


def test_chaos_instances_carry_the_frames_of_their_last_transforms():
    found = holon.chaos_instances(Flame.from_dict(PYRAMID), 600, depth=4, seed=2)
    assert len(found) == 600 and np.allclose(found.scales, 0.5 ** 4)
    turned = Flame("turn", [XForm(1.0, coefs=(0.0, 0.5, -0.5, 0.0, 0.2, 0.0)),
                            XForm(1.0, coefs=(0.0, 0.5, -0.5, 0.0, -0.2, 0.0))])
    frames = holon.chaos_instances(turned, 50, depth=1)
    assert np.allclose(frames.rotations[:, :2, :2], [[0.0, -1.0], [1.0, 0.0]], atol=1e-6)   # a quarter turn
    still = holon.chaos_instances(turned, 50, depth=1, frames="TRANSLATION")
    assert np.allclose(still.rotations, np.eye(3))


def test_size_rules():
    rng = np.random.default_rng(1)
    base = holon.InstanceSet(rng.normal(size=(10, 3)), _rotations(10, rng), np.geomspace(1.0, 1e-3, 10), np.zeros(10),
                             np.zeros(10, np.int16))
    assert np.allclose(base.sized(0.1).scales, 0.1 * base.scales)
    assert np.allclose(base.sized(1.0, falloff=0.5).scales, np.sqrt(base.scales))
    assert len(base.sized(1.0, min_size=0.01)) == 7 and len(base.sized(1.0, cap=3)) == 3
    assert base.sized(1.0, cap=3).scales.min() == pytest.approx(base.scales[2])


def test_euler_angles_rebuild_the_rotations():
    rotations = _rotations(200, np.random.default_rng(3))
    x, y, z = holon.euler_xyz(rotations).T
    cx, sx, cy, sy, cz, sz = np.cos(x), np.sin(x), np.cos(y), np.sin(y), np.cos(z), np.sin(z)
    rebuilt = np.stack([np.stack([cy * cz, sx * sy * cz - cx * sz, cx * sy * cz + sx * sz], -1),
                        np.stack([cy * sz, sx * sy * sz + cx * cz, cx * sy * sz - sx * cz], -1),
                        np.stack([-sy, sx * cy, cx * cy], -1)], axis=1)
    assert np.allclose(rebuilt, rotations, atol=1e-9)


def test_the_pipeline_places_instances_in_blenders_space():
    spec = FlameSpec(PYRAMID, 20_000, output=POINTS,
                     instances=InstanceSpec(mode="TREE", depth=2, size=0.2, min_size=0.0))
    result = run_to_end(build(spec))
    assert len(result.instances) == 20 and result.instance_colours.shape == (20, 3)
    assert np.allclose(np.linalg.det(result.instances.rotations), 1.0)
    raw = holon.tree_instances(Flame.from_dict(PYRAMID), 2)
    assert np.allclose(result.instances.positions, raw.positions * [1.0, -1.0, 1.0])
    assert np.allclose(result.instances.scales, 0.2 * raw.scales)


def test_each_part_of_a_solid_knows_its_transform():
    rng = np.random.default_rng(5)
    left = rng.normal(size=(60_000, 3)) * 0.2 + [-1.0, 0.0, 0.0]
    right = rng.normal(size=(60_000, 3)) * 0.2 + [1.0, 0.0, 0.0]
    orbit = chaos.Orbit(np.concatenate([left, right]).astype(np.float32), np.full(120_000, 0.5, np.float32),
                        np.repeat(np.array([0, 1], np.int16), 60_000), chaos.palette_array([(255, 255, 255)] * 2), ())
    vertices, _quads, _colours, plan = density.density_mesh(orbit, 64, 0.15, 1.0)
    which = density.dominant_xform(orbit, plan, (vertices - np.asarray(plan.origin)) / plan.spacing, 1.0)
    assert (which[vertices[:, 0] < -0.5] == 0).all() and (which[vertices[:, 0] > 0.5] == 1).all()
    solid = run_to_end(build(FlameSpec(PYRAMID, 100_000, output=MESH, resolution=40)))
    assert set(np.unique(solid.xform)) == {0, 1, 2, 3}


@pytest.fixture(scope="module")
def theirs():
    source = ROOT / "sample_source" / "Fractalchemy"
    if not (source / "fractalchemy").is_dir():
        pytest.skip("Fractalchemy's sources are not in the checkout")
    sys.path.insert(0, str(source))
    try:
        from fractalchemy.fractal.scene import Flame as TheirFlame
        from fractalchemy.solid import holon as their_holon
    except Exception as error:                     # pragma: no cover - depends on the sample checkout
        pytest.skip(f"Fractalchemy does not import here: {error}")
    finally:
        sys.path.remove(str(source))
    return their_holon, TheirFlame


CURVED = {"name": "curved", "xforms": [
    {"weight": 1.0, "coefs": [0.5, 0.1, -0.1, 0.5, 0.3, 0.0], "variations": {"spherical": 0.6, "linear": 0.4}},
    {"weight": 1.0, "coefs": [0.4, 0.0, 0.0, 0.6, -0.3, 0.2], "variations": {"swirl": 0.5, "linear": 0.5, "zscale": 0.3}},
    {"weight": 0.5, "coefs": [0.5, 0.0, 0.0, 0.5, 0.0, -0.4], "variations": {"curl": 0.7, "linear": 0.3},
     "params": {"curl_c1": 0.2, "curl_c2": 0.1}}]}


@pytest.mark.parametrize("flame", [PYRAMID, CURVED], ids=["pyramid", "curved"])
def test_the_tree_matches_fractalchemys(theirs, flame):
    """(On flames without random variations: those depend on each program's random stream.)"""
    their_holon, their_flame = theirs
    mine = holon.tree_instances(Flame.from_dict(flame), depth=3)
    other = their_holon.tree_instances(their_flame.from_dict(flame), depth=3)
    finite = np.isfinite(other.positions).all(axis=1)
    assert len(mine) == int(finite.sum())
    assert np.allclose(mine.positions, other.positions[finite], rtol=1e-6, atol=1e-9)
    assert np.allclose(mine.scales, other.scales[finite], rtol=1e-5)
    assert np.allclose(mine.rotations, other.rotations[finite], atol=1e-6)
