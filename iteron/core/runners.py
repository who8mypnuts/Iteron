# SPDX-License-Identifier: MIT
"""The kernel: a formula turned into the four channels Iteron samples at every point.

    (distance, trap, iterations, radius)

`distance` is the distance estimate (negative or ~0 inside); the other three are the colour sources the Color
section switches between (radius is stored as log(1 + r): escaped radii are huge and chaotic). Written against `ops`, so the same code runs in numpy and is traced into GLSL.
"""

from __future__ import annotations

from . import ops
from .formula import DIRECT, ESCAPE, LOG, Formula, Values

TINY = 1e-10


def kernel(entry: Formula, pos, p: Values):
    """`(distance, trap, iterations, radius)` of `entry` at `pos`."""
    if entry.kind == DIRECT:
        distance, trap = entry.fn(pos, p)
        distance, trap, iterations, radius = distance, trap, trap, ops.log(1.0 + ops.length(pos))
    else:
        distance, trap, iterations, radius = _iterated(entry, pos, p)
    return _cut(distance, pos, p), trap, iterations, radius


def _cut(distance, pos, p: Values):
    """Intersect with the half-space behind the cutting plane (when the cut is on)."""
    along = ops.select(p.cut_axis < 0.5, pos.x, ops.select(p.cut_axis < 1.5, pos.y, pos.z))
    side = (along - p.cut_offset) * ops.select(p.cut_flip, -1.0, 1.0)
    return ops.select(p.cut, ops.max(distance, side), distance)


def _iterated(entry: Formula, pos, p: Values):
    c = ops.select(p.julia, p.julia_c, pos) if entry.kind == ESCAPE else pos
    bail2 = p.bailout * p.bailout

    def body(_i, state):
        z, dr, trap = state
        z, dr = entry.fn(z, dr, c, p)
        return z, dr, ops.min(trap, ops.dot(z, z))

    (z, dr, trap), n = ops.loop(p.iterations, entry.param("iterations").max, (pos, 1.0, ops.dot(pos, pos)), body,
                                until=lambda s: ops.dot(s[0], s[0]) > bail2)
    r = ops.max(ops.length(z), TINY)
    if entry.shape is not None:
        distance = entry.shape(z, p) / ops.abs(dr)
    elif entry.distance == LOG:
        distance = 0.5 * ops.log(r) * r / dr
    else:
        distance = r / ops.abs(dr)
    return distance, ops.sqrt(trap), n / p.iterations, ops.log(1.0 + r)
