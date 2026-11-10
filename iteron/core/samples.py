# SPDX-License-Identifier: MIT
"""The sampled distance field of a grid (or a block of one). Colours are evaluated exactly at the vertices later,
so only the distance is kept."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BYTES_PER_VOXEL = 4


@dataclass
class Samples:
    distance: np.ndarray      # (nx, ny, nz) float32

    @classmethod
    def empty(cls, shape: tuple[int, int, int]) -> "Samples":
        return cls(np.empty(shape, dtype=np.float32))

    def store(self, first: int, block: np.ndarray) -> None:
        """Write `(nx, ny, k, 4)` kernel output into slices `first … first + k` (the distance channel)."""
        self.distance[:, :, first:first + block.shape[2]] = block[..., 0]
