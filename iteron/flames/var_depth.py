# SPDX-License-Identifier: MIT
"""Variations that act in 3D: Apophysis's depth built-ins (ported from Fractalchemy's `flam3.py`, Stan Ragets, MIT)
and the 3D plugins `julia3D` and `spherical3D`, written for Iteron from their published formulas."""

from __future__ import annotations

import numpy as np

from .var_classic import gaussian
from .variations import EPS, FORMULA, PI, POST, PRE, Point, variation


def _zeros(p: Point):
    return np.zeros_like(p.x)


@variation("pre_blur", kind=PRE)            # jitters the input point (the chaos game applies it first)
def _pre_blur(p: Point):
    a, k = p.rnd() * 2.0 * PI, p.w * gaussian(p)
    return k * np.cos(a), k * np.sin(a)


@variation("flatten", kind=POST, z=FORMULA)
def _flatten(p: Point):
    return _zeros(p), _zeros(p), -p.pz


@variation("zblur", z=FORMULA)
def _zblur(p: Point):
    return _zeros(p), _zeros(p), p.w * gaussian(p)


@variation("blur3D", z=FORMULA)
def _blur3d(p: Point):
    a, b = p.rnd() * 2.0 * PI, p.rnd() * PI
    rr = p.w * gaussian(p)
    return rr * np.sin(b) * np.cos(a), rr * np.sin(b) * np.sin(a), rr * np.cos(b)


@variation("zscale", z=FORMULA)
def _zscale(p: Point):
    return _zeros(p), _zeros(p), p.w * p.z


@variation("ztranslate", z=FORMULA)
def _ztranslate(p: Point):
    return _zeros(p), _zeros(p), np.full_like(p.x, p.w)


@variation("zcone", z=FORMULA)
def _zcone(p: Point):
    return _zeros(p), _zeros(p), p.w * p.r


@variation("pre_zscale", kind=PRE, z=FORMULA)
def _pre_zscale(p: Point):
    return _zeros(p), _zeros(p), p.z * (p.w - 1.0)


@variation("pre_ztranslate", kind=PRE, z=FORMULA)
def _pre_ztranslate(p: Point):
    return _zeros(p), _zeros(p), np.full_like(p.x, p.w)


def _quarter_turn(w: float) -> tuple[float, float]:
    return np.sin(w * PI * 0.5), np.cos(w * PI * 0.5)


@variation("pre_rotate_x", kind=PRE, z=FORMULA)
def _pre_rotate_x(p: Point):
    sa, ca = _quarter_turn(p.w)
    return _zeros(p), sa * p.z + ca * p.y - p.y, ca * p.z - sa * p.y - p.z


@variation("pre_rotate_y", kind=PRE, z=FORMULA)
def _pre_rotate_y(p: Point):
    sa, ca = _quarter_turn(p.w)
    return ca * p.x - sa * p.z - p.x, _zeros(p), sa * p.x + ca * p.z - p.z


@variation("post_rotate_x", kind=POST, z=FORMULA)
def _post_rotate_x(p: Point):
    sa, ca = _quarter_turn(p.w)
    return _zeros(p), sa * p.pz + ca * p.py - p.py, ca * p.pz - sa * p.py - p.pz


@variation("post_rotate_y", kind=POST, z=FORMULA)
def _post_rotate_y(p: Point):
    sa, ca = _quarter_turn(p.w)
    return ca * p.px - sa * p.pz - p.px, _zeros(p), sa * p.px + ca * p.pz - p.pz


@variation("julia3D", {"power": 2.0}, z=FORMULA)
def _julia3d(p: Point):
    """The 3D Julia set: the plane's power-n root with the depth scaled along (Apophysis's julia3D)."""
    power = p.p("julia3D_power") or 1.0
    n = abs(power)
    z = p.z / n
    r2d = p.r2
    r = p.w * np.power(r2d + z * z + EPS, (1.0 / power - 1.0) / 2.0)
    branch = np.floor(p.rnd() * n)
    a = (p.phi + 2.0 * PI * branch) / power
    planar = r * np.sqrt(r2d)
    return planar * np.cos(a), planar * np.sin(a), r * z


@variation("spherical3D", z=FORMULA, aliases=("Spherical3D",))
def _spherical3d(p: Point):
    """Inversion in the unit sphere."""
    k = p.w / (p.r2 + p.z * p.z + EPS)
    return k * p.x, k * p.y, k * p.z


@variation("curl3D", {"cx": 0.0, "cy": 0.0, "cz": 0.0}, z=FORMULA)
def _curl3d(p: Point):
    """The 3D curl: a Möbius-like inversion about (cx, −cy, cz) (Apophysis's curl3D)."""
    cx, cy, cz = p.p("curl3D_cx"), p.p("curl3D_cy"), p.p("curl3D_cz")
    r2 = p.r2 + p.z * p.z
    r = p.w / (r2 * (cx * cx + cy * cy + cz * cz) + 2.0 * cx * p.x - 2.0 * cy * p.y + 2.0 * cz * p.z + 1.0)
    return r * (p.x + cx * r2), r * (p.y - cy * r2), r * (p.z + cz * r2)
