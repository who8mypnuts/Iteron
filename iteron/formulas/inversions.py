# SPDX-License-Identifier: MIT
"""Limit sets of inversions: space is folded into a cell and inverted in a sphere, again and again, and the points
whose orbits stay bounded form the set. These sets tile space without end, so each is cut out as a solid chunk —
intersected with a box of a chosen size — which makes it an object you can place (the live preview shows the same
chunk)."""

from __future__ import annotations

from ..core import ops
from ..core.formula import DIRECT, formula
from ..core.params import Float, Int, Vec3


def _chunk(d, pos, p):
    """The set intersected with the box `±extent` (both estimates: the larger bounds the intersection)."""
    return ops.max(d, ops.sd_box(pos, ops.vec3(p.extent)))


_EXTENT = Float("extent", 1.0, min=0.2, max=3.0, description="Half the size of the chunk that is cut out")


@formula("Apollonian Packing", family="Inversions", kind=DIRECT, bounds=1.1, surface_offset=0.5,
         description="Spheres packed into the gaps between spheres without end: fold into a cell, invert, repeat",
         params=(Int("iterations", 8, min=1, max=16, description="Folds and inversions per point"),
                 Float("packing", 1.2, min=0.8, max=1.7, description="The inversion's strength (its radius²)"),
                 Float("cell", 1.0, min=0.5, max=2.0, description="The size of the folding cell"),
                 _EXTENT),
         presets={"Default": {}, "Loose": {"packing": 1.0}, "Tight": {"packing": 1.45},
                  "Large Chunk": {"extent": 2.0}})
def apollonian_packing(pos, p):
    def body(_i, state):
        q, scale, trap = state
        q = (ops.fract(q * (0.5 / p.cell) + 0.5) * 2.0 - 1.0) * p.cell      # into the cell [−cell, cell]³
        r2 = ops.max(ops.dot(q, q), 1e-12)
        k = p.packing / r2
        return q * k, scale * k, ops.min(trap, r2)

    (q, scale, trap), _n = ops.loop(p.iterations, 16, (pos, 1.0, 1e4), body)
    return _chunk(0.25 * ops.abs(q.y) / scale, pos, p), ops.sqrt(trap)


@formula("Pseudo Kleinian", family="Inversions", kind=DIRECT, bounds=1.1, surface_offset=0.5,
         description="Theli-at's and Knighty's pseudo-Kleinian: a box fold and a sphere inversion, repeated; what "
                     "stays near the z axis is drawn",
         params=(Int("iterations", 7, min=1, max=20, description="Folds and inversions per point"),
                 Vec3("box", (0.92, 0.92, 1.2), min=0.2, max=2.0, label="Fold Box",
                      description="The box the orbit is folded into"),
                 Float("size", 1.0, min=0.3, max=2.0, description="The inversion sphere's radius²"),
                 Vec3("offset", (0.0, 0.0, 0.0), min=-1.0, max=1.0, description="Added after every inversion"),
                 Float("thickness", 0.01, min=0.0, max=0.3, description="How thick the drawn threads are"),
                 _EXTENT),
         presets={"Default": {}, "Open": {"box": (0.7, 0.7, 1.2)}, "Shifted": {"offset": (0.1, 0.05, 0.0)},
                  "Chunky": {"thickness": 0.08, "size": 1.2}})
def pseudo_kleinian(pos, p):
    def body(_i, state):
        q, factor, trap = state
        q = ops.clamp(q, -p.box, p.box) * 2.0 - q
        r2 = ops.max(ops.dot(q, q), 1e-12)
        k = ops.max(p.size / r2, 1.0)
        return q * k + p.offset, factor * k, ops.min(trap, r2)

    (q, factor, trap), _n = ops.loop(p.iterations, 20, (pos, 1.0, 1e4), body)
    rxy = ops.length(ops.vec3(q.x, q.y, 0.0))
    d = ops.max(rxy - p.thickness, ops.abs(rxy * q.z) / ops.max(ops.length(q), 1e-12)) / factor
    return _chunk(d, pos, p), ops.sqrt(trap)


@formula("Sphere Inversion IFS", family="Inversions", kind=DIRECT, bounds=1.1, surface_offset=0.5,
         description="Fold into an octant, invert in a sphere (clamped, like a sphere fold), offset, repeat: a "
                     "Kleinian-flavoured web of tubes",
         params=(Int("iterations", 8, min=1, max=24, description="Folds and inversions per point"),
                 Vec3("fold", (1.0, 1.0, 1.0), min=-3.0, max=3.0, description="Subtracted after the octant fold"),
                 Float("radius2", 2.0, min=0.1, max=8.0, label="Radius²", description="The inversion sphere's radius²"),
                 Float("min_r2", 0.2, min=0.01, max=2.0, label="Min R²", description="Inside this, the inversion stops "
                       "growing"),
                 Float("max_r2", 1.5, min=0.5, max=8.0, label="Max R²", description="Beyond this, no inversion"),
                 Vec3("offset", (0.6, 0.6, 2.5), min=-4.0, max=8.0, description="Subtracted after the inversion"),
                 Float("thickness", 0.01, min=0.0, max=0.3, description="How thick the tubes are"),
                 _EXTENT),
         presets={"Default": {}, "Threads": {"thickness": 0.0, "iterations": 10},
                  "Lattice": {"offset": (1.0, 1.0, 1.0)}, "Swollen": {"thickness": 0.06}})
def sphere_inversion_ifs(pos, p):
    def body(_i, state):
        q, s, trap = state
        q = ops.abs(q) - p.fold
        r2 = ops.dot(q, q)
        f = p.radius2 / ops.clamp(r2, p.min_r2, p.max_r2)
        return q * f - p.offset, s * f, ops.min(trap, r2)

    (q, s, trap), _n = ops.loop(p.iterations, 24, (pos, 1.0, 1e4), body)
    d = (ops.length(ops.vec3(q.x, 0.0, q.z)) - p.thickness * s) / s
    return _chunk(d, pos, p), ops.sqrt(trap)
