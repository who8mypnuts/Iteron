# SPDX-License-Identifier: MIT
"""Surface nets: closed, manifold, outward-facing quads in the right place."""

import numpy as np
import pytest

from iteron.core.surface_nets import resolve_ambiguities, signed_volume, surface_nets


def _edges(quads):
    e = np.concatenate([quads[:, [i, (i + 1) % 4]] for i in range(4)])
    return e


def _field(n, fn):
    g = np.linspace(-1.5, 1.5, n)
    x, y, z = np.meshgrid(g, g, g, indexing="ij")
    return fn(x, y, z), g[1] - g[0]


def test_sphere_is_closed_oriented_and_placed():
    d, h = _field(48, lambda x, y, z: np.sqrt(x * x + y * y + z * z) - 1.0)
    v, q = surface_nets(d, 0.0)
    assert q.shape[1] == 4 and q.dtype == np.int32
    edges = _edges(q)
    # closed and consistently wound: every directed edge appears once and its reverse once
    directed = set(map(tuple, edges))
    assert len(directed) == edges.shape[0]
    assert all((b, a) in directed for a, b in directed)
    world = v * h - 1.5
    assert np.allclose(np.linalg.norm(world, axis=1), 1.0, atol=h)
    volume = signed_volume(world, q)
    assert volume == pytest.approx(4 / 3 * np.pi, rel=0.03)        # outward: positive


def test_box_cut_by_grid_closes():
    d, h = _field(32, lambda x, y, z: np.maximum(np.abs(x), np.maximum(np.abs(y), np.abs(z))) - 10.0)  # all inside
    v, q = surface_nets(d, 0.0)
    assert q.shape[0] > 0 and signed_volume(v, q) > 0


def test_empty_and_tiny():
    assert surface_nets(np.ones((8, 8, 8)), 0.0)[1].shape == (0, 4)
    assert surface_nets(np.ones((2, 2, 2)), 0.0)[1].shape == (0, 4)


def test_diagonal_patterns_are_resolved():
    inside = np.zeros((6, 6, 6), dtype=bool)
    inside[2, 2, 2] = inside[3, 3, 2] = True          # touching along an edge only
    fixed = resolve_ambiguities(inside)
    assert fixed[2, 3, 2] or fixed[3, 2, 2]
    d = np.where(fixed, -1.0, 1.0)
    v, q = surface_nets(d, 0.0)
    directed = set(map(tuple, _edges(q)))
    assert all((b, a) in directed for a, b in directed)
