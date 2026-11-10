# SPDX-License-Identifier: MIT
"""One build, as a generator of steps: fit, find the occupied blocks, calibrate, mesh block by block, refine,
simplify.

Bpy-free. The sampler is passed in (GPU or CPU), numpy work runs on the worker thread, and every yield is a `Step`
the scheduler can show — so the UI stays live and a newer request can close the job at any step. Memory follows the
surface: a block's samples are dropped once its crossing edges are extracted.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Generator

import numpy as np

from ..core import blocks as blk
from ..core import refine
from ..core.formula import REGISTRY
from ..core.grid import FIT_RESOLUTION, GridPlan, box_plan, cube_plan, fitted_bounds
from ..core.simplify import simplify
from ..core.surface_nets import assemble, crossings
from .steps import GpuTurn, Waiting, in_thread

CHANNELS = ("trap", "iterations", "radius")
GRADIENT_EPS = 0.25          # voxels: the stencil size for refinement and normals
EVAL_BATCH = 1 << 20         # points per evaluation batch


@dataclass(frozen=True)
class BuildSpec:
    formula_id: str
    values: dict[str, Any]
    center: tuple[float, float, float] = (0.0, 0.0, 0.0)
    half_size: float = 0.0                 # 0: the formula's default bounds
    auto_fit: bool = True
    resolution: int = 96
    surface_offset: float = 0.5            # the surface sits this many voxels of *true* distance out (see refine.py)
    final: bool = False
    refine_steps: int = 2                  # Newton steps moving vertices onto the surface (0: none)
    field_normals: bool = True             # normals from the field's gradient
    simplify: float = 0.0                  # merge flat regions within this many voxels (0: off)


@dataclass
class BuildResult:
    vertices: np.ndarray                   # (V, 3) float32, object space
    quads: np.ndarray                      # (Q, 4) int32
    channels: np.ndarray                   # (V, 3) float32 in 0…1: trap, iterations, radius
    plan: GridPlan
    sampler: str
    seconds: float
    spec: BuildSpec = field(repr=False, default=None)
    normals: np.ndarray | None = None      # (V, 3) float32 unit normals (nan rows: use the mesh's own)
    gain: float = 1.0                      # the distance estimator's calibration (|∇d| near the surface)
    tris: np.ndarray | None = None         # (T, 3) int32: triangles left by simplification

    @property
    def faces(self) -> int:
        return len(self.quads) + (0 if self.tris is None else len(self.tris))


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
    plan, near, reach = yield from _plan(spec, sampler, entry, values)
    occupied = blk.occupied(plan, blk.layout(plan), near, reach)
    gain = yield from _calibrate(spec, sampler, entry, values, plan, near)
    level = spec.surface_offset * plan.spacing * gain
    keys, points = [], []
    shape = "×".join(str(n) for n in plan.shape)
    for index, block in enumerate(occupied):
        lo, hi = 0.08 + 0.6 * index / len(occupied), 0.08 + 0.6 * (index + 1) / len(occupied)
        message = f"Sampling {shape} · block {index + 1}/{len(occupied)}"
        found = yield from _stage(sampler.sample(entry, values, blk.sub_plan(plan, block)), lo, hi, message)
        k, p = yield from _stage(in_thread(crossings, found.distance, level, block.lo, block.stop, block.start,
                                           plan.shape), hi, hi, message)
        keys.append(k)
        points.append(p)
    grid_vertices, quads = yield from _stage(in_thread(assemble, keys, points, plan.count), 0.68, 0.72, "Meshing")
    del keys, points
    vertices = plan.to_world(grid_vertices)
    normals, tris = None, None
    if spec.refine_steps > 0 or spec.field_normals:
        vertices, normals, raw, gain = yield from _refine(spec, sampler, entry, values, vertices, gain, plan)
    else:
        raw = (yield from _stage(_evaluate(sampler, entry, values, vertices), 0.72, 0.95, "Colouring"))[:, 1:]
    channels = yield from _stage(in_thread(normalise, np.asarray(raw, dtype=np.float64)), 0.95, 0.96, "Colouring")
    if spec.simplify > 0 and normals is not None and len(quads):
        reduced = yield from _stage(in_thread(simplify, vertices, normals, channels, quads, plan.origin, plan.spacing,
                                              spec.simplify * plan.spacing), 0.96, 1.0, "Simplifying")
        vertices, normals, channels, quads, tris = (reduced.vertices, reduced.normals, reduced.channels, reduced.quads,
                                                    reduced.tris)
    return BuildResult(vertices.astype(np.float32), quads, np.asarray(channels, dtype=np.float32), plan, sampler.name,
                       time.perf_counter() - started, spec, None if normals is None or not spec.field_normals
                       else normals.astype(np.float32), gain, tris)


def _plan(spec: BuildSpec, sampler, entry, values):
    """A coarse pass over the region, then the full grid: the region, shrunk by auto-fit to where the coarse pass
    finds the fractal. Returns the grid, the coarse samples near the surface (world points) and their reach."""
    half = spec.half_size or entry.bounds
    center = np.asarray(spec.center, dtype=np.float64)
    coarse = cube_plan(center, half, FIT_RESOLUTION)
    found = yield from _stage(sampler.sample(entry, values, coarse), 0.0, 0.06, "Finding the surface")
    near = coarse.to_world(np.argwhere(found.distance < coarse.spacing))
    if not spec.auto_fit:
        return cube_plan(center, half, spec.resolution), near, coarse.spacing
    lo, hi = fitted_bounds(coarse, found.distance, center - half, center + half) or (center - half, center + half)
    return box_plan(lo, hi, spec.resolution), near, coarse.spacing


def _calibrate(spec: BuildSpec, sampler, entry, values, plan: GridPlan, near: np.ndarray):
    """The estimator's gain at the surface, from pilot patches on near-surface points (see refine.py)."""
    pilots = []
    for pilot in blk.pilot_plans(plan, near):
        found = yield from _stage(sampler.sample(entry, values, pilot), 0.06, 0.07, "Calibrating")
        pilots.append((pilot, found.distance))
    gain, eps = 1.0, GRADIENT_EPS * plan.spacing
    for _round in range(refine.CALIBRATION_ROUNDS):
        points = refine.calibration_points(pilots, max(spec.surface_offset, 0.1) * plan.spacing * gain)
        if len(points) == 0:
            break
        out = yield from _stage(_evaluate(sampler, entry, values, refine.stencil(points, eps)), 0.07, 0.08, "Calibrating")
        measured = refine.gain_at(refine.split(out, len(points), eps)[1])
        settled = abs(measured - gain) < 0.05 * gain
        gain = measured
        if settled:
            break
    return gain


def _refine(spec: BuildSpec, sampler, entry, values, vertices: np.ndarray, gain: float, plan: GridPlan):
    """Each pass evaluates every vertex and a tetrahedron around it (value + gradient, five evaluations) and
    takes one Newton step; the last pass's gradient is the normal and its values the colours. The first pass also
    re-measures the calibration on the whole surface (the pilots only see patches of it) and re-aims the level.
    With field normals and no refinement, one pass is made without moving."""
    origin = vertices.copy()
    eps = GRADIENT_EPS * plan.spacing
    passes = max(spec.refine_steps, 1)
    for index in range(passes):
        lo, hi = 0.72 + 0.23 * index / passes, 0.72 + 0.23 * (index + 1) / passes
        message = f"Refining ({index + 1}/{passes})" if spec.refine_steps else "Normals"
        out = yield from _stage(_evaluate(sampler, entry, values, refine.stencil(vertices, eps)), lo, hi, message)
        distance, gradient, raw = refine.split(out, len(vertices), eps)
        if index == 0 and spec.refine_steps:
            gain = refine.gain_at(gradient)
        if spec.refine_steps:
            level = spec.surface_offset * plan.spacing * gain
            vertices = yield from _stage(in_thread(refine.newton_step, vertices, origin, distance, gradient, level,
                                                   plan.spacing), hi, hi, message)
    return vertices, refine.normals(gradient), raw, gain


def _evaluate(sampler, entry, values, points: np.ndarray):
    """Kernel output at `points`, in batches (bounded memory on either sampler)."""
    out = np.empty((len(points), 4), dtype=np.float32)
    for start in range(0, len(points), EVAL_BATCH):
        batch = points[start:start + EVAL_BATCH]
        out[start:start + len(batch)] = yield from _scaled(sampler.evaluate(entry, values, batch), start, len(batch),
                                                           len(points))
    return out


def _scaled(inner: Generator, start: int, count: int, total: int):
    """Re-yield a batch's progress as progress through all batches."""
    try:
        while True:
            item = next(inner)
            if isinstance(item, (Waiting, GpuTurn)):
                item.fraction = (start + (item.fraction or 0.0) * count) / max(total, 1)
            yield item
    except StopIteration as done:
        return done.value
    finally:
        inner.close()


def normalise(raw: np.ndarray) -> np.ndarray:
    """Each colour channel stretched to 0…1 over its 1st–99th percentile."""
    if raw.shape[0] == 0:
        return np.zeros((0, 3), dtype=np.float32)
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
