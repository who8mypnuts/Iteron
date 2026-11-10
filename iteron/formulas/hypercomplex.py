# SPDX-License-Identifier: MIT
"""More four-dimensional algebras, seen through 3D slices: the quaternion Mandelbrot set, cubic quaternion Julia
sets, and Rochon's bicomplex Mandelbrot (the "tetrabrot") and Julia sets. Distance from the running derivative,
as for the quaternion Julia set."""

from __future__ import annotations

from ..core import ops
from ..core.formula import DIRECT, formula
from ..core.params import Float, Int, Vec3
from .quaternion import _square

_ITERATIONS = Int("iterations", 12, min=1, max=64, description="Iterations per point")
_SLICE = Float("slice", 0.0, min=-1.5, max=1.5, description="The fourth coordinate of the 3D slice")
_BAILOUT = Float("bailout", 4.0, min=2.0, max=64.0, hard_min=1.0, description="Radius beyond which a point has escaped")


def _multiply(a, b):
    """The quaternion product a·b for (x; y, z, w) with x the real part."""
    return ops.vec4(a.x * b.x - a.y * b.y - a.z * b.z - a.w * b.w,
                    a.x * b.y + a.y * b.x + a.z * b.w - a.w * b.z,
                    a.x * b.z - a.y * b.w + a.z * b.x + a.w * b.y,
                    a.x * b.w + a.y * b.z - a.z * b.y + a.w * b.x)


def _bicomplex_square(q):
    """(z₁ + z₂ j)² = (z₁² − z₂²) + 2 z₁z₂ j for z₁ = x + iy, z₂ = z + iw (i and j commute)."""
    x, y, z, w = q.x, q.y, q.z, q.w
    return ops.vec4(x * x - y * y - z * z + w * w, 2.0 * (x * y - z * w), 2.0 * (x * z - y * w), 2.0 * (x * w + y * z))


def _iterate(start, c, p, step, degree: float, max_iterations: int = 64):
    """`(distance, trap)` for the escape-time map `step(q) + c` from `start`."""
    bail2 = p.bailout * p.bailout

    def body(_i, state):
        q, dq, trap = state
        dq = degree * ops.pow(ops.max(ops.length(q), 1e-10), degree - 1.0) * dq + 1.0
        q = step(q) + c
        return q, dq, ops.min(trap, ops.dot(q, q))

    (q, dq, trap), _n = ops.loop(p.iterations, max_iterations, (start, 1.0, ops.dot(start, start)), body,
                                 until=lambda s: ops.dot(s[0], s[0]) > bail2)
    r = ops.max(ops.length(q), 1e-10)
    return 0.5 * r * ops.log(r) / dq, ops.sqrt(trap)


@formula("Quaternion Mandelbrot", family="Hypercomplex", kind=DIRECT, bounds=1.8,
         description="The Mandelbrot set in the quaternions: every point is its own constant, q² + c",
         params=(_ITERATIONS, _SLICE, _BAILOUT),
         presets={"Default": {}, "Sliced": {"slice": 0.3}, "Deep": {"iterations": 20}})
def quaternion_mandelbrot(pos, p):
    c = ops.vec4(pos.x, pos.y, pos.z, p.slice)
    return _iterate(c, c, p, _square, 2.0)


@formula("Cubic Quaternion Julia", family="Hypercomplex", kind=DIRECT, bounds=1.5,
         description="A Julia set of q³ + c in the quaternions",
         params=(_ITERATIONS,
                 Vec3("c", (-0.45, 0.5, 0.2), min=-1.5, max=1.5, label="C", description="The first three components of C"),
                 Float("c_w", 0.1, min=-1.5, max=1.5, label="C w", description="The fourth component of C"),
                 _SLICE, _BAILOUT),
         presets={"Default": {}, "Spiky": {"c": (0.2, 0.6, -0.3), "c_w": 0.0},
                  "Lobes": {"c": (-0.6, 0.1, 0.1), "c_w": 0.2}})
def cubic_quaternion_julia(pos, p):
    return _iterate(ops.vec4(pos.x, pos.y, pos.z, p.slice), ops.vec4(p.c.x, p.c.y, p.c.z, p.c_w), p,
                    lambda q: _multiply(q, _square(q)), 3.0)


@formula("Tetrabrot", family="Hypercomplex", kind=DIRECT, bounds=2.0,
         description="Dominic Rochon's tetrabrot: the Mandelbrot set of the bicomplex numbers, sliced to 3D",
         params=(_ITERATIONS, _SLICE, _BAILOUT),
         presets={"Default": {}, "Sliced": {"slice": 0.25}, "Deep": {"iterations": 20}})
def tetrabrot(pos, p):
    c = ops.vec4(pos.x, pos.y, pos.z, p.slice)
    return _iterate(c, c, p, _bicomplex_square, 2.0)


@formula("Bicomplex Julia", family="Hypercomplex", kind=DIRECT, bounds=1.8,
         description="A Julia set of z² + c in the bicomplex numbers, sliced to 3D",
         params=(_ITERATIONS,
                 Vec3("c", (-0.6, 0.4, 0.1), min=-1.5, max=1.5, label="C", description="The first three components of C"),
                 Float("c_w", 0.0, min=-1.5, max=1.5, label="C w", description="The fourth component of C"),
                 _SLICE, _BAILOUT),
         presets={"Default": {}, "Dendrite": {"c": (0.0, 1.0, 0.0)}, "Rabbit": {"c": (-0.12, 0.75, 0.1)}})
def bicomplex_julia(pos, p):
    return _iterate(ops.vec4(pos.x, pos.y, pos.z, p.slice), ops.vec4(p.c.x, p.c.y, p.c.z, p.c_w), p,
                    _bicomplex_square, 2.0)
