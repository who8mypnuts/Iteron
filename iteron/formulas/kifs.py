# SPDX-License-Identifier: MIT
"""Kaleidoscopic IFS (Knighty's construction): fold into a symmetry domain, then scale towards a vertex."""

from __future__ import annotations

from ..core import ops
from ..core.formula import IFS, formula
from ..core.params import Float, Vec3
from .common import sort_descending

INV_SQRT3 = 0.5773502691896258


def _tetrahedron(z, _p):
    """Distance to the tetrahedron with vertices (1,1,1), (1,-1,-1), (-1,1,-1), (-1,-1,1)."""
    a = ops.max(-z.x - z.y - z.z, z.x + z.y - z.z)
    b = ops.max(-z.x + z.y + z.z, z.x - z.y + z.z)
    return (ops.max(a, b) - 1.0) * INV_SQRT3


def _octahedron(z, _p):
    return (ops.abs(z.x) + ops.abs(z.y) + ops.abs(z.z) - 1.0) * INV_SQRT3


@formula("Sierpinski Tetrahedron", family="Kaleidoscopic IFS", kind=IFS, bounds=1.1, shape=_tetrahedron,
         description="Four half-size copies of a tetrahedron, again and again",
         params=(Float("scale", 2.0, min=1.5, max=3.0, hard_min=1.01, description="Scale of each iteration (2 is Sierpinski)"),
                 Vec3("offset", (1.0, 1.0, 1.0), min=0.0, max=2.0, description="The vertex the copies are scaled towards")),
         overrides={"iterations": {"default": 7, "max": 16}},
         presets={"Default": {}, "Sparse": {"scale": 2.3}, "Skewed": {"offset": (1.0, 0.8, 1.2)}})
def sierpinski(z, dr, c, p):
    z = ops.select(z.x + z.y < 0.0, ops.vec3(-z.y, -z.x, z.z), z)
    z = ops.select(z.x + z.z < 0.0, ops.vec3(-z.z, z.y, -z.x), z)
    z = ops.select(z.y + z.z < 0.0, ops.vec3(z.x, -z.z, -z.y), z)
    return z * p.scale - p.offset * (p.scale - 1.0), dr * p.scale


@formula("Octahedral KIFS", family="Kaleidoscopic IFS", kind=IFS, bounds=1.2, shape=_octahedron,
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
