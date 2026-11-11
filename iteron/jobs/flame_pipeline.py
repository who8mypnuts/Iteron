# SPDX-License-Identifier: MIT
"""One flame build, as a generator of steps: the chaos game, then either a point cloud or a density mesh, and (when
asked) holon instances. Bpy-free; the numpy work runs on the worker thread (flames are CPU-only: the chaos game's
branching suits numpy)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..flames import holon
from ..flames.chaos import chaos_game
from ..flames.density import density_mesh, dominant_xform, trimmed
from ..flames.formats import TO_BLENDER
from ..flames.model import Flame
from .pipeline import Step, _stage
from .steps import Cancel, Cancelled, in_thread

POINTS, MESH = "POINTS", "MESH"


@dataclass(frozen=True)
class InstanceSpec:
    """Holons along the flame (or along `flame`, an IFS of their own): see flames/holon.py."""
    mode: str = "CHAOS"                    # CHAOS (orbit samples) or TREE (every composition)
    count: int = 2000
    depth: int = 6
    leaves_only: bool = False
    frames: str = "JACOBIAN"               # JACOBIAN (turned and scaled) or TRANSLATION (scaled only)
    size: float = 0.1
    falloff: float = 1.0
    min_size: float = 0.002
    cap: int = 20000
    seed: int = 1
    flame: dict[str, Any] | None = None


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
    instances: InstanceSpec | None = None


@dataclass
class FlameResult:
    vertices: np.ndarray                   # (V, 3) float32
    quads: np.ndarray                      # (Q, 4) int32 (none for a point cloud)
    colours: np.ndarray                    # (V, 3) float32: the palette colour
    xform: np.ndarray | None               # (V,) int16: the transform that made each point (the densest, on a solid)
    seconds: float
    unsupported: tuple[str, ...] = ()
    sampler: str = "CPU"
    tris: np.ndarray | None = None
    spec: FlameSpec | None = field(default=None, repr=False)
    instances: holon.InstanceSet | None = None     # in Blender's space, sized
    instance_colours: np.ndarray | None = None     # (N, 3) the palette colour of each instance's orbit point

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

    share = 0.6 if spec.output == MESH else 0.9
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
        result = FlameResult(orbit.points[keep], np.zeros((0, 4), dtype=np.int32), orbit.rgb[keep], orbit.xform[keep],
                             0.0, orbit.unsupported, spec=spec)
    else:
        vertices, quads, colours, plan = yield from _stage(
            in_thread(density_mesh, orbit, spec.resolution, spec.threshold, spec.smoothing), share, 0.9, "Meshing")
        grid = (vertices - np.asarray(plan.origin)) / plan.spacing
        xform = yield from _stage(in_thread(dominant_xform, orbit, plan, grid, spec.smoothing), 0.9, 0.92, "Meshing")
        result = FlameResult(vertices.astype(np.float32), quads, colours.astype(np.float32), xform, 0.0,
                             orbit.unsupported, spec=spec)
    if spec.instances is not None:
        result.instances, result.instance_colours = yield from _stage(
            in_thread(instances_for, flame, spec.instances, orbit.palette), 0.92, 1.0, "Placing instances")
    result.seconds = time.perf_counter() - started
    return result


def instances_for(flame: Flame, spec: InstanceSpec, palette: np.ndarray):
    """`(InstanceSet in Blender's space and sized, palette colours (N, 3))`."""
    source = Flame.from_dict(spec.flame) if spec.flame else flame
    if spec.mode == "TREE":
        raw = holon.tree_instances(source, spec.depth, spec.leaves_only, spec.frames, max(spec.cap, 1) * 4, spec.seed)
    else:
        raw = holon.chaos_instances(source, spec.count, spec.depth, spec.seed, spec.frames)
    sized = raw.sized(spec.size, spec.falloff, spec.min_size, spec.cap)
    mirror = TO_BLENDER                                     # y down the screen → Blender's y up, as for the points
    out = holon.InstanceSet(sized.positions @ mirror.T, mirror @ sized.rotations @ mirror, sized.scales, sized.colour,
                            sized.xform)
    colours = palette[np.clip((out.colour * 255.0 + 0.5).astype(np.int64), 0, 255)] if len(out) else np.zeros((0, 3))
    return out, colours


__all__ = ["FlameSpec", "FlameResult", "InstanceSpec", "build", "instances_for", "POINTS", "MESH", "Step"]
