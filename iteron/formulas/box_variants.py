# SPDX-License-Identifier: MIT
"""More of Tglad's box family: the Mandelbox in four dimensions, with a drifting scale, and with the Sierpinski
tetrahedron's folds in place of the box fold."""

from __future__ import annotations

from ..core import ops
from ..core.formula import DIRECT, ESCAPE, LINEAR, formula
from ..core.params import Float, Int
from .boxes import _FOLDS
from .common import box_fold, sierpinski_fold, sphere_fold

_SCALE = Float("scale", 2.0, min=-3.0, max=3.0, description="Scale applied every iteration")


@formula("Mandelbox 4D", family="Boxes", kind=DIRECT, bounds=6.5, surface_offset=1.25,
         description="Tglad's Mandelbox in four dimensions, seen through a 3D slice at a chosen fourth coordinate",
         params=(Int("iterations", 14, min=1, max=40, description="Iterations per point"),
                 _SCALE,
                 Float("fold_limit", 1.0, min=0.1, max=2.0, group="Folds", description="Where the box fold reflects"),
                 ) + _FOLDS + (
                 Float("slice", 0.0, min=-3.0, max=3.0, description="The fourth coordinate of the 3D slice"),
                 Float("c_w", 0.0, min=-3.0, max=3.0, label="C w", description="Added to the fourth coordinate"),
                 Float("bailout", 100.0, min=2.0, max=1000.0, hard_min=1.0,
                       description="Radius beyond which a point has escaped")),
         presets={"Default": {"slice": 0.6}, "Sliced Deep": {"slice": 1.4}, "Negative": {"scale": -1.6, "slice": 0.3},
                  "Shifted": {"c_w": 0.8, "slice": 0.2}})
def mandelbox_4d(pos, p):
    c = ops.vec4(pos.x, pos.y, pos.z, p.slice + p.c_w)
    bail2 = p.bailout * p.bailout

    def body(_i, state):
        q, dr, trap = state
        q = box_fold(q, p.fold_limit)
        factor = p.fixed_radius2 / ops.clamp(ops.dot(q, q), p.min_radius2, p.fixed_radius2)
        q = q * factor * p.scale + c
        dr = dr * factor * ops.abs(p.scale) + 1.0
        return q, dr, ops.min(trap, ops.dot(q, q))

    start = ops.vec4(pos.x, pos.y, pos.z, p.slice)
    (q, dr, trap), _n = ops.loop(p.iterations, 40, (start, 1.0, ops.dot(start, start)), body,
                                 until=lambda s: ops.dot(s[0], s[0]) > bail2)
    return ops.length(q) / ops.abs(dr), ops.sqrt(trap)


@formula("Vary Scale Box", family="Boxes", kind=DIRECT, bounds=4.0, surface_offset=1.25,
         description="Tglad's Mandelbox whose scale drifts every iteration (scale += vary · (|scale| − 1))",
         params=(Int("iterations", 14, min=1, max=40, description="Iterations per point"),
                 _SCALE,
                 Float("vary", 0.1, min=-0.5, max=0.5, description="How much the scale drifts per iteration"),
                 Float("fold_limit", 1.0, min=0.1, max=2.0, group="Folds", description="Where the box fold reflects"),
                 ) + _FOLDS + (
                 Float("bailout", 100.0, min=2.0, max=1000.0, hard_min=1.0,
                       description="Radius beyond which a point has escaped"),),
         presets={"Default": {}, "Gentle": {"vary": 0.04}, "Shrinking": {"vary": -0.03, "scale": 2.2},
                  "Strong": {"vary": 0.25, "scale": 1.8}})
def vary_scale_box(pos, p):
    bail2 = p.bailout * p.bailout

    def body(_i, state):
        z, dr, scale, trap = state
        z = box_fold(z, p.fold_limit)
        z, dr = sphere_fold(z, dr, p.min_radius2, p.fixed_radius2)
        z = z * scale + pos
        dr = dr * ops.abs(scale) + 1.0
        return z, dr, scale + p.vary * (ops.abs(scale) - 1.0), ops.min(trap, ops.dot(z, z))

    (z, dr, _scale, trap), _n = ops.loop(p.iterations, 40, (pos, 1.0, p.scale, ops.dot(pos, pos)), body,
                                         until=lambda s: ops.dot(s[0], s[0]) > bail2)
    return ops.length(z) / ops.abs(dr), ops.sqrt(trap)


@formula("Tetra Box", family="Boxes", kind=ESCAPE, distance=LINEAR, bounds=3.0, surface_offset=1.0,
         description="The Mandelbox with the Sierpinski tetrahedron's folds in place of the box fold",
         params=(_SCALE,
                 Float("fold_limit", 1.0, min=0.1, max=2.0, group="Folds", description="Where the box fold reflects"),
                 ) + _FOLDS,
         overrides={"iterations": {"default": 12}, "bailout": {"default": 100.0, "max": 1000.0}},
         presets={"Default": {}, "Negative": {"scale": -1.8}, "Tight": {"fold_limit": 0.7},
                  "Julia": {"julia": True, "julia_c": (1.0, 0.5, 0.2), "scale": -1.8}})
def tetra_box(z, dr, c, p):
    z = box_fold(sierpinski_fold(z), p.fold_limit)
    z, dr = sphere_fold(z, dr, p.min_radius2, p.fixed_radius2)
    return z * p.scale + c, dr * ops.abs(p.scale) + 1.0
