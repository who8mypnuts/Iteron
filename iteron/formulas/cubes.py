# SPDX-License-Identifier: MIT
"""Cube fractals beyond the sponges: Cantor dust, the Vicsek fractal, a Koch surface of cubes, a Menger sponge
twisted every level, and a foam of nested gyroids."""

from __future__ import annotations

from ..core import ops
from ..core.formula import DIRECT, IFS, formula
from ..core.params import Enum, Float, Int, Vec3
from .common import sort_descending

def _cube():
    return ops.vec3(1.0)          # made per call: a module-level constant would be numpy, not traceable


def _box_shape(z, _p):
    return ops.sd_box(z, _cube())


@formula("Cantor Dust", family="Sponges & Cubes", kind=IFS, bounds=1.1, shape=_box_shape, surface_offset=0.5,
         description="Georg Cantor's dust in 3D: only the eight corner cubes survive every level",
         params=(Float("scale", 3.0, min=2.05, max=4.0, hard_min=2.01, description="Scale of each level (3 is Cantor)"),
                 Vec3("offset", (1.0, 1.0, 1.0), min=0.0, max=1.5, description="The corner the copies move towards")),
         overrides={"iterations": {"default": 4, "max": 10}},
         presets={"Level 4": {}, "Level 2": {"iterations": 2}, "Fat": {"scale": 2.4},
                  "Stretched": {"offset": (1.0, 0.6, 1.0)}})
def cantor_dust(z, dr, c, p):
    return ops.abs(z) * p.scale - p.offset * (p.scale - 1.0), dr * p.scale


_PATTERNS = (("CROSS", "Cross", "The centre and its six face neighbours"),
             ("CORNERS", "Corners", "The centre and the eight corners"))


@formula("Vicsek Cube", family="Sponges & Cubes", kind=IFS, bounds=1.1, shape=_box_shape, surface_offset=0.5,
         description="Tamás Vicsek's fractal in 3D: a cube keeps its centre and a cross (or its corners) of cubes",
         params=(Enum("pattern", "CROSS", items=_PATTERNS, static=True, description="Which cubes survive every level"),),
         overrides={"iterations": {"default": 4, "max": 8}},
         presets={"Cross": {}, "Corners": {"pattern": "CORNERS"}, "Cross Level 2": {"iterations": 2}})
def vicsek_cube(z, dr, c, p):
    z = sort_descending(ops.abs(z))                        # x ≥ y ≥ z ≥ 0
    third = 1.0 / 3.0
    if p.pattern == 0:
        moved = ops.vec3(z.x - 2.0 * third, z.y, z.z)       # the face cube on +x
        outer = z.x > third
    else:
        moved = z - 2.0 * third                             # the corner cube
        outer = z.z > third
    return ops.select(outer, moved, z) * 3.0, dr * 3.0


@formula("Koch Cube", family="Sponges & Cubes", kind=DIRECT, bounds=1.8, surface_offset=0.5,
         description="A Koch surface of cubes: every face of every cube grows a smaller cube, again and again",
         params=(Int("iterations", 4, min=0, max=7, description="Levels of growth"),
                 Float("scale", 2.4, min=2.05, max=4.0, hard_min=2.01, description="Parent to child size ratio"),
                 Float("lift", 1.0, min=0.5, max=1.5, description="How far out each child sits (1: touching)")),
         presets={"Default": {}, "Level 2": {"iterations": 2}, "Small Children": {"scale": 3.0},
                  "Floating": {"lift": 1.2}})
def koch_cube(pos, p):
    reach = 1.0 + p.lift / p.scale                         # the child's centre, in the parent's units

    def body(_i, state):
        z, s, d = state
        z = sort_descending(ops.abs(z))                    # the face nearest the point is +x
        z = ops.vec3(z.x - reach, z.y, z.z) * p.scale
        s = s * p.scale
        return z, s, ops.min(d, ops.sd_box(z, _cube()) / s)

    (z, _s, d), _n = ops.loop(p.iterations, 7, (pos, 1.0, ops.sd_box(pos, _cube())), body)
    return d, ops.length(z) / (1.0 + ops.length(z))


@formula("Twisted Menger", family="Sponges & Cubes", kind=IFS, bounds=1.3, surface_offset=0.5,
         shape=_box_shape,
         description="Knighty's Menger fold with a rotation every level: the sponge turns into a twisted lattice",
         params=(Float("scale", 3.0, min=1.5, max=4.0, hard_min=1.01, description="Scale of each level"),
                 Vec3("offset", (1.0, 1.0, 1.0), min=0.0, max=2.0, description="The corner the copies move towards"),
                 Vec3("rotation", (0.0, 0.0, 12.0), min=-180.0, max=180.0, group="Rotation",
                      description="Rotation applied every level, in degrees")),
         prepare=lambda p: {"rot": ops.rotation_xyz(p.rotation)},
         overrides={"iterations": {"default": 5, "max": 12}},
         presets={"Default": {}, "Spun": {"rotation": (20.0, 0.0, 0.0)}, "Skewed": {"rotation": (8.0, 8.0, 8.0)},
                  "Open": {"scale": 2.6, "rotation": (0.0, 0.0, 30.0)}})
def twisted_menger(z, dr, c, p):
    z = sort_descending(ops.abs(ops.mat_mul(p.rot, z)))
    grow = p.scale - 1.0
    z = z * p.scale - p.offset * grow
    zz = ops.select(z.z < -0.5 * p.offset.z * grow, z.z + p.offset.z * grow, z.z)
    return ops.vec3(z.x, z.y, zz), dr * p.scale


def _gyroid(q):
    return ops.dot(ops.sin(q), ops.cos(ops.vec3(q.y, q.z, q.x)))


@formula("Gyroid Foam", family="Sponges & Cubes", kind=DIRECT, bounds=1.1, surface_offset=0.5,
         description="Alan Schoen's gyroid carved out of a cube at finer and finer scales: a fractal foam",
         params=(Int("iterations", 4, min=1, max=7, description="Scales of gyroid"),
                 Float("scale", 2.7, min=1.8, max=4.0, description="How much finer each scale is"),
                 Float("period", 6.0, min=2.0, max=16.0, description="Gyroid cells across the cube at the first scale"),
                 Float("thickness", 0.25, min=0.02, max=0.9, description="The channels' width, in cell units")),
         presets={"Default": {}, "Coarse": {"iterations": 2, "thickness": 0.4}, "Lace": {"thickness": 0.12},
                  "Dense": {"period": 10.0, "scale": 2.2}})
def gyroid_foam(pos, p):
    def body(i, state):
        d, s, trap = state
        g = (ops.abs(_gyroid(pos * s)) - p.thickness) / (s * 1.7320508)    # |∇gyroid| ≤ √3
        return ops.max(d, -g), s * p.scale, ops.select(-g > d, i + 1.0, trap)

    (d, _s, trap), _n = ops.loop(p.iterations, 7, (ops.sd_box(pos, _cube()), p.period, 0.0), body)
    return d, trap / p.iterations
