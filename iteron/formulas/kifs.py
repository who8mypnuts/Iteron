# SPDX-License-Identifier: MIT
"""Kaleidoscopic IFS (Knighty's construction): fold into a symmetry domain, then scale towards a vertex."""

from __future__ import annotations

from ..core import ops
from ..core.formula import DIRECT, IFS, formula
from ..core.params import Float, Int, Vec3
from .common import INV_SQRT3, sd_tetrahedron, sierpinski_fold, sort_descending


def _tetrahedron(z, _p):
    return sd_tetrahedron(z)


def _octahedron(z, _p):
    return (ops.abs(z.x) + ops.abs(z.y) + ops.abs(z.z) - 1.0) * INV_SQRT3


@formula("Sierpinski Tetrahedron", family="Kaleidoscopic IFS", kind=IFS, bounds=1.1, shape=_tetrahedron,
         surface_offset=0.5,
         description="Four half-size copies of a tetrahedron, again and again",
         params=(Float("scale", 2.0, min=1.5, max=3.0, hard_min=1.01, description="Scale of each iteration (2 is Sierpinski)"),
                 Vec3("offset", (1.0, 1.0, 1.0), min=0.0, max=2.0, description="The vertex the copies are scaled towards")),
         overrides={"iterations": {"default": 7, "max": 16}},
         presets={"Default": {}, "Sparse": {"scale": 2.3}, "Skewed": {"offset": (1.0, 0.8, 1.2)}})
def sierpinski(z, dr, c, p):
    return sierpinski_fold(z) * p.scale - p.offset * (p.scale - 1.0), dr * p.scale


@formula("Octahedral KIFS", family="Kaleidoscopic IFS", kind=IFS, bounds=1.2, shape=_octahedron,
         surface_offset=0.5,
         description="Octahedral symmetry folds with a rotation every iteration",
         params=(Float("scale", 2.0, min=1.2, max=3.0, hard_min=1.01, description="Scale of each iteration"),
                 Vec3("offset", (1.0, 0.0, 0.0), min=0.0, max=2.0, description="The point the copies are scaled towards"),
                 Vec3("rotation", (0.0, 0.0, 0.0), min=-180.0, max=180.0, group="Rotation",
                      description="Rotation applied every iteration, in degrees")),
         prepare=lambda p: {"rot": ops.rotation_xyz(p.rotation)},
         overrides={"iterations": {"default": 8, "max": 20}},
         presets={"Default": {}, "Truncated": {"offset": (1.0, 1.0, 0.0)}, "Star": {"offset": (1.0, 0.3, 0.3)},
                  "Twisted": {"rotation": (5.0, 5.0, 5.0), "scale": 2.1}})
def octahedral(z, dr, c, p):
    z = ops.mat_mul(p.rot, sort_descending(ops.abs(z)))
    return z * p.scale - p.offset * (p.scale - 1.0), dr * p.scale


@formula("Koch Tetrahedron", family="Kaleidoscopic IFS", kind=DIRECT, bounds=1.3, surface_offset=0.5,
         description="The 3D Koch snowflake: every face grows a half-size tetrahedron, again and again",
         params=(Int("iterations", 4, min=0, max=8, description="Levels of growth"),
                 Float("scale", 2.0, min=1.5, max=3.0, hard_min=1.01, description="Scale of each level (2 is Koch)"),
                 Float("offset", 1.0, min=0.0, max=2.0, description="Where the copies are scaled towards"),
                 Float("rounding", 0.0, min=0.0, max=0.1, hard_min=0.0, description="Rounds the tetrahedra")),
         presets={"Default": {}, "Level 2": {"iterations": 2}, "Stretched": {"scale": 2.3}})
def koch_tetrahedron(pos, p):
    grow = p.offset * (p.scale - 1.0)

    def body(_i, state):
        z, s, d = state
        corner = sierpinski_fold(z) * p.scale - grow
        face = sierpinski_fold(-z) * p.scale - grow
        dc, df = sd_tetrahedron(corner), sd_tetrahedron(face)
        s = s * p.scale
        return ops.select(dc < df, corner, face), s, ops.min(d, ops.min(dc, df) / s)

    (z, _s, d), n = ops.loop(p.iterations, 8, (pos, 1.0, sd_tetrahedron(pos)), body)
    return d - p.rounding, ops.length(z) / (1.0 + ops.length(z))
