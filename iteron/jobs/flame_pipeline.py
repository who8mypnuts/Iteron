# SPDX-License-Identifier: MIT
"""One flame build, as a generator of steps: the chaos game, then either a point cloud or a density mesh. Bpy-free;
the numpy work runs on the worker thread (flames are CPU-only: the chaos game's branching suits numpy)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..flames.chaos import chaos_game
from ..flames.density import density_mesh, trimmed
from ..flames.formats import TO_BLENDER
from ..flames.model import Flame
from .pipeline import Step, _stage
from .steps import Cancel, Cancelled, in_thread

POINTS, MESH = "POINTS", "MESH"


@dataclass(frozen=True)
class FlameSpec:
    flame: dict[str, Any]
    points: int = 1_000_000
    seed: int = 1
    output: str = POINTS
    resolution: int = 128
    threshold: float = 0.15
    smoothing: float = 1.0
    final: bool = False


@dataclass
class FlameResult:
    vertices: np.ndarray                   # (V, 3) float32
    quads: np.ndarray                      # (Q, 4) int32 (none for a point cloud)
    colours: np.ndarray                    # (V, 3) float32: the palette colour
    xform: np.ndarray | None               # (V,) int16: the transform that made each point (point clouds)
    seconds: float
    unsupported: tuple[str, ...] = ()
    sampler: str = "CPU"
    tris: np.ndarray | None = None
    spec: FlameSpec | None = field(default=None, repr=False)

    @property
    def faces(self) -> int:
        return len(self.quads)


def build(spec: FlameSpec, cancel: Cancel | None = None):
    started = time.perf_counter()
    cancel = cancel or Cancel()
    flame = Flame.from_dict(spec.flame)
    progress = [0.0]

    def iterate():
        return chaos_game(flame, spec.points, spec.seed, lambda f: progress.__setitem__(0, f), cancel)

    share = 0.6 if spec.output == MESH else 0.95
    try:
        orbit = yield from _stage(in_thread(iterate, progress=progress), 0.0, share, "Iterating")
    except GeneratorExit:
        cancel.set()
        raise
    if orbit is None:
        raise Cancelled
    orbit.points = orbit.points @ TO_BLENDER.T.astype(np.float32)      # before meshing, so faces stay outward
    if spec.output == POINTS:
        keep = trimmed(orbit)
        return FlameResult(orbit.points[keep], np.zeros((0, 4), dtype=np.int32), orbit.rgb[keep], orbit.xform[keep],
                           time.perf_counter() - started, orbit.unsupported, spec=spec)
    vertices, quads, colours, _plan = yield from _stage(
        in_thread(density_mesh, orbit, spec.resolution, spec.threshold, spec.smoothing), share, 1.0, "Meshing")
    return FlameResult(vertices.astype(np.float32), quads, colours.astype(np.float32), None,
                       time.perf_counter() - started, orbit.unsupported, spec=spec)


__all__ = ["FlameSpec", "FlameResult", "build", "POINTS", "MESH", "Step"]
