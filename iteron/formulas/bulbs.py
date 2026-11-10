# SPDX-License-Identifier: MIT
"""Bulbs: escape-time fractals in triplex (spherical) arithmetic."""

from __future__ import annotations

from ..core import ops
from ..core.formula import ESCAPE, LOG, formula
from ..core.params import Float, Vec3
from .common import TINY, triplex_multiply, triplex_power


@formula("Mandelbulb", family="Bulbs", kind=ESCAPE, distance=LOG, bounds=1.4,
         description="The White–Nylander power bulb; turn on Julia for a Juliabulb",
         params=(Float("power", 8.0, min=2.0, max=16.0, hard_min=1.0, description="Exponent of the triplex power"),),
         presets={"Classic": {},
                  "Power 4": {"power": 4.0},
                  "Power 3": {"power": 3.0, "iterations": 16},
                  "Juliabulb": {"julia": True, "julia_c": (0.35, 0.45, -0.3), "iterations": 10}})
def mandelbulb(z, dr, c, p):
    r = ops.max(ops.length(z), TINY)
    dr = ops.pow(r, p.power - 1.0) * p.power * dr + 1.0
    return triplex_power(z, p.power) + c, dr


@formula("Folding Int Pow", family="Bulbs", kind=ESCAPE, distance=LOG, bounds=4.3,
         description="Mandelbulb3D's FoldingIntPow: a box fold, a triplex power and a z multiplier",
         params=(Float("power", 3.0, min=2.0, max=8.0, hard_min=1.0, description="Exponent of the triplex power"),
                 Float("fold", 1.0, min=0.0, max=3.0, description="Where the box fold reflects"),
                 Float("z_mul", 1.0, min=-3.0, max=3.0, label="Z Multiplier", description="Scales z after the power")),
         overrides={"iterations": {"default": 10}, "bailout": {"default": 8.0},
                    "julia_c": {"default": (0.2, 0.4, 0.1)}},
         presets={"Default": {}, "Power 2": {"power": 2.0}, "Flattened": {"z_mul": 0.6},
                  "Julia": {"julia": True}})
def folding_int_pow(z, dr, c, p):
    z = ops.abs(z + p.fold) - ops.abs(z - p.fold) - z
    r = ops.max(ops.length(z), TINY)
    dr = ops.pow(r, p.power - 1.0) * p.power * dr + 1.0
    z = triplex_power(z, p.power)
    return ops.vec3(z.x, z.y, z.z * p.z_mul) + c, dr


@formula("Lambdabulb", family="Bulbs", kind=ESCAPE, distance=LOG, bounds=1.6,
         description="z = λ z (1 − z^(n−1)) in triplex arithmetic: the lambda Mandelbrot lifted to 3D",
         params=(Float("power", 3.0, min=2.0, max=8.0, hard_min=1.5, description="Exponent n"),
                 Vec3("lambda_", (1.3, 0.2, 0.1), min=-3.0, max=3.0, label="Lambda", description="The constant λ")),
         overrides={"bailout": {"default": 16.0}, "julia": {"default": False}},
         presets={"Default": {}, "Power 2": {"power": 2.0, "lambda_": (1.0, 0.5, 0.0)},
                  "Spiral": {"lambda_": (1.1, 0.6, 0.3)}})
def lambdabulb(z, dr, c, p):
    # the derivative of λ z (1 − zⁿ⁻¹) is λ (1 − n zⁿ⁻¹): its length scales the running derivative
    # (c, the shared Julia constant, is added when Julia is on, so λ-maps can be perturbed too)
    zn1 = triplex_power(z, p.power - 1.0)
    one = ops.vec3(1.0, 0.0, 0.0)
    dr = ops.length(p.lambda_) * ops.max(ops.length(one - p.power * zn1), TINY) * dr
    z = triplex_multiply(p.lambda_, triplex_multiply(z, one - zn1))
    return ops.select(p.julia, z + p.julia_c, z), dr
