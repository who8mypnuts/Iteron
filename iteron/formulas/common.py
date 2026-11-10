# SPDX-License-Identifier: MIT
"""Building blocks shared by several formula families."""

from __future__ import annotations

from ..core import ops

TINY = 1e-10


def triplex_power(z, n):
    """White–Nylander triplex power: z^n in spherical coordinates (theta from the z axis, phi around it)."""
    r = ops.max(ops.length(z), TINY)
    theta = ops.acos(ops.clamp(z.z / r, -1.0, 1.0)) * n
    phi = ops.atan2(z.y, z.x) * n
    sin_theta = ops.sin(theta)
    return ops.pow(r, n) * ops.vec3(sin_theta * ops.cos(phi), sin_theta * ops.sin(phi), ops.cos(theta))


def sphere_fold(z, dr, min_r2, fixed_r2):
    """Tglad's sphere fold: invert inside `fixed_r2`, scale up uniformly inside `min_r2`."""
    factor = fixed_r2 / ops.clamp(ops.dot(z, z), min_r2, fixed_r2)
    return z * factor, dr * factor


def box_fold(v, limit):
    """Tglad's box fold: reflect each coordinate that passes ±limit."""
    return ops.clamp(v, -limit, limit) * 2.0 - v


def sort_descending(z):
    """Reorder the components so x ≥ y ≥ z (the octahedral group's fundamental domain after `abs`)."""
    z = ops.select(z.x < z.y, ops.vec3(z.y, z.x, z.z), z)
    z = ops.select(z.x < z.z, ops.vec3(z.z, z.y, z.x), z)
    return ops.select(z.y < z.z, ops.vec3(z.x, z.z, z.y), z)


def triplex_multiply(a, b):
    """Triplex product: lengths multiply, spherical angles add (the Mandelbulb's multiplication, for hybrids and the
    Lambdabulb)."""
    ra, rb = ops.max(ops.length(a), TINY), ops.max(ops.length(b), TINY)
    theta = ops.acos(ops.clamp(a.z / ra, -1.0, 1.0)) + ops.acos(ops.clamp(b.z / rb, -1.0, 1.0))
    phi = ops.atan2(a.y, a.x) + ops.atan2(b.y, b.x)
    sin_theta = ops.sin(theta)
    return ra * rb * ops.vec3(sin_theta * ops.cos(phi), sin_theta * ops.sin(phi), ops.cos(theta))


def sierpinski_fold(z):
    """Fold into the domain of the tetrahedron's vertex (1, 1, 1): the three reflections of the Sierpinski KIFS."""
    z = ops.select(z.x + z.y < 0.0, ops.vec3(-z.y, -z.x, z.z), z)
    z = ops.select(z.x + z.z < 0.0, ops.vec3(-z.z, z.y, -z.x), z)
    return ops.select(z.y + z.z < 0.0, ops.vec3(z.x, -z.z, -z.y), z)


INV_SQRT3 = 0.5773502691896258


def sd_tetrahedron(z):
    """Distance (a GDF bound) to the tetrahedron with vertices (1,1,1), (1,-1,-1), (-1,1,-1), (-1,-1,1)."""
    a = ops.max(-z.x - z.y - z.z, z.x + z.y - z.z)
    b = ops.max(-z.x + z.y + z.z, z.x - z.y + z.z)
    return (ops.max(a, b) - 1.0) * INV_SQRT3
