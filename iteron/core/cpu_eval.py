# SPDX-License-Identifier: MIT
"""The CPU path: evaluate a formula's kernel with numpy (float64) on batches of points."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from .formula import Formula, numpy_values
from .runners import kernel
from .vec import NVec

CHUNK = 1 << 17            # points per batch: big enough to amortise Python overhead, small enough for the cache
FAR = 1e6                  # distance reported where the estimate is not finite (treated as far outside)


def evaluate(entry: Formula, values: dict[str, Any], points: np.ndarray) -> np.ndarray:
    """`(M, 4)` float32 — distance, trap, iterations, radius — at `(M, 3)` points."""
    p = numpy_values(entry, values)
    pos = NVec(np.ascontiguousarray(points, dtype=np.float64).T)
    with np.errstate(all="ignore"):
        channels = kernel(entry, pos, p)
    out = np.empty((points.shape[0], 4), dtype=np.float32)
    for index, channel in enumerate(channels):
        out[:, index] = np.broadcast_to(np.asarray(channel, dtype=np.float64), (points.shape[0],))
    return sanitize(out)


def sanitize(samples: np.ndarray) -> np.ndarray:
    """Non-finite distances become FAR (outside); non-finite colour channels become 0. In place; returns it."""
    distance = samples[..., 0]
    distance[~np.isfinite(distance)] = FAR
    colours = samples[..., 1:]
    colours[~np.isfinite(colours)] = 0.0
    return samples


def evaluate_chunked(entry: Formula, values: dict[str, Any], points: np.ndarray,
                     progress: Callable[[float], None] | None = None,
                     cancelled: Callable[[], bool] | None = None) -> np.ndarray | None:
    """`evaluate` in batches, reporting progress; returns None when cancelled."""
    out = np.empty((points.shape[0], 4), dtype=np.float32)
    for start in range(0, points.shape[0], CHUNK):
        if cancelled and cancelled():
            return None
        stop = min(start + CHUNK, points.shape[0])
        out[start:stop] = evaluate(entry, values, points[start:stop])
        if progress:
            progress(stop / max(points.shape[0], 1))
    return out
