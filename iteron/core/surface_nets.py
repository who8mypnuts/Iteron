# SPDX-License-Identifier: MIT
"""The isosurface of a sampled distance field as a quad mesh: *naive surface nets*, vectorised in numpy.

Ported from Fractalchemy (`solid/isosurface.py`) and reorganised for blocks: `crossings` extracts the crossing
edges of one block of a large grid (named by their global grid index), `assemble` turns every block's crossings into
one mesh — so memory follows the surface, never the whole volume. One vertex per surface cube (the mean of its
edges' crossings), one quad per crossing edge joining the four cubes around it, wound so normals point outwards.
Quads are kept as quads — what Blender prefers. The grid's outer layer counts as outside, so the surface always
closes, and diagonal voxel patterns are filled first (`resolve_ambiguities`), so every edge is shared by exactly two
quads.
"""

from __future__ import annotations

import numpy as np

_CORNERS = ((-1, -1), (0, -1), (0, 0), (-1, 0))     # the cubes around an edge, counter-clockwise
AMBIGUITY_PASSES = 8     # fill passes (8 settles what 16 would); each reaches one voxel further: blocks need this halo


def surface_nets(distance: np.ndarray, iso: float) -> tuple[np.ndarray, np.ndarray]:
    """`(vertices, quads)` of the surface `distance == iso` of one whole grid (inside where `distance < iso`).

    Vertices are `(V, 3)` float64 in grid coordinates; quads `(Q, 4)` int32.
    """
    d = np.asarray(distance, dtype=np.float32)
    if min(d.shape) < 3:
        return np.zeros((0, 3)), np.zeros((0, 4), dtype=np.int32)
    keys, points = crossings(d, iso, (0, 0, 0), d.shape, (0, 0, 0), d.shape)
    return assemble([keys], [points], d.size)


def crossings(d: np.ndarray, iso: float, offset, core_stop, core_start, shape) -> tuple[np.ndarray, np.ndarray]:
    """The crossing edges of a block.

    `d` holds samples of the global grid (`shape`) starting at global index `offset` (it may include a halo).
    Edges are returned when their low end lies in the core `core_start <= index < core_stop` (global indices), so
    neighbouring blocks never report the same edge. Returns `(keys (E, 4) int64, points (E, 3) float32)`: the four
    cubes around each edge, in winding order, as flat indices of the global grid, and the crossing point in global
    grid coordinates.
    """
    d = np.asarray(d, dtype=np.float32)
    offset, shape = np.asarray(offset, dtype=np.int64), np.asarray(shape, dtype=np.int64)
    outside = _global_boundary(d.shape, offset, shape)
    inside = resolve_ambiguities((d < iso) & ~outside, outside)
    strides = np.array([shape[1] * shape[2], shape[2], 1], dtype=np.int64)
    local = np.array(d.shape)
    lo = np.maximum(np.asarray(core_start) - offset, 0)
    keys, points = [], []
    for axis in range(3):
        hi = np.minimum(np.asarray(core_stop) - offset, local)
        hi[axis] = min(hi[axis], local[axis] - 1)                # the edge's high end must be in the block too
        window = tuple(slice(int(a), int(b)) for a, b in zip(lo, hi))
        ahead = list(window)
        ahead[axis] = slice(int(lo[axis]) + 1, int(hi[axis]) + 1)
        crossing = inside[window] != inside[tuple(ahead)]
        where = np.nonzero(crossing)
        if where[0].size == 0:
            continue
        low = np.stack(where, axis=1) + lo                      # local indices of the edges' low ends
        step = np.zeros(3, dtype=np.int64)
        step[axis] = 1
        d0, d1 = d[tuple(low.T)], d[tuple((low + step).T)]
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.clip(np.nan_to_num((iso - d0) / (d1 - d0), nan=0.5), 0.0, 1.0).astype(np.float32)
        global_low = low + offset
        point = global_low.astype(np.float32)
        point[:, axis] += t
        start = global_low @ strides
        others = ((axis + 1) % 3, (axis + 2) % 3)              # cyclic, so every axis winds the same way
        corner_keys = np.stack([start + da * strides[others[0]] + db * strides[others[1]] for da, db in _CORNERS], axis=1)
        outward = inside[tuple(low.T)]                          # inside at the low end: the surface faces +axis
        corner_keys[~outward] = corner_keys[~outward][:, ::-1]
        keys.append(corner_keys)
        points.append(point)
    if not keys:
        return np.zeros((0, 4), dtype=np.int64), np.zeros((0, 3), dtype=np.float32)
    return np.concatenate(keys), np.concatenate(points)


DENSE_LIMIT = 1 << 28      # grids up to this many voxels number their cubes with a dense mask (fast); larger sort


def assemble(keys: list[np.ndarray], points: list[np.ndarray], grid_size: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Every block's crossings → `(vertices (V, 3) float64 grid coordinates, quads (Q, 4) int32)`.

    `grid_size` (the grid's voxel count) allows the dense numbering of surface cubes when it is small enough."""
    keys = [k for k in keys if len(k)]
    if not keys:
        return np.zeros((0, 3)), np.zeros((0, 4), dtype=np.int32)
    all_keys = np.concatenate(keys)
    all_points = np.concatenate([p for p in points if len(p)])
    if 0 < grid_size <= DENSE_LIMIT:                           # each surface cube is one vertex
        active = np.zeros(grid_size, dtype=bool)
        active[all_keys.ravel()] = True
        cubes = np.flatnonzero(active)                         # sorted, so searchsorted numbers them
        del active
        ids = np.searchsorted(cubes, all_keys).astype(np.int32)
    else:
        cubes, ids = np.unique(all_keys, return_inverse=True)
        ids = ids.reshape(all_keys.shape).astype(np.int32)
    sums = np.zeros((cubes.size, 3), dtype=np.float64)
    counts = np.zeros(cubes.size, dtype=np.float64)
    for corner in range(4):
        counts += np.bincount(ids[:, corner], minlength=cubes.size)
        for c in range(3):
            sums[:, c] += np.bincount(ids[:, corner], weights=all_points[:, c], minlength=cubes.size)
    return sums / counts[:, None], ids


def _global_boundary(local_shape, offset: np.ndarray, shape: np.ndarray) -> np.ndarray:
    """The voxels of a block on (or beyond) the global grid's outermost layers: they always count as outside."""
    outside = np.zeros(local_shape, dtype=bool)
    for axis in range(3):
        index = np.arange(local_shape[axis]) + offset[axis]
        layer = (index <= 0) | (index >= shape[axis] - 1)
        if layer.any():
            selector = [slice(None)] * 3
            selector[axis] = layer
            outside[tuple(selector)] = True
    return outside


def resolve_ambiguities(inside: np.ndarray, outside: np.ndarray | None = None,
                        max_passes: int = AMBIGUITY_PASSES) -> np.ndarray:
    """Fill the diagonal 2 × 2 patterns (two inside voxels touching only along an edge) on every grid face.

    Such a face has all four of its edges crossing, so the four quads around them would share one cube-to-cube
    edge — a non-manifold edge. Filling the two outside voxels of each pattern makes every face unambiguous;
    a few passes settle the patterns the fills create.
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
            if outside is not None:
                inside &= ~outside
        if not changed:
            break
    return inside


def _shift2(a: np.ndarray, axis_a: int, axis_b: int, da: int, db: int) -> np.ndarray:
    index = [slice(None)] * 3
    index[axis_a] = slice(da, a.shape[axis_a] - 1 + da)
    index[axis_b] = slice(db, a.shape[axis_b] - 1 + db)
    return a[tuple(index)]


def signed_volume(vertices: np.ndarray, quads: np.ndarray) -> float:
    """Volume enclosed by the (closed) quad mesh; positive when the quads face outwards."""
    a, b, c, d = (vertices[quads[:, i]] for i in range(4))
    return float((np.einsum("ij,ij->i", a, np.cross(b, c)) + np.einsum("ij,ij->i", a, np.cross(c, d))).sum() / 6.0)
