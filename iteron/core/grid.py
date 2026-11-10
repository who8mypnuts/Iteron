# SPDX-License-Identifier: MIT
"""Where to sample: the voxel grid plan, and auto-fit (shrink the box to where the fractal is)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

FIT_RESOLUTION = 40        # the coarse pass auto-fit samples
FIT_MARGIN = 1.5           # coarse voxels added around what the coarse pass found
PAD = 2                    # fine voxels of empty border, so the surface closes without clipping the fractal
SURFACE_EXPONENT = 2.5     # fractal surfaces grow faster than res²: faces ≈ faces₀ (res / res₀)^2.5 (2.2 – 2.7 seen)
BYTES_PER_FACE = 240       # peak build memory per output face (edges, assembly, refinement, the Blender mesh)


@dataclass(frozen=True)
class GridPlan:
    """Sample points `origin + (i, j, k) * spacing` for `0 <= (i, j, k) < shape`."""
    origin: tuple[float, float, float]
    spacing: float
    shape: tuple[int, int, int]

    @property
    def count(self) -> int:
        return self.shape[0] * self.shape[1] * self.shape[2]

    def slab_points(self, first: int, last: int) -> np.ndarray:
        """`(M, 3)` points of slices `first <= k < last`, ordered so they reshape to `(nx, ny, last - first)`."""
        axes = [np.arange(n, dtype=np.float64) for n in self.shape[:2]] + [np.arange(first, last, dtype=np.float64)]
        ii, jj, kk = np.meshgrid(*axes, indexing="ij")
        grid = np.stack([ii.ravel(), jj.ravel(), kk.ravel()], axis=1)
        return np.asarray(self.origin) + grid * self.spacing

    def to_world(self, grid_coords: np.ndarray) -> np.ndarray:
        return np.asarray(self.origin) + np.asarray(grid_coords, dtype=np.float64) * self.spacing


def region(bounds: float, center, half_size: float) -> tuple[np.ndarray, np.ndarray]:
    """The sampling box: `center ± half_size`, or `center ± bounds` (the formula's own) when `half_size` is 0."""
    c = np.asarray(center, dtype=np.float64)
    half = half_size or bounds
    return c - half, c + half


def cube_plan(center, half_size: float, resolution: int) -> GridPlan:
    """`resolution` points per side spanning the cube `center ± half_size`."""
    resolution = max(int(resolution), 4)
    spacing = 2.0 * half_size / (resolution - 1)
    origin = tuple(float(c) - half_size for c in center)
    return GridPlan(origin, spacing, (resolution,) * 3)


def box_plan(lo, hi, resolution: int, pad: int = PAD) -> GridPlan:
    """Cubic voxels over the box `lo…hi`, `resolution` points along its longest side, plus `pad` all round."""
    lo, hi = np.asarray(lo, dtype=np.float64), np.asarray(hi, dtype=np.float64)
    extent = np.maximum(hi - lo, 1e-9)
    spacing = float(extent.max()) / max(int(resolution) - 1, 1)
    shape = tuple(int(math.ceil(e / spacing)) + 1 + 2 * pad for e in extent)
    origin = tuple(float(v) for v in lo - pad * spacing)
    return GridPlan(origin, spacing, shape)


def fitted_bounds(coarse: GridPlan, distance: np.ndarray, lo, hi) -> tuple[np.ndarray, np.ndarray] | None:
    """The part of `lo…hi` where the coarse distances come within one coarse voxel of the surface, with a margin.
    None when the coarse pass found nothing (keep the whole box)."""
    near = distance < coarse.spacing
    if not near.any():
        return None
    idx = np.argwhere(near)
    found_lo = coarse.to_world(idx.min(axis=0) - FIT_MARGIN)
    found_hi = coarse.to_world(idx.max(axis=0) + FIT_MARGIN)
    return np.maximum(found_lo, lo), np.minimum(found_hi, hi)


def estimate_faces(faces: int, resolution: int, target: int) -> int:
    """About how many faces a build at `target` will have, from one at `resolution` with `faces`."""
    return int(faces * (target / max(resolution, 1)) ** SURFACE_EXPONENT)


def estimate_bytes(faces: int) -> int:
    """About the peak memory of a build that makes `faces` faces (blocks keep the sampled volume small)."""
    return int(faces) * BYTES_PER_FACE + 64 * 1024 * 1024
