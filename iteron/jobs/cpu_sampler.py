# SPDX-License-Identifier: MIT
"""The CPU sampler: the numpy kernel over a grid (slab by slab) or a list of points, on the worker thread."""

from __future__ import annotations

from typing import Any, Callable, Generator

import numpy as np

from ..core.cpu_eval import CHUNK, evaluate, evaluate_chunked
from ..core.formula import Formula
from ..core.grid import GridPlan
from ..core.samples import Samples
from .steps import Cancel, Cancelled, Waiting, in_thread


class CpuSampler:
    name = "CPU"

    def __init__(self, cancel: Cancel | None = None):
        self.cancel = cancel or Cancel()

    def sample(self, entry: Formula, values: dict[str, Any], plan: GridPlan) -> Generator[Waiting, None, Samples]:
        nx, ny, nz = plan.shape
        step = max(1, CHUNK // (nx * ny))

        def work(progress: list[float]) -> Samples | None:
            samples = Samples.empty(plan.shape)
            for first in range(0, nz, step):
                if self.cancel():
                    return None
                last = min(first + step, nz)
                block = evaluate(entry, values, plan.slab_points(first, last)).reshape(nx, ny, last - first, 4)
                samples.store(first, block)
                progress[0] = last / nz
            return samples

        return (yield from self._run(work))

    def evaluate(self, entry: Formula, values: dict[str, Any], points: np.ndarray) -> Generator[Waiting, None, np.ndarray]:
        """`(M, 4)` kernel output at `(M, 3)` points."""
        def work(progress: list[float]) -> np.ndarray | None:
            return evaluate_chunked(entry, values, points, lambda f: progress.__setitem__(0, f), self.cancel)

        return (yield from self._run(work))

    def _run(self, work: Callable[[list[float]], Any]) -> Generator[Waiting, None, Any]:
        progress = [0.0]
        try:
            result = yield from in_thread(work, progress, progress=progress)
        except GeneratorExit:
            self.cancel.set()            # the job was closed early: stop the worker too
            raise
        if result is None:
            raise Cancelled
        return result
