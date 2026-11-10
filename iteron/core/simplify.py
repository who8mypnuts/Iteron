# SPDX-License-Identifier: MIT
"""Fewer faces where the fractal is flat, every face where it is not: adaptive vertex clustering on the voxel octree.

After refinement every vertex lies on the surface and carries the field's normal, i.e. a tangent plane. Going up the
octree (cells of 2, 4, 8 … voxels), a cell's vertices merge into one when their planes agree — the quadric error of
the best point (the dual-contouring QEF, regularised towards the vertices' centre) stays under the tolerance and
their normals lie within a cone. A cell only merges if all its children did, so detail regions keep their full
resolution. Faces come from the fine quads, re-pointed at the merged vertices: no cracks, no T-junctions; quads
whose corners merge pairwise become triangles or vanish. Sharp creases survive because the QEF point sits on them.
After Schaefer & Warren, *Adaptive Vertex Clustering Using Octrees* (2003).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MAX_LEVEL = 5           # cells up to 32 voxels
REPAIR_PASSES = 6       # rounds of splitting clusters that made a non-manifold edge
CONE = 0.9              # mean resultant length of a cell's normals (1 = all parallel; 0.9 ≈ within ~25°)
REGULARISE = 0.02       # pull of the vertices' centre on the QEF point (dimensionless)


@dataclass
class Simplified:
    vertices: np.ndarray        # (V', 3)
    normals: np.ndarray         # (V', 3)
    channels: np.ndarray        # (V', 3)
    quads: np.ndarray           # (Q', 4)
    tris: np.ndarray            # (T', 3)


def simplify(vertices: np.ndarray, normals: np.ndarray, channels: np.ndarray, quads: np.ndarray,
             origin, spacing: float, tolerance: float, max_level: int = MAX_LEVEL) -> Simplified:
    """Merge vertices cell by cell while the surface in the cell is flat within `tolerance` (world units).

    Merging can pinch two sheets of a thin part together (an edge shared by more than two faces) or collapse a face
    so that a hole opens (an edge used once; the input is closed). The clusters touching such an edge are split back
    into their fine vertices and the faces rebuilt, until the mesh is as closed and manifold as the input."""
    cluster, positions, normals_out, channels_out = _cluster(vertices, normals, channels, origin, spacing, tolerance,
                                                             max_level)
    for _ in range(REPAIR_PASSES):
        result, used = _build(cluster, positions, normals_out, channels_out, quads)
        bad = _non_manifold_vertices(result)
        if bad.size == 0:
            break
        undo = np.isin(cluster, used[bad]) & (cluster >= len(vertices))   # merged clusters with a bad edge
        cluster[undo] = np.flatnonzero(undo)                                # back to their own fine vertices
    return result


def _build(cluster, positions, normals, channels, quads):
    """The simplified mesh for a vertex → cluster assignment, and the cluster id of each output vertex."""
    used, compact = np.unique(cluster, return_inverse=True)
    new_quads, tris = _faces(compact[quads])
    return Simplified(positions[used], normals[used], channels[used], new_quads, tris), used


def _non_manifold_vertices(mesh: "Simplified") -> np.ndarray:
    """Vertices on edges not used by exactly two faces."""
    edges = [mesh.quads[:, [i, (i + 1) % 4]] for i in range(4)] + [mesh.tris[:, [i, (i + 1) % 3]] for i in range(3)]
    edges = np.sort(np.concatenate(edges).astype(np.int64), axis=1)
    keys, counts = np.unique(edges[:, 0] * len(mesh.vertices) + edges[:, 1], return_counts=True)
    bad = keys[counts != 2]
    return np.unique(np.concatenate([bad // len(mesh.vertices), bad % len(mesh.vertices)]))


def _cluster(vertices, normals, channels, origin, spacing, tolerance, max_level):
    """Bottom-up clustering: per fine vertex its cluster id (its own index if it never merged), and per cluster id
    the position, normal and colour channels."""
    count = len(vertices)
    grid = (np.asarray(vertices, dtype=np.float64) - np.asarray(origin)) / spacing
    n = np.nan_to_num(np.asarray(normals, dtype=np.float64))
    planes = np.einsum("ij,ij->i", n, vertices)
    cluster = np.arange(count)
    positions, cluster_normals, cluster_channels = [vertices], [n], [channels]
    locked = ~np.isfinite(np.asarray(normals, dtype=np.float64)).all(axis=1)
    next_id = count
    for level in range(1, max_level + 1):
        size = 1 << level
        free = np.flatnonzero(~locked)              # locked vertices never merge again: only the rest are examined
        if free.size == 0:
            break
        keys_all = _cell_keys(grid, size)
        cells, member = np.unique(keys_all[free], return_inverse=True)
        blocked = np.isin(cells, keys_all[locked])   # a cell holding any locked vertex may not merge
        stats = _qef(vertices[free], n[free], planes[free], member, len(cells))
        lo = cells_min(cells, size) * spacing + np.asarray(origin)
        point = np.clip(stats.point, lo - 0.5 * spacing, lo + (size + 0.5) * spacing)
        flat = (stats.error(point) <= tolerance * tolerance) & (stats.resultant >= CONE)
        ok = ~blocked & (flat | (stats.count == 1))          # a lone vertex is trivially fine: it must not block its parent
        if not ok.any():
            break
        accepted = ok[member]
        locked[free[~accepted]] = True
        ids = np.full(len(cells), -1, dtype=np.int64)
        ids[ok] = next_id + np.arange(int(ok.sum()))
        next_id += int(ok.sum())
        cluster[free[accepted]] = ids[member[accepted]]
        positions.append(point[ok])
        mean_normal = stats.normal_sum[ok]
        cluster_normals.append(mean_normal / np.maximum(np.linalg.norm(mean_normal, axis=1, keepdims=True), 1e-12))
        cluster_channels.append(stats.channel_mean(channels[free], member, len(cells))[ok])
    return cluster, np.concatenate(positions), np.concatenate(cluster_normals), np.concatenate(cluster_channels)


KEY_BASE = 1 << 21          # cell coordinates are packed three to an int64 key …
KEY_SHIFT = 4               # … after this shift, so a vertex refinement moved just outside the grid stays positive


def _cell_keys(grid: np.ndarray, size: int) -> np.ndarray:
    cell = np.floor(grid / size).astype(np.int64) + KEY_SHIFT
    return (cell[:, 0] * KEY_BASE + cell[:, 1]) * KEY_BASE + cell[:, 2]


def cells_min(cells: np.ndarray, size: int) -> np.ndarray:
    """The lowest voxel corner (grid units) of each level cell, from its packed key."""
    z = cells % KEY_BASE
    y = (cells // KEY_BASE) % KEY_BASE
    x = cells // (KEY_BASE * KEY_BASE)
    return (np.stack([x, y, z], axis=1) - KEY_SHIFT).astype(np.float64) * size


class _qef:
    """Per-cell sums of the members' tangent planes and the best point for them."""

    def __init__(self, p: np.ndarray, n: np.ndarray, d: np.ndarray, member: np.ndarray, cells: int):
        def total(values):
            return np.bincount(member, weights=values, minlength=cells)
        self.count = total(np.ones(len(p)))
        self.a = np.stack([np.stack([total(n[:, i] * n[:, j]) for j in range(3)], axis=1) for i in range(3)], axis=1)
        self.b = np.stack([total(n[:, i] * d) for i in range(3)], axis=1)
        self.c = total(d * d)
        self.mass = np.stack([total(p[:, i]) for i in range(3)], axis=1) / self.count[:, None]
        self.normal_sum = np.stack([total(n[:, i]) for i in range(3)], axis=1)
        self.resultant = np.linalg.norm(self.normal_sum, axis=1) / self.count
        self.member, self.cells = member, cells
        a = self.a / self.count[:, None, None] + REGULARISE * np.eye(3)
        rhs = self.b / self.count[:, None] - np.einsum("kij,kj->ki", self.a, self.mass) / self.count[:, None]
        self.point = self.mass + np.linalg.solve(a, rhs[..., None])[..., 0]

    def error(self, x: np.ndarray) -> np.ndarray:
        """Mean squared distance of the members' planes from `x`."""
        quadratic = np.einsum("ki,kij,kj->k", x, self.a, x)
        return np.maximum(quadratic - 2.0 * np.einsum("ki,ki->k", self.b, x) + self.c, 0.0) / self.count

    def channel_mean(self, channels: np.ndarray, member: np.ndarray, cells: int) -> np.ndarray:
        return np.stack([np.bincount(member, weights=channels[:, i], minlength=cells) for i in range(channels.shape[1])],
                        axis=1) / self.count[:, None]


def _faces(q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Quads re-pointed at merged vertices → the quads that stay quads, the ones that became triangles (one pair of
    neighbouring corners merged); everything else has collapsed. Duplicates (two faces on the same corners) go."""
    a, b, c, d = q.T
    ab, bc, cd, da, ac, bd = a == b, b == c, c == d, d == a, a == c, b == d
    quads = q[~(ab | bc | cd | da | ac | bd)]
    tris = []
    for drop, pattern in ((1, ab & ~bc & ~cd & ~da & ~ac & ~bd), (2, bc & ~ab & ~cd & ~da & ~ac & ~bd),
                          (3, cd & ~ab & ~bc & ~da & ~ac & ~bd), (3, da & ~ab & ~bc & ~cd & ~ac & ~bd)):
        keep = [i for i in range(4) if i != drop]
        tris.append(q[pattern][:, keep])
    tris = np.concatenate(tris) if tris else np.zeros((0, 3), dtype=q.dtype)
    return _unique_faces(quads).astype(np.int32), _unique_faces(tris).astype(np.int32)


def _unique_faces(faces: np.ndarray) -> np.ndarray:
    """Drop faces whose corner set repeats an earlier face's: hash the sorted corners, sort by hash, compare neighbours
    exactly (several times quicker than `np.unique(axis=0)`; a hash collision can only leave a duplicate in place)."""
    if len(faces) < 2:
        return faces
    rows = np.sort(faces, axis=1).astype(np.uint64)
    key = rows[:, 0].copy()
    for column in range(1, rows.shape[1]):
        key = key * np.uint64(1_000_003) ^ rows[:, column]
    order = np.argsort(key, kind="stable")
    ordered_rows = rows[order]
    same = (key[order][1:] == key[order][:-1]) & (ordered_rows[1:] == ordered_rows[:-1]).all(axis=1)
    repeat = np.zeros(len(faces), dtype=bool)
    repeat[order[1:]] = same
    return faces[~repeat]
