# SPDX-License-Identifier: MIT
"""Probe shaders: a formula's traced kernel compiled with Blender's `GPUShaderCreateInfo`, cached per formula
version and static parameter values."""

from __future__ import annotations

from typing import Any

import gpu
from gpu_extras.batch import batch_for_shader

from ..core import glsl
from ..core.formula import Formula

_CACHE: dict[tuple, tuple[Any, Any, int]] = {}
_QUAD = [(-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0), (1.0, 1.0)]


def probe(entry: Formula, values: dict[str, Any]):
    """`(shader, batch, slots)` drawing `entry`'s probe over a full-screen quad."""
    key = (entry.id, entry.version, entry.static_key(values))
    if key not in _CACHE:
        source = glsl.kernel_source(entry, values)
        info = gpu.types.GPUShaderCreateInfo()
        info.vertex_in(0, "VEC2", "pos")
        for type_, name in glsl.PROBE_CONSTANTS:
            info.push_constant(type_, name)
        info.typedef_source(source.typedef)
        info.uniform_buf(0, glsl.STRUCT, glsl.UNIFORM)
        info.fragment_out(0, "VEC4", "fragColor")
        info.vertex_source("void main() { gl_Position = vec4(pos, 0.0, 1.0); }")
        info.fragment_source(source.kernel + glsl.PROBE_MAIN)
        shader = gpu.shader.create_from_info(info)
        _CACHE[key] = (shader, batch_for_shader(shader, "TRI_STRIP", {"pos": _QUAD}), source.slots)
    return _CACHE[key]


def uniform_block(entry: Formula, values: dict[str, Any]):
    data = glsl.pack(entry, values)
    return gpu.types.GPUUniformBuf(gpu.types.Buffer("FLOAT", len(data), data.tolist()))


def clear_cache() -> None:
    _CACHE.clear()
