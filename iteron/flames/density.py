# SPDX-License-Identifier: MIT
"""A flame's orbit as a solid: points → a density grid → an isosurface (the existing surface nets).

After Fractalchemy's `solid/voxelize.py` (Stan Ragets, MIT), in numpy only: the box is the points' percentile-trimmed
extent (a few runaway points must not shrink everything into a corner), density is points per voxel, blurred with a
separable Gaussian and normalised so its 99th percentile (over occupied voxels) is 1; the surface is where the
normalised density crosses `threshold`. Vertex colours are the mean palette colour around each vertex.
"""

from __future__ import annotations

import numpy as np

from ..core.grid import GridPlan, box_plan
from ..core.surface_nets import surface_nets
from .chaos import Orbit

TRIM = 0.2                  # percent of points trimmed off each end of every axis for the box
NORMALISE = 99.0            # the density percentile that becomes 1.0


def bounds(points: np.ndarray, trim: float = TRIM) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = np.percentile(points, trim, axis=0), np.percentile(points, 100.0 - trim, axis=0)
    span = np.maximum(hi - lo, 1e-6)
    return lo - 0.02 * span, hi + 0.02 * span


def blur(volume: np.ndarray, sigma: float) -> np.ndarray:
    """A separable Gaussian blur (σ in voxels), zero outside the grid."""
    if sigma <= 0:
        return volume
    radius = max(1, int(np.ceil(3.0 * sigma)))
    taps = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    taps /= taps.sum()
    out = volume.astype(np.float32)
    for axis in range(3):
        padded = np.pad(out, [(radius, radius) if a == axis else (0, 0) for a in range(3)])
        acc = np.zeros_like(out)
        for offset, weight in enumerate(taps):
            acc += weight * np.take(padded, np.arange(offset, offset + out.shape[axis]), axis=axis)
        out = acc
    return out


def trilinear(volume: np.ndarray, coords: np.ndarray) -> np.ndarray:
    """`volume` (nx, ny, nz[, C]) interpolated at `(V, 3)` grid coordinates (clamped to the grid)."""
    shape = np.array(volume.shape[:3])
    c = np.clip(coords, 0.0, shape - 1.000001)
    i0 = np.floor(c).astype(np.int64)
    f = c - i0
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = ((f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2]))
                corner = volume[i0[:, 0] + dx, i0[:, 1] + dy, i0[:, 2] + dz].astype(np.float64)
                out = out + (w[:, None] * corner if corner.ndim == 2 else w * corner)
    return out


def density_mesh(orbit: Orbit, resolution: int, threshold: float, smoothing: float):
    """`(vertices (V, 3), quads (Q, 4), colours (V, 3), plan)` of the orbit's dense regions."""
    points = orbit.points.astype(np.float64)
    lo, hi = bounds(points)
    plan = box_plan(lo, hi, resolution)
    index = np.floor((points - np.asarray(plan.origin)) / plan.spacing).astype(np.int64)
    ok = np.all((index >= 0) & (index < np.array(plan.shape)), axis=1)
    flat = np.ravel_multi_index(tuple(index[ok].T), plan.shape)
    size = plan.count
    density = np.bincount(flat, minlength=size).reshape(plan.shape).astype(np.float32)
    rgb = orbit.rgb[ok]
    colour = np.stack([np.bincount(flat, weights=rgb[:, c], minlength=size) for c in range(3)], axis=-1)
    density = blur(density, smoothing)
    colour = np.stack([blur(colour.reshape(plan.shape + (3,))[..., c].astype(np.float32), smoothing) for c in range(3)],
                      axis=-1)
    occupied = density[density > 1e-6]
    scale = float(np.percentile(occupied, NORMALISE)) if occupied.size else 1.0
    norm = density / max(scale, 1e-9)
    grid_vertices, quads = surface_nets(-norm, -threshold)
    weight = np.maximum(trilinear(density, grid_vertices), 1e-9)
    colours = np.clip(trilinear(colour, grid_vertices) / weight[:, None], 0.0, 1.0)
    return plan.to_world(grid_vertices), quads, colours, plan


def dominant_xform(orbit: Orbit, plan: GridPlan, grid_vertices: np.ndarray, smoothing: float,
                   max_cells: int = 128) -> np.ndarray:
    """`(V,)` int16: which transform's points are densest around each vertex (a face's material). Each transform's
    density is binned on a grid of at most `max_cells` per side, blurred like the solid's, and compared there."""
    step = max(1, int(np.ceil(max(plan.shape) / max_cells)))
    shape = tuple(int(np.ceil(n / step)) for n in plan.shape)
    index = np.floor((orbit.points.astype(np.float64) - np.asarray(plan.origin)) / (plan.spacing * step)).astype(np.int64)
    ok = np.all((index >= 0) & (index < np.array(shape)), axis=1)
    flat, which = np.ravel_multi_index(tuple(index[ok].T), shape), orbit.xform[ok]
    coords = np.asarray(grid_vertices, dtype=np.float64) / step
    best = np.full(len(coords), -1.0)
    chosen = np.zeros(len(coords), dtype=np.int16)
    for transform in np.unique(which):
        grid = np.bincount(flat[which == transform], minlength=int(np.prod(shape))).reshape(shape).astype(np.float32)
        here = trilinear(blur(grid, smoothing / step + 0.5), coords)
        better = here > best
        best[better], chosen[better] = here[better], transform
    return chosen


def trimmed(orbit: Orbit, slack: float = 0.5) -> np.ndarray:
    """Which points to keep as a point cloud: within the trimmed box, widened by `slack` of its size."""
    lo, hi = bounds(orbit.points)
    span = hi - lo
    return np.all((orbit.points >= lo - slack * span) & (orbit.points <= hi + slack * span), axis=1)


__all__ = ["density_mesh", "dominant_xform", "trimmed", "blur", "trilinear", "bounds", "GridPlan"]
