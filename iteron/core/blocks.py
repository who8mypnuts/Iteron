# SPDX-License-Identifier: MIT
"""Sparse sampling: the grid as blocks, and which blocks can hold surface.

A build samples and meshes one block at a time (`surface_nets.crossings`), so memory follows the surface, and only
blocks the surface can pass through are sampled at all. The coarse pass every build starts with decides: its samples
with `d < coarse spacing` are *near* the surface (an estimator never overstates a distance, so every surface point is
within reach of such a sample; interior samples count as near too, which only costs time), and a block is occupied
when a near sample lies within reach of it. Calibration uses small full-resolution *pilot* patches centred on near
samples, so they land on the surface whatever the block layout.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np

from .grid import GridPlan
from .surface_nets import AMBIGUITY_PASSES

BLOCK = 160             # voxels per block side (the halo adds ~35 % to sampling)
HALO = AMBIGUITY_PASSES  # extra samples around a block: ambiguity fills reach one voxel per pass, so with a halo as
                         # deep as the passes, a block resolves its voxels exactly as the whole grid would
PILOTS, PILOT_SIZE = 24, 16


@dataclass(frozen=True)
class Block:
    start: tuple[int, int, int]      # the core, in global indices: edges whose low end lies here belong to the block
    stop: tuple[int, int, int]
    lo: tuple[int, int, int]         # the sampled range (the core, its +1 neighbours and the halo, clipped)
    hi: tuple[int, int, int]


def layout(plan: GridPlan, size: int | None = None) -> list[Block]:
    size = size or BLOCK
    shape = np.array(plan.shape)
    blocks = []
    for start in itertools.product(*(range(0, n, size) for n in shape)):
        start = np.array(start)
        stop = np.minimum(start + size, shape)
        lo = np.maximum(start - HALO, 0)
        hi = np.minimum(stop + 1 + HALO, shape)
        blocks.append(Block(tuple(int(v) for v in start), tuple(int(v) for v in stop), tuple(int(v) for v in lo),
                            tuple(int(v) for v in hi)))
    return blocks


def sub_plan(plan: GridPlan, block: Block) -> GridPlan:
    """The block's sampled range as a plan of its own."""
    origin = tuple(float(o + l * plan.spacing) for o, l in zip(plan.origin, block.lo))
    return GridPlan(origin, plan.spacing, tuple(h - l for l, h in zip(block.lo, block.hi)))


def occupied(plan: GridPlan, blocks: list[Block], near: np.ndarray, reach: float) -> list[Block]:
    """The blocks within `reach` of any near-surface point `(K, 3)`."""
    if len(near) == 0 or not blocks:
        return []
    size = BLOCK
    counts = [int(np.ceil(n / size)) for n in plan.shape]
    marked = np.zeros(counts, dtype=bool)
    grid = (near - np.asarray(plan.origin)) / plan.spacing
    margin = reach / plan.spacing + HALO + 1
    for corner in np.array(np.meshgrid([-1, 1], [-1, 1], [-1, 1], indexing="ij")).reshape(3, -1).T:
        index = np.floor((grid + corner * margin) / size).astype(np.int64)
        index = index[np.all((index >= 0) & (index < counts), axis=1)]
        marked[tuple(index.T)] = True
    return [b for b in blocks if marked[tuple(start // size for start in b.start)]]


def pilot_plans(plan: GridPlan, near: np.ndarray, count: int = PILOTS, size: int = PILOT_SIZE,
                seed: int = 0) -> list[GridPlan]:
    """Small full-resolution patches centred on `count` near-surface points (chosen at random, seeded)."""
    if len(near) == 0:
        return []
    rng = np.random.default_rng(seed)
    shape = np.array(plan.shape)
    extent = np.minimum(size, shape)
    plans = []
    for point in near[rng.choice(len(near), min(count, len(near)), replace=False)]:
        centre = np.round((point - np.asarray(plan.origin)) / plan.spacing).astype(np.int64)
        lo = np.clip(centre - extent // 2, 0, shape - extent)
        origin = tuple(float(o + l * plan.spacing) for o, l in zip(plan.origin, lo))
        plans.append(GridPlan(origin, plan.spacing, tuple(int(e) for e in extent)))
    return plans
