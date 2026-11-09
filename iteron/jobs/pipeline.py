# SPDX-License-Identifier: MIT
"""One build, as a generator of steps: fit the box, sample the field, mesh it, colour the vertices.

Bpy-free. The sampler is passed in (GPU or CPU), heavy numpy work runs on the worker thread, and every yield is a
`Step` the scheduler can show — so the UI stays live and a newer request can close the job at any step.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Generator

import numpy as np

from ..core.formula import REGISTRY
from ..core.grid import FIT_RESOLUTION, GridPlan, box_plan, cube_plan, fitted_bounds
from ..core.samples import Samples, trilinear
from ..core.surface_nets import surface_nets
from .steps import GpuTurn, Waiting, in_thread

CHANNELS = ("trap", "iterations", "radius")


@dataclass(frozen=True)
class BuildSpec:
    formula_id: str
    values: dict[str, Any]
    center: tuple[float, float, float] = (0.0, 0.0, 0.0)
    half_size: float = 0.0                 # 0: the formula's default bounds
    auto_fit: bool = True
    resolution: int = 96
    surface_offset: float = 0.5            # the surface is `distance = offset × voxel size`
    final: bool = False


@dataclass
class BuildResult:
    vertices: np.ndarray                   # (V, 3) float32, object space
    quads: np.ndarray                      # (Q, 4) int32
    channels: np.ndarray                   # (V, 3) float32 in 0…1: trap, iterations, radius
    plan: GridPlan
    sampler: str
    seconds: float
    spec: BuildSpec = field(repr=False, default=None)


@dataclass
class Step:
    fraction: float
    message: str
    waiting: bool = False                  # a worker thread is busy: come back later rather than spin
    needs_gpu: bool = False                # the next step draws: advance the job from a draw callback


def build(spec: BuildSpec, sampler) -> Generator[Step, None, BuildResult]:
    started = time.perf_counter()
    entry = REGISTRY[spec.formula_id]
    values = entry.values(spec.values)
    half = spec.half_size or entry.bounds
    center = np.asarray(spec.center, dtype=np.float64)
    if spec.auto_fit:
        coarse = cube_plan(center, half, FIT_RESOLUTION)
        found = yield from _stage(sampler.sample(entry, values, coarse), 0.0, 0.1, "Fitting")
        lo, hi = fitted_bounds(coarse, found.distance, center - half, center + half) or (center - half, center + half)
        plan = box_plan(lo, hi, spec.resolution)
    else:
        plan = cube_plan(center, half, spec.resolution)
    shape = "×".join(str(n) for n in plan.shape)
    samples = yield from _stage(sampler.sample(entry, values, plan), 0.1, 0.8, f"Sampling {shape}")
    grid_vertices, quads = yield from _stage(in_thread(surface_nets, samples.distance, spec.surface_offset * plan.spacing),
                                             0.8, 0.95, "Meshing")
    channels = yield from _stage(in_thread(vertex_channels, samples, grid_vertices), 0.95, 1.0, "Colouring")
    return BuildResult(plan.to_world(grid_vertices).astype(np.float32), quads, channels, plan, sampler.name,
                       time.perf_counter() - started, spec)


def vertex_channels(samples: Samples, grid_vertices: np.ndarray) -> np.ndarray:
    """The colour channels at the vertices, each stretched to 0…1 over its 1st–99th percentile."""
    if grid_vertices.shape[0] == 0:
        return np.zeros((0, 3), dtype=np.float32)
    raw = trilinear(samples.channels, grid_vertices)
    lo, hi = np.percentile(raw, 1, axis=0), np.percentile(raw, 99, axis=0)
    span = np.where(hi - lo > 1e-9, hi - lo, 1.0)
    return np.clip((raw - lo) / span, 0.0, 1.0).astype(np.float32)


def _stage(inner: Generator, lo: float, hi: float, message: str) -> Generator[Step, None, Any]:
    """Re-yield a sub-generator's progress (floats, `Waiting` or `GpuTurn`) as `Step`s in `lo…hi`; return its value."""
    try:
        while True:
            item = next(inner)
            fraction = (item.fraction if isinstance(item, (Waiting, GpuTurn)) else item) or 0.0
            yield Step(lo + (hi - lo) * fraction, message, isinstance(item, Waiting), isinstance(item, GpuTurn))
    except StopIteration as done:
        return done.value
    finally:
        inner.close()
