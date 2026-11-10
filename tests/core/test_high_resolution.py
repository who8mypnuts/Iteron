# SPDX-License-Identifier: MIT
"""Meshing beyond 1024³: blocks the surface can't reach are culled by a probe lattice, so sampling follows the
surface — a small ball in a 2048³ (CPU) or 4096³ (GPU, moderngl) grid samples a handful of its thousands of blocks,
and the mesh is closed and on the ball."""

import sys

import numpy as np
import pytest

from iteron.core import blocks, ops
from iteron.core.formula import DIRECT, GLOBAL, Formula
from iteron.core.grid import cube_plan
from iteron.core.params import Float
from iteron.jobs.cpu_sampler import CpuSampler
from iteron.jobs.pipeline import BuildSpec, build
from iteron.jobs.steps import run_to_end

BALL = Formula(id="test_ball", name="Ball", family="Bulbs", kind=DIRECT, bounds=1.0,
               fn=lambda pos, p: (ops.length(pos) - p.radius, ops.length(pos)),
               params=GLOBAL + (Float("radius", 0.05),))


def _build(resolution: int, sampler):
    spec = BuildSpec(BALL.id, {}, (0.3, 0.0, 0.0), 1.0, False, resolution, 0.5, True, 1, True, 0.0)
    return run_to_end(build(spec, sampler, BALL))


def _check(result, resolution: int, most_blocks: int):
    total = int(np.ceil(resolution / blocks.BLOCK)) ** 3
    sampled, candidates = result.blocks
    assert result.plan.shape == (resolution,) * 3
    assert sampled <= most_blocks < total and sampled <= candidates
    radius = np.linalg.norm(result.vertices, axis=1)
    level = 0.05 + 0.5 * result.plan.spacing
    assert np.abs(radius - level).max() < 0.05 * result.plan.spacing + 1e-6
    edges = np.sort(np.concatenate([result.quads[:, [i, (i + 1) % 4]] for i in range(4)]).astype(np.int64), axis=1)
    _keys, uses = np.unique(edges[:, 0] * len(result.vertices) + edges[:, 1], return_counts=True)
    assert (uses == 2).all()
    expected = 4 * np.pi * (0.05 / result.plan.spacing) ** 2          # ~ one quad per voxel of sphere area
    assert 0.8 * expected < result.faces < 1.6 * expected


def test_a_ball_in_a_2048_grid_samples_only_the_blocks_around_it():
    _check(_build(2048, CpuSampler()), 2048, most_blocks=8)


def test_a_ball_in_a_4096_grid_on_the_gpu():
    if "bpy" in sys.modules:
        pytest.skip("inside Blender (moderngl and Blender's OpenGL don't share a process)")
    from iteron.cli.gl_sampler import GlSampler, context
    ctx = context()
    if ctx is None:
        pytest.skip("no OpenGL 3.3 context (moderngl + EGL/llvmpipe)")
    _check(_build(4096, GlSampler(ctx)), 4096, most_blocks=27)


def test_culling_never_drops_a_block_with_surface():
    """Probes on every block of a 96³ grid of a ball: exactly the blocks the ball's shell crosses survive."""
    plan = cube_plan((0.0, 0.0, 0.0), 1.0, 96)
    values = BALL.values({"radius": 0.5})
    from iteron.core import cpu_eval
    for block in blocks.layout(plan, size=16):
        points, step = blocks.probe_points(plan, block)
        keep = blocks.can_hold_surface(cpu_eval.evaluate(BALL, values, points)[:, 0], step, 0.0, plan.spacing)
        core = plan.to_world(np.argwhere(np.ones(tuple(b - a for a, b in zip(block.start, block.stop)))) +
                             np.array(block.start))
        crossed = np.ptp(np.sign(np.linalg.norm(core, axis=1) - 0.5)) > 0
        assert keep or not crossed
