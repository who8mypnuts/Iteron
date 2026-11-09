# SPDX-License-Identifier: MIT
"""The CPU sampler: the numpy kernel over the grid, slab by slab, on the worker thread."""

from __future__ import annotations

from typing import Any, Generator

from ..core.cpu_eval import CHUNK, evaluate
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
        progress = [0.0]

        def work() -> Samples | None:
            samples = Samples.empty(plan.shape)
            for first in range(0, nz, step):
                if self.cancel():
                    return None
                last = min(first + step, nz)
                samples.store(first, evaluate(entry, values, plan.slab_points(first, last)).reshape(nx, ny, last - first, 4))
                progress[0] = last / nz
            return samples

        try:
            result = yield from in_thread(work, progress=progress)
        except GeneratorExit:
            self.cancel.set()            # the job was closed early: stop the worker too
            raise
        if result is None:
            raise Cancelled
        return result
