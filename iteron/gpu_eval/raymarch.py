# SPDX-License-Identifier: MIT
"""Drawing the live preview: a formula ray-marched in the viewport with Blender's `gpu` module (see core/raymarch.py
for the shader). Called from the viewport's draw callback, where a GPU context is guaranteed."""

from __future__ import annotations

from typing import Any

import gpu
import numpy as np
from gpu_extras.batch import batch_for_shader

from ..core import glsl, raymarch
from ..core.formula import Formula
from . import shaders

_CACHE: dict[tuple, tuple[Any, Any]] = {}
_RAMPS: dict[tuple, Any] = {}
_SAMPLERS: dict[tuple, tuple[str, ...]] = {}


def shader(entry: Formula, values: dict[str, Any]):
    """`(shader, batch)` for `entry`'s ray-march, cached like the probes."""
    key = (entry.id, entry.version, entry.static_key(values), "raymarch")
    if key not in _CACHE:
        source = glsl.kernel_source(entry, values)
        info = gpu.types.GPUShaderCreateInfo()
        info.vertex_in(0, "VEC3", "pos")
        info.typedef_source(source.typedef + "\n" + raymarch.TYPEDEF)
        info.uniform_buf(0, glsl.STRUCT, glsl.UNIFORM)
        info.uniform_buf(1, raymarch.STRUCT, raymarch.UNIFORM)
        info.sampler(0, "FLOAT_2D", raymarch.RAMP)
        shaders.declare_samplers(info, source)
        info.fragment_out(0, "VEC4", "fragColor")
        if hasattr(info, "depth_write"):          # Blender 5: declare it (4.2's OpenGL writes depth regardless)
            info.depth_write("ANY")
        info.vertex_source(raymarch.VERTEX)
        info.fragment_source(source.kernel + raymarch.FRAGMENT)
        compiled = gpu.shader.create_from_info(info)
        _CACHE[key] = (compiled, batch_for_shader(compiled, "TRIS", {"pos": raymarch.CUBE}))
        _SAMPLERS[key] = source.samplers
    return _CACHE[key]


def ramp_texture(lut: np.ndarray):
    """A 256 × 1 float texture of the ramp's colours, cached by content."""
    key = (lut.shape, hash(lut.tobytes()))
    if key not in _RAMPS:
        if len(_RAMPS) > 32:
            _RAMPS.clear()
        _RAMPS[key] = gpu.types.GPUTexture((lut.shape[0], 1), format="RGBA32F", data=shaders.float_buffer(lut))
    return _RAMPS[key]


def draw(entry: Formula, values: dict[str, Any], mvp, viewport, box, lut: np.ndarray, channel: str,
         channel_range, detail: float = raymarch.DETAIL, steps: int = raymarch.MAX_STEPS, textures=None) -> None:
    """Draw the ray-marched fractal into the bound framebuffer (depth tested and written). `textures`: a
    fragment's, by sampler name."""
    compiled, batch = shader(entry, values)
    samplers = _SAMPLERS[(entry.id, entry.version, entry.static_key(values), "raymarch")]
    view = raymarch.view_block(np.asarray(mvp), viewport, box[0], box[1], channel, channel_range[0], channel_range[1],
                               detail, steps)
    params = shaders.uniform_block(entry, values)
    view_buffer = gpu.types.GPUUniformBuf(shaders.float_buffer(view))
    saved = (gpu.state.depth_test_get(), gpu.state.depth_mask_get(), gpu.state.blend_get())
    gpu.state.depth_test_set("LESS_EQUAL")
    gpu.state.depth_mask_set(True)
    gpu.state.blend_set("NONE")
    gpu.state.face_culling_set("FRONT")
    compiled.bind()
    compiled.uniform_block(glsl.UNIFORM, params)
    compiled.uniform_block(raymarch.UNIFORM, view_buffer)
    compiled.uniform_sampler(raymarch.RAMP, ramp_texture(lut))
    shaders.bind_samplers(compiled, samplers, textures or {})
    batch.draw(compiled)
    gpu.state.face_culling_set("NONE")
    gpu.state.depth_test_set(saved[0])
    gpu.state.depth_mask_set(saved[1])
    gpu.state.blend_set(saved[2])


def clear_cache() -> None:
    _CACHE.clear()
    _RAMPS.clear()
    _SAMPLERS.clear()
