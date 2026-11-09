# SPDX-License-Identifier: MIT
"""Boxes: Tglad's box fold and sphere fold, scaled and offset every iteration."""

from __future__ import annotations

from ..core import ops
from ..core.formula import ESCAPE, LINEAR, formula
from ..core.params import Float, Vec3
from .common import box_fold, sphere_fold

_FOLDS = (
    Float("min_radius2", 0.25, min=0.0, max=2.0, hard_min=0.0001, label="Min Radius²", group="Folds",
          description="Inside this squared radius the sphere fold scales uniformly"),
    Float("fixed_radius2", 1.0, min=0.1, max=4.0, hard_min=0.0001, label="Fixed Radius²", group="Folds",
          description="Squared radius of the sphere fold's inversion"),
)


@formula("Mandelbox", family="Boxes", kind=ESCAPE, distance=LINEAR, bounds=6.5,
         description="Tom Lowe's Mandelbox: box fold, sphere fold, scale",
         params=(Float("scale", 2.0, min=-3.0, max=3.0, description="Scale applied every iteration"),
                 Float("fold_limit", 1.0, min=0.1, max=2.0, group="Folds", description="Where the box fold reflects"),
                 ) + _FOLDS,
         overrides={"iterations": {"default": 14}, "bailout": {"default": 100.0, "max": 1000.0}},
         presets={"Classic": {}, "Open": {"scale": 2.5}, "Sculpted": {"scale": -2.0},
                  "Amazing Box": {"scale": -1.5}})
def mandelbox(z, dr, c, p):
    z = box_fold(z, p.fold_limit)
    z, dr = sphere_fold(z, dr, p.min_radius2, p.fixed_radius2)
    return z * p.scale + c, dr * ops.abs(p.scale) + 1.0


@formula("Amazing Surf", family="Boxes", kind=ESCAPE, distance=LINEAR, bounds=3.0,
         description="Mandelbulb3D's Amazing Surf: the box fold on x and y only, a sphere fold, scale and rotation",
         params=(Float("scale", 2.0, min=-4.0, max=4.0, description="Scale applied every iteration"),
                 Float("fold_x", 1.0, min=0.0, max=3.0, group="Folds", description="Box fold limit along x"),
                 Float("fold_y", 1.0, min=0.0, max=3.0, group="Folds", description="Box fold limit along y"),
                 ) + _FOLDS + (
                 Vec3("rotation", (20.0, 20.0, 0.0), min=-180.0, max=180.0, group="Rotation",
                      description="Rotation applied every iteration, in degrees"),),
         prepare=lambda p: {"rot": ops.rotation_xyz(p.rotation)},
         overrides={"iterations": {"default": 12}, "bailout": {"default": 100.0, "max": 1000.0}},
         presets={"Default": {}, "Flat": {"rotation": (0.0, 0.0, 0.0)},
                  "Waves": {"rotation": (30.0, 0.0, 0.0), "julia": True, "julia_c": (0.5, 0.3, 0.2)}})
def amazing_surf(z, dr, c, p):
    z = ops.vec3(box_fold(z.x, p.fold_x), box_fold(z.y, p.fold_y), z.z)
    z, dr = sphere_fold(z, dr, p.min_radius2, p.fixed_radius2)
    return ops.mat_mul(p.rot, z) * p.scale + c, dr * ops.abs(p.scale) + 1.0
