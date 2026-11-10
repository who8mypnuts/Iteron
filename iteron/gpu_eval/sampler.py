# SPDX-License-Identifier: MIT
"""The GPU sampler: draw a probe shader into a float offscreen target and read the pixels back.

`sample` covers a voxel grid: each pixel is one voxel, and a slab of `k` z-slices is drawn as `k` rows of `ny` pixels
stacked vertically, so one draw covers many slices. `evaluate` covers arbitrary points (vertex refinement, normals,
exact colours), read from a float texture, one point per pixel. Draws are kept to a pixel budget so a slow formula
never trips the driver's watchdog. Before every draw the sampler yields a `GpuTurn`: the scheduler then advances it
from a 3D viewport draw callback, where Blender guarantees a GPU context on every backend.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Generator

import gpu
import numpy as np

from ..core import glsl
from ..core.cpu_eval import sanitize
from ..core.formula import Formula
from ..core.grid import GridPlan
from ..core.samples import Samples
from ..jobs.steps import GpuTurn
from . import shaders

PIXEL_BUDGET = 1 << 20      # voxels or points per draw
POINTS_WIDTH = 1024         # texture width for point batches


class GpuSampler:
    name = "GPU"

    def sample(self, entry: Formula, values: dict[str, Any], plan: GridPlan) -> Generator[GpuTurn, None, Samples]:
        yield GpuTurn(0.0)
        nx, ny, nz = plan.shape
        limit = gpu.capabilities.max_texture_size_get()
        if nx > limit:
            raise RuntimeError(f"resolution {nx} exceeds the GPU's texture size ({limit})")
        k = int(max(1, min(nz, limit // ny, PIXEL_BUDGET // (nx * ny))))
        shader, batch = shaders.probe(entry, values, "grid")
        block = shaders.uniform_block(entry, values)
        out = Samples.empty(plan.shape)
        offscreen = gpu.types.GPUOffScreen(nx, ny * k, format="RGBA32F")
        try:
            for first in range(0, nz, k):
                count = min(k, nz - first)

                def uniforms(first=first):
                    shader.uniform_float("probe_origin", plan.origin)
                    shader.uniform_float("probe_spacing", plan.spacing)
                    shader.uniform_int("probe_res_y", ny)
                    shader.uniform_int("probe_first", first)

                pixels = _draw(offscreen, shader, batch, block, uniforms, nx, ny * count)
                out.store(first, sanitize(pixels.reshape(count, ny, nx, 4).transpose(2, 1, 0, 3).copy()))
                if first + count < nz:
                    yield GpuTurn((first + count) / nz)
        finally:
            offscreen.free()
        return out

    def evaluate(self, entry: Formula, values: dict[str, Any], points: np.ndarray) -> Generator[GpuTurn, None, np.ndarray]:
        """`(M, 4)` kernel output at `(M, 3)` points."""
        yield GpuTurn(0.0)
        shader, batch = shaders.probe(entry, values, "points")
        block = shaders.uniform_block(entry, values)
        out = np.empty((len(points), 4), dtype=np.float32)
        rows = max(1, PIXEL_BUDGET // POINTS_WIDTH)
        offscreen = gpu.types.GPUOffScreen(POINTS_WIDTH, rows, format="RGBA32F")
        try:
            for start in range(0, len(points), POINTS_WIDTH * rows):
                chunk = points[start:start + POINTS_WIDTH * rows]
                height = math.ceil(len(chunk) / POINTS_WIDTH)
                texels = np.zeros((POINTS_WIDTH * height, 4), dtype=np.float32)
                texels[:len(chunk), :3] = chunk
                texture = gpu.types.GPUTexture((POINTS_WIDTH, height), format="RGBA32F",
                                               data=shaders.float_buffer(texels))
                pixels = _draw(offscreen, shader, batch, block,
                               lambda: shader.uniform_sampler(glsl.POINTS_SAMPLER, texture), POINTS_WIDTH, height)
                out[start:start + len(chunk)] = pixels.reshape(-1, 4)[:len(chunk)]
                if start + len(chunk) < len(points):
                    yield GpuTurn((start + len(chunk)) / len(points))
        finally:
            offscreen.free()
        return sanitize(out)


def _draw(offscreen, shader, batch, block, uniforms: Callable[[], None], width: int, height: int) -> np.ndarray:
    """Draw the probe over `width × height` pixels of `offscreen`; the pixels as `(height, width, 4)` float32."""
    flat = gpu.types.Buffer("FLOAT", width * height * 4)
    saved = _save_state()
    with offscreen.bind():
        framebuffer = gpu.state.active_framebuffer_get()
        # the state is whatever was last drawn (viewport, EEVEE): set everything the probe relies on
        gpu.state.depth_test_set("NONE")
        gpu.state.depth_mask_set(False)
        gpu.state.blend_set("NONE")
        gpu.state.face_culling_set("NONE")
        gpu.state.viewport_set(0, 0, width, height)
        shader.bind()
        shader.uniform_block(glsl.UNIFORM, block)
        uniforms()
        batch.draw(shader)
        # a flat Buffer: the shaped one Blender returns exposes reversed strides to numpy
        framebuffer.read_color(0, 0, width, height, 4, 0, "FLOAT", data=flat)
    _restore_state(saved)
    return np.asarray(flat, dtype=np.float32).reshape(height, width, 4)


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
