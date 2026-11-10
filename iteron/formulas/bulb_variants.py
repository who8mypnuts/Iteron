# SPDX-License-Identifier: MIT
"""More escape-time bulbs: the Mandelbulb's published variations (a different angle, a conjugate, absolute values,
a polynomial) and Doug Bristor's quadratic 3D map. Each carries the Mandelbulb's running derivative."""

from __future__ import annotations

from ..core import ops
from ..core.formula import ESCAPE, LOG, formula
from ..core.params import Float
from .common import TINY, triplex_power

def _power(default: float) -> Float:
    return Float("power", default, min=2.0, max=16.0, hard_min=1.0, description="Exponent of the triplex power")


def _dr(z, dr, n):
    r = ops.max(ops.length(z), TINY)
    return ops.pow(r, n - 1.0) * n * dr + 1.0


@formula("Cosine Mandelbulb", family="Bulbs", kind=ESCAPE, distance=LOG, bounds=1.4,
         description="Daniel White's other bulb: the polar angle measured from the equator (cosine form)",
         params=(_power(5.0),),
         presets={"Default": {}, "Power 8": {"power": 8.0}, "Power 3": {"power": 3.0, "iterations": 14},
                  "Julia": {"julia": True, "julia_c": (0.4, -0.3, 0.5)}})
def cosine_mandelbulb(z, dr, c, p):
    r = ops.max(ops.length(z), TINY)
    theta = ops.asin(ops.clamp(z.z / r, -1.0, 1.0)) * p.power
    phi = ops.atan2(z.y, z.x) * p.power
    cos_theta = ops.cos(theta)
    return (ops.pow(r, p.power) * ops.vec3(cos_theta * ops.cos(phi), cos_theta * ops.sin(phi), ops.sin(theta)) + c,
            _dr(z, dr, p.power))


@formula("Mandelbar Bulb", family="Bulbs", kind=ESCAPE, distance=LOG, bounds=1.4,
         description="The tricorn lifted to 3D: the triplex power of the conjugate (the azimuth turns backwards)",
         params=(_power(3.0),),
         presets={"Default": {}, "Power 2": {"power": 2.0, "iterations": 16}, "Power 5": {"power": 5.0},
                  "Julia": {"julia": True, "julia_c": (-0.3, 0.2, 0.4)}})
def mandelbar_bulb(z, dr, c, p):
    return triplex_power(ops.vec3(z.x, -z.y, z.z), p.power) + c, _dr(z, dr, p.power)


@formula("Burning Ship Bulb", family="Bulbs", kind=ESCAPE, distance=LOG, bounds=1.6,
         description="The burning ship lifted to 3D: the triplex power of the absolute values",
         params=(_power(3.0),),
         overrides={"iterations": {"default": 10}},
         presets={"Default": {}, "Power 2": {"power": 2.0, "iterations": 14}, "Power 5": {"power": 5.0},
                  "Julia": {"julia": True, "julia_c": (-0.5, -0.3, 0.2)}})
def burning_ship_bulb(z, dr, c, p):
    return triplex_power(ops.abs(z), p.power) + c, _dr(z, dr, p.power)


@formula("Bristorbrot", family="Bulbs", kind=ESCAPE, distance=LOG, bounds=1.8,
         description="Doug Bristor's quadratic map: x² − y² − z², y(2x − z), z(2x + y)",
         overrides={"iterations": {"default": 14}},
         presets={"Default": {}, "Julia": {"julia": True, "julia_c": (-0.6, 0.4, 0.3)},
                  "Deep": {"iterations": 22}})
def bristorbrot(z, dr, c, p):
    r = ops.max(ops.length(z), TINY)
    z = ops.vec3(z.x * z.x - z.y * z.y - z.z * z.z, z.y * (2.0 * z.x - z.z), z.z * (2.0 * z.x + z.y))
    return z + c, 2.0 * r * dr + 1.0


@formula("Polynomial Bulb", family="Bulbs", kind=ESCAPE, distance=LOG, bounds=1.5,
         description="Two triplex powers added: zⁿ + k·zᵐ + c",
         params=(Float("power", 6.0, min=2.0, max=12.0, hard_min=1.0, description="The first exponent n"),
                 Float("power2", 2.0, min=1.0, max=8.0, hard_min=1.0, label="Second Power",
                       description="The second exponent m"),
                 Float("mix", 0.5, min=-2.0, max=2.0, description="The second power's weight k")),
         presets={"Default": {}, "Eight and Three": {"power": 8.0, "power2": 3.0, "mix": 0.4},
                  "Negative": {"mix": -0.6}, "Julia": {"julia": True, "julia_c": (0.3, 0.3, -0.4)}})
def polynomial_bulb(z, dr, c, p):
    r = ops.max(ops.length(z), TINY)
    dr = (p.power * ops.pow(r, p.power - 1.0) + ops.abs(p.mix) * p.power2 * ops.pow(r, p.power2 - 1.0)) * dr + 1.0
    return triplex_power(z, p.power) + p.mix * triplex_power(z, p.power2) + c, dr
