# SPDX-License-Identifier: MIT
"""The sampled field of one build: distance as float32, the three colour channels as float16 (half the memory;
colour needs no more precision)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BYTES_PER_VOXEL = 4 + 3 * 2


@dataclass
class Samples:
    distance: np.ndarray      # (nx, ny, nz) float32
    channels: np.ndarray      # (nx, ny, nz, 3) float16: trap, iterations, radius

    @classmethod
    def empty(cls, shape: tuple[int, int, int]) -> "Samples":
        return cls(np.empty(shape, dtype=np.float32), np.empty(shape + (3,), dtype=np.float16))

    def store(self, first: int, block: np.ndarray) -> None:
        """Write `(nx, ny, k, 4)` kernel output into slices `first … first + k`."""
        k = block.shape[2]
        self.distance[:, :, first:first + k] = block[..., 0]
        self.channels[:, :, first:first + k] = np.clip(block[..., 1:], -6e4, 6e4)


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
