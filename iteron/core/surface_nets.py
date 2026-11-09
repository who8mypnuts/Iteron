# SPDX-License-Identifier: MIT
"""The isosurface of a sampled distance field as a quad mesh: *naive surface nets*, vectorised in numpy.

Ported from Fractalchemy (`solid/isosurface.py`) and made sparse: everything after the inside/outside test is
built from the crossing edges alone, so memory follows the surface, not the volume. One vertex per surface cube
(the mean of its edges' crossings), one quad per crossing edge joining the four cubes around it, wound so normals
point outwards. Quads are kept as quads — what Blender prefers. The grid's outer layer counts as outside, so the
surface always closes, and diagonal voxel patterns are filled first (`resolve_ambiguities`), so every edge is
shared by exactly two quads.
"""

from __future__ import annotations

import numpy as np

_CORNERS = ((-1, -1), (0, -1), (0, 0), (-1, 0))     # the cubes around an edge, counter-clockwise


def surface_nets(distance: np.ndarray, iso: float) -> tuple[np.ndarray, np.ndarray]:
    """`(vertices, quads)` of the surface `distance == iso` (inside where `distance < iso`).

    Vertices are `(V, 3)` float64 in grid coordinates (multiply by the spacing, add the origin); quads `(Q, 4)` int32.
    Cubes are named by the flat grid index of their lowest corner, so every lookup is integer arithmetic.
    """
    d = np.asarray(distance, dtype=np.float32)
    if min(d.shape) < 3:
        return np.zeros((0, 3)), np.zeros((0, 4), dtype=np.int32)
    inside = resolve_ambiguities(_closed(d < iso))
    flat_d, flat_inside = d.ravel(), inside.ravel()
    strides = np.array([d.shape[1] * d.shape[2], d.shape[2], 1], dtype=np.int64)
    active = np.zeros(d.size, dtype=bool)
    edges = []                                         # per axis: (corner cube keys (E, 4), crossing points (E, 3))
    for axis in range(3):
        crossing = np.zeros(d.shape, dtype=bool)
        crossing[_take_index(axis, 0, -1)] = _take(inside, axis, 0, -1) != _take(inside, axis, 1, None)
        start = np.flatnonzero(crossing)
        del crossing
        if start.size == 0:
            continue
        d0, d1 = flat_d[start], flat_d[start + strides[axis]]
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.clip(np.nan_to_num((iso - d0) / (d1 - d0), nan=0.5), 0.0, 1.0).astype(np.float32)
        point = np.stack(np.unravel_index(start, d.shape), axis=1).astype(np.float32)
        point[:, axis] += t
        others = ((axis + 1) % 3, (axis + 2) % 3)       # cyclic, so every axis winds the same way
        keys = np.stack([start + da * strides[others[0]] + db * strides[others[1]] for da, db in _CORNERS], axis=1)
        outward = flat_inside[start]                   # inside at the low end: the surface faces +axis
        keys[~outward] = keys[~outward][:, ::-1]
        active[keys.ravel()] = True
        edges.append((keys, point))
    if not edges:
        return np.zeros((0, 3)), np.zeros((0, 4), dtype=np.int32)
    cubes = np.flatnonzero(active)                     # sorted: no sort needed to number the vertices
    del active
    sums = np.zeros((cubes.size, 3), dtype=np.float64)
    counts = np.zeros(cubes.size, dtype=np.float64)
    quads = []
    for keys, point in edges:
        ids = np.searchsorted(cubes, keys).astype(np.int32)
        quads.append(ids)
        for corner in range(4):
            counts += np.bincount(ids[:, corner], minlength=cubes.size)
            for c in range(3):
                sums[:, c] += np.bincount(ids[:, corner], weights=point[:, c], minlength=cubes.size)
    return sums / counts[:, None], np.concatenate(quads)


def _closed(inside: np.ndarray) -> np.ndarray:
    inside = inside.copy()
    inside[0], inside[-1] = False, False
    inside[:, 0], inside[:, -1] = False, False
    inside[:, :, 0], inside[:, :, -1] = False, False
    return inside


def resolve_ambiguities(inside: np.ndarray, max_passes: int = 16) -> np.ndarray:
    """Fill the diagonal 2 × 2 patterns (two inside voxels touching only along an edge) on every grid face.

    Such a face has all four of its edges crossing, so the four quads around them would share one cube-to-cube
    edge — a non-manifold edge. Filling the two outside voxels of each pattern makes every face unambiguous;
    a few passes settle the patterns the fills create. The outermost layer stays outside.
    """
    inside = inside.copy()
    for _ in range(max_passes):
        changed = False
        for axis in range(3):
            a, b = [o for o in range(3) if o != axis]
            s00, s10 = _shift2(inside, a, b, 0, 0), _shift2(inside, a, b, 1, 0)
            s01, s11 = _shift2(inside, a, b, 0, 1), _shift2(inside, a, b, 1, 1)
            diagonal = (s00 & s11 & ~s10 & ~s01) | (~s00 & ~s11 & s10 & s01)
            if not diagonal.any():
                continue
            changed = True
            fill = np.zeros_like(inside)
            for da, db in ((0, 0), (1, 0), (0, 1), (1, 1)):
                index = [slice(None)] * 3
                index[a] = slice(da, inside.shape[a] - 1 + da)
                index[b] = slice(db, inside.shape[b] - 1 + db)
                fill[tuple(index)] |= diagonal
            inside |= fill
        inside = _closed(inside)
        if not changed:
            break
    return inside


def _shift2(a: np.ndarray, axis_a: int, axis_b: int, da: int, db: int) -> np.ndarray:
    index = [slice(None)] * 3
    index[axis_a] = slice(da, a.shape[axis_a] - 1 + da)
    index[axis_b] = slice(db, a.shape[axis_b] - 1 + db)
    return a[tuple(index)]


def _take_index(axis: int, start: int, stop: int | None) -> tuple:
    index = [slice(None)] * 3
    index[axis] = slice(start, stop)
    return tuple(index)


def _take(a: np.ndarray, axis: int, start: int, stop: int | None) -> np.ndarray:
    return a[_take_index(axis, start, stop)]


def signed_volume(vertices: np.ndarray, quads: np.ndarray) -> float:
    """Volume enclosed by the (closed) quad mesh; positive when the quads face outwards."""
    a, b, c, d = (vertices[quads[:, i]] for i in range(4))
    return float((np.einsum("ij,ij->i", a, np.cross(b, c)) + np.einsum("ij,ij->i", a, np.cross(c, d))).sum() / 6.0)
