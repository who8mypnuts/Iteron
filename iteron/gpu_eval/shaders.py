# SPDX-License-Identifier: MIT
"""Probe shaders: a formula's traced kernel compiled with Blender's `GPUShaderCreateInfo`, cached per formula
version, static parameter values and mode — "grid" (voxels from the pixel position) or "points" (positions read
from a texture)."""

from __future__ import annotations

from typing import Any

import gpu
import numpy as np
from gpu_extras.batch import batch_for_shader

from ..core import glsl
from ..core.formula import Formula

_CACHE: dict[tuple, tuple[Any, Any]] = {}
_QUAD = [(-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0), (1.0, 1.0)]


def probe(entry: Formula, values: dict[str, Any], mode: str = "grid"):
    """`(shader, batch)` drawing `entry`'s probe over a full-screen quad."""
    key = (entry.id, entry.version, entry.static_key(values), mode)
    if key not in _CACHE:
        source = glsl.kernel_source(entry, values)
        info = gpu.types.GPUShaderCreateInfo()
        info.vertex_in(0, "VEC2", "pos")
        if mode == "grid":
            for type_, name in glsl.PROBE_CONSTANTS:
                info.push_constant(type_, name)
        else:
            info.sampler(0, "FLOAT_2D", glsl.POINTS_SAMPLER)
        info.typedef_source(source.typedef)
        info.uniform_buf(0, glsl.STRUCT, glsl.UNIFORM)
        info.fragment_out(0, "VEC4", "fragColor")
        info.vertex_source("void main() { gl_Position = vec4(pos, 0.0, 1.0); }")
        info.fragment_source(source.kernel + (glsl.PROBE_MAIN if mode == "grid" else glsl.POINTS_MAIN))
        shader = gpu.shader.create_from_info(info)
        _CACHE[key] = (shader, batch_for_shader(shader, "TRI_STRIP", {"pos": _QUAD}))
    return _CACHE[key]


def float_buffer(array: np.ndarray):
    """A flat FLOAT `gpu.types.Buffer` from numpy, without a Python list (shaped Buffers get numpy strides wrong)."""
    return gpu.types.Buffer("FLOAT", array.size, np.ascontiguousarray(array, dtype=np.float32).ravel())


def uniform_block(entry: Formula, values: dict[str, Any]):
    return gpu.types.GPUUniformBuf(float_buffer(glsl.pack(entry, values)))


def clear_cache() -> None:
    _CACHE.clear()
