# SPDX-License-Identifier: MIT
"""The Iteron mark's geometry: a Menger sponge in isometric projection, as seamless flat regions.

In an isometric view every voxel edge lies on a triangular lattice, so the picture is exactly a colouring of
lattice triangles. Voxel faces are painted into the lattice in painter's order (increasing `i + j + k`, exact for
an isometric view of a grid), which resolves occlusion — the tunnels show their inner walls like the real solid —
and the triangles of each colour are then merged into one outline, so no seams appear between faces.

Lattice coordinates: a point (x, y, z) sits at (a, b) = (x − z, y − z); triangles are `(a, b, "R")` =
{(a,b), (a+1,b), (a+1,b+1)} and `(a, b, "L")` = {(a,b), (a+1,b+1), (a,b+1)}, both counter-clockwise in (a, b).
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Callable, Hashable

COS30 = math.cos(math.radians(30))

Point = tuple[int, int]


def menger_voxels(level: int) -> set[tuple[int, int, int]]:
    """The voxels of a level-`level` Menger sponge on a 3^level grid."""
    size = 3 ** level
    return {(i, j, k) for i in range(size) for j in range(size) for k in range(size) if _kept(i, j, k, level)}


def _kept(i: int, j: int, k: int, level: int) -> bool:
    for _ in range(level):
        if (i % 3 == 1) + (j % 3 == 1) + (k % 3 == 1) >= 2:
            return False
        i, j, k = i // 3, j // 3, k // 3
    return True


def project(x: float, y: float, z: float) -> tuple[float, float]:
    """Isometric projection: +x runs down-right, +y down-left, +z up (screen y grows downwards)."""
    return (x - y) * COS30, (x + y) * 0.5 - z


def to_screen(point: Point) -> tuple[float, float]:
    return project(point[0], point[1], 0.0)


# the faces the viewer at (+1, +1, +1) sees: axis of the normal, and the face's two triangles relative to (A, B)
# where A = i − k, B = j − k of the voxel (i, j, k)
_FACE_TRIANGLES = {
    "top": (2, ((-1, -1, "R"), (-1, -1, "L"))),
    "right": (0, ((0, -1, "L"), (0, 0, "R"))),
    "left": (1, ((-1, 0, "R"), (0, 0, "L"))),
}


def paint(voxels: set[tuple[int, int, int]], size: int) -> dict[tuple[int, int, str], tuple[str, int]]:
    """Lattice triangle → (orientation, depth) of the face seen there; depth counts voxel layers between the face
    and the sponge's outer surface along its normal."""
    seen = {}
    for voxel in sorted(voxels, key=lambda v: (sum(v), v)):
        i, j, k = voxel
        for name, (axis, triangles) in _FACE_TRIANGLES.items():
            neighbour = list(voxel)
            neighbour[axis] += 1
            if tuple(neighbour) in voxels:
                continue
            depth = size - 1 - voxel[axis]
            for da, db, kind in triangles:
                seen[(i - k + da, j - k + db, kind)] = (name, depth)
    return seen


def _corners(triangle: tuple[int, int, str]) -> tuple[Point, Point, Point]:
    a, b, kind = triangle
    return ((a, b), (a + 1, b), (a + 1, b + 1)) if kind == "R" else ((a, b), (a + 1, b + 1), (a, b + 1))


def regions(seen: dict, key: Callable[[tuple[str, int]], Hashable]) -> dict[Hashable, list[list[Point]]]:
    """Group the painted triangles by `key(orientation, depth)` and trace each group's outline as closed loops
    (outer boundaries and holes; fill them with the even-odd rule)."""
    edges = defaultdict(set)
    for triangle, face in seen.items():
        p, q, r = _corners(triangle)
        group = edges[key(face)]
        for edge in ((p, q), (q, r), (r, p)):
            reverse = (edge[1], edge[0])
            if reverse in group:
                group.discard(reverse)       # shared with a neighbour of the same group: interior
            else:
                group.add(edge)
    return {name: _loops(group) for name, group in edges.items()}


def _loops(edges: set[tuple[Point, Point]]) -> list[list[Point]]:
    outgoing = defaultdict(list)
    for start, end in edges:
        outgoing[start].append(end)
    loops = []
    while outgoing:
        start = next(iter(outgoing))
        loop, point = [start], start
        while True:
            nxt = outgoing[point].pop()
            if not outgoing[point]:
                del outgoing[point]
            if nxt == start:
                break
            loop.append(nxt)
            point = nxt
        loops.append(_simplify(loop))
    return loops


def _simplify(loop: list[Point]) -> list[Point]:
    """Drop the points in the middle of straight runs."""
    out = []
    n = len(loop)
    for index, point in enumerate(loop):
        prev, nxt = loop[index - 1], loop[(index + 1) % n]
        if (point[0] - prev[0]) * (nxt[1] - point[1]) != (point[1] - prev[1]) * (nxt[0] - point[0]):
            out.append(point)
    return out


def outline(size: int) -> list[tuple[float, float]]:
    """The silhouette hexagon of the whole cube."""
    s = size
    return [project(*p) for p in ((0, 0, s), (s, 0, s), (s, 0, 0), (s, s, 0), (0, s, 0), (0, s, s))]
