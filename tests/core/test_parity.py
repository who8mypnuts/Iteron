# SPDX-License-Identifier: MIT
"""Every formula gives the same field on the GPU (traced GLSL, float32) as on the CPU (numpy, float64).

Runs on any OpenGL 3.3 context through moderngl (Mesa's llvmpipe is enough). Never inside a Blender process: two
OpenGL stacks in one process crash there, and `tests/blender/test_gpu.py` checks Blender's own `gpu` module instead.
"""

import sys

import numpy as np
import pytest

import iteron.formulas  # noqa: F401
from iteron.core import cpu_eval
from iteron.core.formula import REGISTRY
from iteron.core.grid import cube_plan

from .gl_harness import context, sample

pytestmark = pytest.mark.skipif("bpy" in sys.modules, reason="inside Blender: see tests/blender/test_gpu.py")


@pytest.fixture(scope="module")
def ctx():
    created = context()
    if created is None:
        pytest.skip("no OpenGL 3.3 context (moderngl + EGL/llvmpipe)")
    return created


def _cases():
    for fid, entry in REGISTRY.items():
        for preset in entry.presets:
            yield pytest.param(fid, preset, id=f"{fid}-{preset}")


@pytest.mark.parametrize("fid,preset", list(_cases()))
def test_gpu_matches_cpu(ctx, fid, preset):
    entry = REGISTRY[fid]
    values = entry.values(entry.presets[preset])
    plan = cube_plan((0.0, 0.0, 0.0), entry.bounds, 20)
    gpu = sample(ctx, entry, values, plan)
    cpu = cpu_eval.evaluate(entry, values, plan.slab_points(0, plan.shape[2])).reshape(plan.shape + (4,))
    cpu_eval.sanitize(gpu)
    scale = plan.spacing
    # distance: what matters for meshing is agreement near and inside the surface, to a fraction of a voxel
    near = np.minimum(np.abs(cpu[..., 0]), np.abs(gpu[..., 0])) < 4 * scale
    close = np.abs(cpu[..., 0] - gpu[..., 0]) <= 1e-3 * scale + 1e-3 * np.abs(cpu[..., 0])
    assert close[near].mean() > 0.97, f"distance agrees at only {close[near].mean():.1%} of near-surface voxels"
    assert (np.sign(cpu[..., 0]) == np.sign(gpu[..., 0])).mean() > 0.98
    # colour channels: orbits near and inside the set are chaotic, so float32 drifts from float64 (a visual 2 % is fine)
    for channel in (1, 2, 3):
        agree = np.isclose(cpu[..., channel], gpu[..., channel], rtol=0.02, atol=0.02)
        assert agree.mean() > 0.90, f"channel {channel} agrees at only {agree.mean():.1%}"
