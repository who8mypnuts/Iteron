# SPDX-License-Identifier: MIT
"""Bulbs: escape-time fractals in triplex (spherical) arithmetic."""

from __future__ import annotations

from ..core import ops
from ..core.formula import ESCAPE, LOG, formula
from ..core.params import Float
from .common import TINY, triplex_power


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
