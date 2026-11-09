# SPDX-License-Identifier: MIT
"""Blender's `gpu` module samples the same field as numpy. Needs a GPU context: in background mode one exists only
after something (an EEVEE render) creates it, which this module does; skipped where that fails."""

import numpy as np
import pytest

import bpy
import iteron.formulas  # noqa: F401
from iteron.core import cpu_eval
from iteron.core.formula import REGISTRY
from iteron.core.grid import cube_plan
from iteron.jobs.steps import run_to_end


@pytest.fixture
def gpu_sampler(gpu_context):
    return gpu_context.GpuSampler()


@pytest.mark.parametrize("fid", list(REGISTRY))
def test_gpu_sampler_matches_cpu(gpu_sampler, fid):
    entry = REGISTRY[fid]
    values = entry.values()
    plan = cube_plan((0.0, 0.0, 0.0), entry.bounds, 24)
    gpu = run_to_end(gpu_sampler.sample(entry, values, plan))
    cpu = cpu_eval.evaluate(entry, values, plan.slab_points(0, plan.shape[2])).reshape(plan.shape + (4,))
    near = np.minimum(np.abs(cpu[..., 0]), np.abs(gpu.distance)) < 4 * plan.spacing
    close = np.abs(cpu[..., 0] - gpu.distance) <= 1e-3 * plan.spacing + 1e-3 * np.abs(cpu[..., 0])
    assert close[near].mean() > 0.97
    assert (np.sign(cpu[..., 0]) == np.sign(gpu.distance)).mean() > 0.98


def test_gpu_build_through_the_add_on(gpu_sampler):
    bpy.ops.iteron.add_fractal(formula="mandelbulb")
    obj = bpy.context.active_object
    assert obj.iteron.built_device == "GPU" and obj.iteron.built_faces > 1000 and not obj.iteron.message
