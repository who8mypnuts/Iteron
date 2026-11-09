# SPDX-License-Identifier: MIT
"""The GPU sampler: draw the probe shader into a float offscreen target, a slab of z-slices at a time.

Each pixel is one voxel; a slab of `k` slices is drawn as `k` rows of `ny` pixels stacked vertically, so one draw
and one read-back cover many slices. Slabs are kept to a pixel budget so a slow formula never trips the driver's
watchdog. Before every slab (the first included) the sampler yields a `GpuTurn`: the scheduler then advances it from
a 3D viewport draw callback, where Blender guarantees a GPU context on every backend.
"""

from __future__ import annotations

from typing import Any, Generator

import gpu
import numpy as np

from ..core import glsl
from ..core.cpu_eval import sanitize
from ..core.formula import Formula
from ..core.grid import GridPlan
from ..core.samples import Samples
from ..jobs.steps import GpuTurn
from . import shaders

PIXEL_BUDGET = 1 << 20      # voxels per draw


class GpuSampler:
    name = "GPU"

    def sample(self, entry: Formula, values: dict[str, Any], plan: GridPlan) -> Generator[GpuTurn, None, Samples]:
        yield GpuTurn(0.0)
        nx, ny, nz = plan.shape
        limit = gpu.capabilities.max_texture_size_get()
        if nx > limit:
            raise RuntimeError(f"resolution {nx} exceeds the GPU's texture size ({limit})")
        k = int(max(1, min(nz, limit // ny, PIXEL_BUDGET // (nx * ny))))
        shader, batch, _slots = shaders.probe(entry, values)
        block = shaders.uniform_block(entry, values)
        out = Samples.empty(plan.shape)
        offscreen = gpu.types.GPUOffScreen(nx, ny * k, format="RGBA32F")
        try:
            for first in range(0, nz, k):
                count = min(k, nz - first)
                out.store(first, sanitize(self._slab(offscreen, shader, batch, block, plan, first, count)))
                if first + count < nz:
                    yield GpuTurn((first + count) / nz)
        finally:
            offscreen.free()
        return out

    @staticmethod
    def _slab(offscreen, shader, batch, block, plan: GridPlan, first: int, count: int) -> np.ndarray:
        nx, ny, _nz = plan.shape
        height = ny * count
        flat = gpu.types.Buffer("FLOAT", nx * height * 4)
        saved = _save_state()
        with offscreen.bind():
            framebuffer = gpu.state.active_framebuffer_get()
            # the state is whatever was last drawn (viewport, EEVEE): set everything the probe relies on
            gpu.state.depth_test_set("NONE")
            gpu.state.depth_mask_set(False)
            gpu.state.blend_set("NONE")
            gpu.state.face_culling_set("NONE")
            gpu.state.viewport_set(0, 0, nx, height)
            shader.bind()
            shader.uniform_block(glsl.UNIFORM, block)
            shader.uniform_float("probe_origin", plan.origin)
            shader.uniform_float("probe_spacing", plan.spacing)
            shader.uniform_int("probe_res_y", ny)
            shader.uniform_int("probe_first", first)
            batch.draw(shader)
            # a flat Buffer: the shaped one Blender returns exposes reversed strides to numpy
            framebuffer.read_color(0, 0, nx, height, 4, 0, "FLOAT", data=flat)
        _restore_state(saved)
        pixels = np.asarray(flat, dtype=np.float32).reshape(count, ny, nx, 4)
        return pixels.transpose(2, 1, 0, 3).copy()


def _save_state():
    return (gpu.state.viewport_get(), gpu.state.blend_get(), gpu.state.depth_test_get(), gpu.state.depth_mask_get())


def _restore_state(saved) -> None:
    viewport, blend, depth_test, depth_mask = saved
    gpu.state.viewport_set(*viewport)
    gpu.state.blend_set(blend)
    gpu.state.depth_test_set(depth_test)
    gpu.state.depth_mask_set(depth_mask)


def available() -> bool:
    """Whether the GPU path can run: Blender has a GPU backend and, in background mode (where only scripts run),
    something has already initialised a GPU context."""
    import bpy
    if bpy.app.background:
        try:
            gpu.types.GPUOffScreen(4, 4, format="RGBA32F").free()
            return True
        except Exception:       # noqa: BLE001 - "not available in background mode", or a broken driver
            return False
    return gpu.platform.backend_type_get() in {"OPENGL", "METAL", "VULKAN"}
