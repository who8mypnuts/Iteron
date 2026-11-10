# SPDX-License-Identifier: MIT
"""Putting the surface where the fractal really is: a calibrated level, vertices moved onto it, normals from it.

* **Calibration.** Distance estimators underestimate: the Mandelbox's reads about a third of the true distance near
  its surface, the bulbs' about half. A level of "half a voxel of estimated distance" would therefore sit several
  voxels out and fill every groove. The field's gradient measures the shortfall (a true distance field has
  |∇d| = 1), so the level is set in *true* distance: `offset × voxel × gain`, the gain being the median |∇d| *on the
  surface itself*. It is found on small full-resolution pilot patches: mesh them at a guessed level, measure the
  gradient at their vertices, re-level, repeat — it settles in two or three rounds (the Mandelbox at ≈ 0.25, the
  bulbs ≈ 0.4, the sponges ≈ 1).
* **Refinement.** Surface nets puts a vertex at the mean of its cube's edge crossings, each linearly interpolated
  between two samples. A few Newton steps on the field, `p ← p − (d(p) − level) ∇d / |∇d|²`, move it onto the level
  set itself — ridges and grooves narrower than a few voxels come out crisp instead of melted. Each step evaluates the
  point and a tetrahedron around it (five evaluations: the exact value, and a gradient as good as six central
  differences give); each step is limited, and the total move stays within a voxel, so the mesh never folds over itself.
* **Normals** are the field's gradient from the last stencil: the shading follows the fractal, not the facets.
"""

from __future__ import annotations

import numpy as np

from .grid import GridPlan
from .surface_nets import surface_nets

CALIBRATION_POINTS = 4000   # surface points the calibration measures
CALIBRATION_ROUNDS = 4      # re-levelling rounds (it settles in two or three)
GAIN_RANGE = (0.02, 1.0)    # a plausible calibration (a true distance field is 1)
STEP_LIMIT = 0.5            # voxels per Newton step
MOVE_LIMIT = 1.0            # voxels in total from the surface-nets position
TETRA = np.array([[1, -1, -1], [-1, -1, 1], [-1, 1, -1], [1, 1, 1]], dtype=np.float64)
STENCIL = np.vstack([np.zeros((1, 3)), TETRA])       # the point itself, then the tetrahedron


def calibration_points(pilots: list[tuple[GridPlan, np.ndarray]], level: float, count: int = CALIBRATION_POINTS,
                       seed: int = 0) -> np.ndarray:
    """Up to `count` surface points (the surface-nets vertices of the pilot patches at `level`), in world space."""
    found = []
    for plan, distance in pilots:
        vertices, _quads = surface_nets(distance, level)
        if len(vertices):
            found.append(plan.to_world(vertices))
    if not found:
        return np.zeros((0, 3))
    points = np.concatenate(found)
    if len(points) > count:
        points = points[np.random.default_rng(seed).choice(len(points), count, replace=False)]
    return points


def gain_at(gradient: np.ndarray) -> float:
    """The median |∇d| over gradients measured on the surface, clipped to a plausible range."""
    magnitude = np.sqrt(np.einsum("ij,ij->i", gradient, gradient))
    magnitude = magnitude[np.isfinite(magnitude)]
    return float(np.clip(np.median(magnitude), *GAIN_RANGE)) if magnitude.size else 1.0


def stencil(points: np.ndarray, eps: float) -> np.ndarray:
    """`(5M, 3)`: each point, then the four corners of a tetrahedron around it (Inigo Quilez's normal trick)."""
    out = np.empty((len(points), 5, 3), dtype=np.float64)
    out[:] = points[:, None, :]
    out += (STENCIL * eps)[None]
    return out.reshape(-1, 3)


def split(samples: np.ndarray, count: int, eps: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Kernel output at `stencil` → (distance (M,), gradient (M, 3), colour channels (M, 3)) at the points: the
    value and colours from the point itself, the gradient Σ kᵢ d(p + kᵢ eps) / (4 eps) from the tetrahedron."""
    s = np.asarray(samples).reshape(count, 5, 4)
    d = [s[:, k, 0].astype(np.float64) for k in range(5)]
    scale = 1.0 / (4.0 * eps)
    gradient = np.stack([(d[1] - d[2] - d[3] + d[4]) * scale,          # the columns of TETRA, written out
                         (-d[1] - d[2] + d[3] + d[4]) * scale,
                         (-d[1] + d[2] - d[3] + d[4]) * scale], axis=1)
    return d[0], gradient, s[:, 0, 1:].astype(np.float64)


def newton_step(points: np.ndarray, origin: np.ndarray, distance: np.ndarray, gradient: np.ndarray, level: float,
                spacing: float) -> np.ndarray:
    """Points moved towards `distance == level` along the gradient, limited per step and in total from `origin`."""
    g2 = np.einsum("ij,ij->i", gradient, gradient)
    ok = np.isfinite(distance) & (g2 > 1e-12)
    move = np.zeros_like(points)
    move[ok] = -((distance[ok] - level) / g2[ok])[:, None] * gradient[ok]
    length = np.linalg.norm(move, axis=1)
    too_far = length > STEP_LIMIT * spacing
    move[too_far] *= (STEP_LIMIT * spacing / length[too_far])[:, None]
    moved = points + move
    offset = moved - origin
    total = np.linalg.norm(offset, axis=1)
    clamp = total > MOVE_LIMIT * spacing
    moved[clamp] = origin[clamp] + offset[clamp] * (MOVE_LIMIT * spacing / total[clamp])[:, None]
    return moved


def normals(gradient: np.ndarray) -> np.ndarray:
    """Unit normals from gradients; `nan` rows where the gradient vanished (the caller keeps the mesh's normal)."""
    length = np.linalg.norm(gradient, axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        n = gradient / length
    n[~(length[:, 0] > 1e-12)] = np.nan
    return n
