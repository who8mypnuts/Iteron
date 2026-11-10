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


def test_blocks_give_the_same_mesh_as_the_whole_grid():
    from iteron.core.surface_nets import assemble, crossings
    d, _h = _field(40, lambda x, y, z: np.sin(3 * x) * np.cos(3 * y) + np.sin(3 * y) * np.cos(3 * z)
                   + np.sin(3 * z) * np.cos(3 * x) + 0.3)
    whole_v, whole_q = surface_nets(d, 0.0)
    keys, points, block, halo = [], [], 9, 2
    for i in range(0, 40, block):
        for j in range(0, 40, block):
            for k in range(0, 40, block):
                start = np.array([i, j, k])
                lo = np.maximum(start - halo, 0)
                hi = np.minimum(start + block + 1 + halo, 40)
                sub = d[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
                kb, pb = crossings(sub, 0.0, lo, np.minimum(start + block, 40), start, d.shape)
                keys.append(kb)
                points.append(pb)
    v, q = assemble(keys, points)
    assert len(q) == len(whole_q) and len(v) == len(whole_v)
    as_set = lambda verts, quads: {tuple(sorted(map(tuple, np.round(verts[face], 5)))) for face in quads}
    assert as_set(v, q) == as_set(whole_v, whole_q)
