# SPDX-License-Identifier: MIT
"""Run Iteron's probe shaders outside Blender for the tests: the command line's moderngl sampler
(`iteron/cli/gl_sampler.py`), here returning all four kernel channels at every voxel of a grid."""

from __future__ import annotations

import numpy as np

from iteron.cli.gl_sampler import GlSampler, context
from iteron.core.grid import GridPlan
from iteron.jobs.steps import run_to_end

_SAMPLERS: dict[int, GlSampler] = {}


def sample(ctx, entry, values, plan: GridPlan) -> np.ndarray:
    """`(nx, ny, nz, 4)` kernel output at the plan's voxels."""
    sampler = _SAMPLERS.setdefault(id(ctx), GlSampler(ctx))
    points = plan.slab_points(0, plan.shape[2])
    return run_to_end(sampler.evaluate(entry, values, points)).reshape(plan.shape + (4,))


__all__ = ["context", "sample"]
