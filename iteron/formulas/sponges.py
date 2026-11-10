# SPDX-License-Identifier: MIT
"""Sponges: cubes with recursive holes."""

from __future__ import annotations

from ..core import ops
from ..core.formula import DIRECT, IFS, formula
from ..core.params import Bool, Float, Int, Vec3
from .common import sort_descending


@formula("Menger Sponge", family="Sponges", kind=IFS, bounds=1.1, surface_offset=0.5,
         description="The Menger sponge as a kaleidoscopic IFS: fold, sort, scale by 3",
         params=(Float("scale", 3.0, min=1.5, max=4.0, hard_min=1.01, description="Scale of each iteration (3 is Menger)"),
                 Vec3("offset", (1.0, 1.0, 1.0), min=0.0, max=2.0, description="The corner the copies are scaled towards")),
         shape=lambda z, p: ops.sd_box(z, ops.vec3(1.0)),
         overrides={"iterations": {"default": 4, "max": 12}},
         presets={"Level 4": {}, "Level 2": {"iterations": 2}, "Level 5": {"iterations": 5},
                  "Stretched": {"offset": (1.0, 0.7, 1.0)}})
def menger(z, dr, c, p):
    z = sort_descending(ops.abs(z))
    grow = p.scale - 1.0
    z = z * p.scale - p.offset * grow
    # the layer that fell into the cut-out cross is folded back (Knighty's construction)
    zz = ops.select(z.z < -0.5 * p.offset.z * grow, z.z + p.offset.z * grow, z.z)
    return ops.vec3(z.x, z.y, zz), dr * p.scale


@formula("Mosely Snowflake", family="Sponges", kind=DIRECT, bounds=1.1, surface_offset=0.5,
         description="A Menger-like cube keeping the edge and face cubes, dropping the corners (and the centre)",
         params=(Int("iterations", 4, min=1, max=7, description="Levels of subdivision"),
                 Float("cell_size", 1.0 / 3.0, min=0.2, max=0.45, description="Size of the cut corner cubes (1/3 is Mosely)"),
                 Bool("drop_centre", True, description="Also remove the centre cube of every cell")),
         presets={"Default": {}, "Keep Centre": {"drop_centre": False}, "Lace": {"cell_size": 0.4}})
def mosely(pos, p):
    # The corner cut is centred on the cell's corner and twice the corner cube's size, so it also covers the mirror
    # corner of the neighbouring cell: no cut face coincides with the cube's face (which would leave a phantom skin).
    corner = ops.vec3(2.0 * p.cell_size)
    centre = ops.vec3(p.cell_size)

    def body(i, state):
        d, s, level = state
        a = ops.mod(pos * s + 1.0, 2.0) - 1.0    # cell coordinates in [-1, 1]; cells centred on the cube's grid
        cut = ops.sd_box(ops.abs(a) - 1.0, corner)
        cut = ops.select(p.drop_centre, ops.min(cut, ops.sd_box(a, centre)), cut)
        new = ops.max(d, -cut / s)
        return new, s * 3.0, ops.select(new > d + 1e-6, i + 1.0, level)

    (d, _s, level), _n = ops.loop(p.iterations, 7, (ops.sd_box(pos, ops.vec3(1.0)), 1.0, 0.0), body)
    return d, level / p.iterations


@formula("Jerusalem Cube", family="Sponges", kind=DIRECT, bounds=1.1, surface_offset=0.5,
         description="A cube minus a cross of slabs; its 8 corner cubes and 12 edge cubes repeat the pattern",
         params=(Int("iterations", 4, min=1, max=10, description="Levels of the pattern"),
                 Float("ratio", 2.41421356, min=2.1, max=3.2, description="Cube to corner-cube ratio (1 + √2 is "
                       "the Jerusalem cube)")),
         presets={"Default": {}, "Level 2": {"iterations": 2}, "Chunky": {"ratio": 2.2}, "Airy": {"ratio": 2.8}})
def jerusalem_cube(pos, p):
    k = p.ratio
    a, b = 2.0 / k, 2.0 / (k * k)           # the corner cube's side; the edge cube's side (and the slab width)

    def body(_i, state):
        z, s, d, corners = state
        z = sort_descending(ops.abs(z))      # x ≥ y ≥ z ≥ 0
        in_corner = z.z > b * 0.5
        corner = (z - (1.0 - a * 0.5)) * k
        edge = ops.vec3(z.x - (1.0 - b * 0.5), z.y - (1.0 - b * 0.5), z.z) * (k * k)
        z = ops.select(in_corner, corner, edge)
        s = s * ops.select(in_corner, k, k * k)
        return z, s, ops.max(d, ops.sd_box(z, ops.vec3(1.0)) / s), corners + ops.select(in_corner, 1.0, 0.0)

    (_z, _s, d, corners), _n = ops.loop(p.iterations, 10, (pos, 1.0, ops.sd_box(pos, ops.vec3(1.0)), 0.0), body)
    return d, corners / p.iterations
