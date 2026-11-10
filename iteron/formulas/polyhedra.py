# SPDX-License-Identifier: MIT
"""Kaleidoscopic IFS with icosahedral symmetry (Knighty's construction), and the Sierpinski square pyramid.

The icosahedral fold reflects a point across the group's 15 mirror planes until it lies in one fundamental
chamber — the triangle cone between a 5-fold axis (an icosahedron vertex), a 3-fold axis (a face centre, i.e. a
dodecahedron vertex) and a 2-fold axis. Three sweeps always suffice (a test checks that folding any image of a point
under the group gives the same point). Scaling towards the 5-fold corner makes the icosahedron flake; towards the
3-fold corner, the dodecahedron flake.
"""

from __future__ import annotations

from ..core import ops
from ..core.formula import IFS, formula
from ..core.params import Float, Vec3

PHI = 1.618033988749895
# the 12 mirrors other than the coordinate planes, oriented towards the chamber: ½(φ, 1, 1/φ) and its even
# permutations and sign changes (the coordinate mirrors are `abs`)
_H, _HALF, _HINV = PHI / 2.0, 0.5, 0.5 / PHI
MIRRORS = ((_H, _HALF, _HINV), (_HINV, _H, _HALF), (_HALF, _HINV, _H), (-_H, -_HALF, _HINV), (-_HINV, _H, _HALF),
           (_HALF, -_HINV, _H), (_H, -_HALF, _HINV), (-_HINV, -_H, _HALF), (-_HALF, _HINV, _H), (-_H, _HALF, _HINV),
           (_HINV, -_H, _HALF), (-_HALF, -_HINV, _H))
SWEEPS = 3
FIVE_FOLD = (0.0, 0.5257311121191336, 0.85065080835204)      # icosahedron vertex in the chamber
THREE_FOLD = (0.35682208977308993, 0.0, 0.9341723589627157)   # face centre (dodecahedron vertex) in the chamber
INRADIUS = 0.7946544722917661                                 # inradius / circumradius of both solids


def icosahedral_fold(z):
    for _ in range(SWEEPS):
        z = ops.abs(z)
        for normal in MIRRORS:
            n = ops.vec3(*normal)
            t = ops.dot(z, n)
            z = ops.select(t < 0.0, z - n * (2.0 * t), z)
    return z


def _icosahedron(z, _p):
    return ops.dot(z, ops.vec3(*THREE_FOLD)) - INRADIUS


def _dodecahedron(z, _p):
    return ops.dot(z, ops.vec3(*FIVE_FOLD)) - INRADIUS


_ROTATION = Vec3("rotation", (0.0, 0.0, 0.0), min=-180.0, max=180.0, group="Rotation",
                 description="Rotation applied every iteration, in degrees")


@formula("Icosahedral KIFS", family="Kaleidoscopic IFS", kind=IFS, bounds=1.2, shape=_icosahedron,
         surface_offset=0.5,
         description="Twelve smaller icosahedra at an icosahedron's vertices, again and again (the icosahedron flake)",
         params=(Float("scale", 2.618034, min=1.6, max=3.5, hard_min=1.01,
                       description="Scale of each iteration (φ² touches)"),
                 Float("stretch", 1.0, min=0.5, max=1.5, description="How far out the copies sit"),
                 _ROTATION),
         prepare=lambda p: {"rot": ops.rotation_xyz(p.rotation)},
         overrides={"iterations": {"default": 6, "max": 16}},
         presets={"Flake": {}, "Loose": {"scale": 3.0}, "Twisted": {"rotation": (0.0, 0.0, 12.0)},
                  "Dense": {"scale": 2.2}})
def icosahedral_kifs(z, dr, c, p):
    z = ops.mat_mul(p.rot, icosahedral_fold(z))
    return z * p.scale - ops.vec3(*FIVE_FOLD) * (p.stretch * (p.scale - 1.0)), dr * p.scale


@formula("Dodecahedral KIFS", family="Kaleidoscopic IFS", kind=IFS, bounds=1.2, shape=_dodecahedron,
         surface_offset=0.5,
         description="Twenty smaller dodecahedra at a dodecahedron's vertices, again and again (the dodecahedron "
                     "flake)",
         params=(Float("scale", 3.618034, min=2.0, max=4.5, hard_min=1.01,
                       description="Scale of each iteration (φ + 2 touches)"),
                 Float("stretch", 1.0, min=0.5, max=1.5, description="How far out the copies sit"),
                 _ROTATION),
         prepare=lambda p: {"rot": ops.rotation_xyz(p.rotation)},
         overrides={"iterations": {"default": 5, "max": 12}},
         presets={"Flake": {}, "Overlapping": {"scale": 2.8}, "Twisted": {"rotation": (10.0, 0.0, 0.0)},
                  "Loose": {"scale": 4.0}})
def dodecahedral_kifs(z, dr, c, p):
    z = ops.mat_mul(p.rot, icosahedral_fold(z))
    return z * p.scale - ops.vec3(*THREE_FOLD) * (p.stretch * (p.scale - 1.0)), dr * p.scale


_SIDE = 0.4472135954999579       # 1/√5: the pyramid's side planes are 2|x| + z = 1


def _pyramid(z, _p):
    """A bound on the distance to the square pyramid with apex (0, 0, 1) and base z = −1, |x|, |y| ≤ 1."""
    return ops.max(-z.z - 1.0, ops.max(2.0 * ops.abs(z.x) + z.z - 1.0, 2.0 * ops.abs(z.y) + z.z - 1.0) * _SIDE)


@formula("Sierpinski Square Pyramid", family="Kaleidoscopic IFS", kind=IFS, bounds=1.1, shape=_pyramid, surface_offset=0.5,
         description="A square pyramid made of five half-size pyramids — the four base corners and the apex",
         params=(Float("scale", 2.0, min=1.5, max=3.0, hard_min=1.01, description="Scale of each iteration (2 is "
                       "Sierpinski)"),),
         overrides={"iterations": {"default": 7, "max": 16}},
         presets={"Default": {}, "Sparse": {"scale": 2.3}, "Level 3": {"iterations": 3}})
def sierpinski_square_pyramid(z, dr, c, p):
    z = ops.vec3(ops.abs(z.x), ops.abs(z.y), z.z)                  # into one base quadrant
    apex, corner = ops.vec3(0.0, 0.0, 1.0), ops.vec3(1.0, 1.0, -1.0)
    to_apex, to_corner = z - apex, z - corner
    vertex = ops.select(ops.dot(to_apex, to_apex) < ops.dot(to_corner, to_corner), apex, corner)
    return z * p.scale - vertex * (p.scale - 1.0), dr * p.scale
