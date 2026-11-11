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


MAINS = {"grid": glsl.PROBE_MAIN, "points": glsl.POINTS_MAIN, "color": glsl.COLOR_MAIN}


def probe(entry: Formula, values: dict[str, Any], mode: str = "grid"):
    """`(shader, batch, samplers)` drawing `entry`'s probe over a full-screen quad: "grid" (voxels from the pixel
    position), "points" (positions from a texture) or "color" (a fragment's `baseColor` at such points).
    `samplers` are the kernel's own textures, bound from `glsl.TEXTURE_SLOT`."""
    key = (entry.id, entry.version, entry.static_key(values), mode)
    if key not in _CACHE:
        source = glsl.kernel_source(entry, values)
        info = gpu.types.GPUShaderCreateInfo()
        info.vertex_in(0, "VEC2", "pos")
        constants = glsl.PROBE_CONSTANTS if mode == "grid" else glsl.COLOR_CONSTANTS if mode == "color" else ()
        for type_, name in constants:
            info.push_constant(type_, name)
        if mode != "grid":
            info.sampler(0, "FLOAT_2D", glsl.POINTS_SAMPLER)
        declare_samplers(info, source)
        info.typedef_source(source.typedef)
        info.uniform_buf(0, glsl.STRUCT, glsl.UNIFORM)
        info.fragment_out(0, "VEC4", "fragColor")
        info.vertex_source("void main() { gl_Position = vec4(pos, 0.0, 1.0); }")
        info.fragment_source(source.kernel + MAINS[mode])
        shader = gpu.shader.create_from_info(info)
        _CACHE[key] = (shader, batch_for_shader(shader, "TRI_STRIP", {"pos": _QUAD}), source.samplers)
    return _CACHE[key]


def declare_samplers(info, source: glsl.KernelSource) -> None:
    for slot, name in enumerate(source.samplers, start=glsl.TEXTURE_SLOT):
        info.sampler(slot, "FLOAT_2D", name)


def bind_samplers(shader, samplers: tuple[str, ...], textures: dict) -> None:
    """Bind a kernel's textures (`FragmentError`-like `RuntimeError` when one has no image)."""
    for name in samplers:
        if name not in textures:
            raise RuntimeError(f"no image for the texture {name!r}")
        shader.uniform_sampler(name, textures[name])


def float_buffer(array: np.ndarray):
    """A flat FLOAT `gpu.types.Buffer` from numpy, without a Python list (shaped Buffers get numpy strides wrong)."""
    return gpu.types.Buffer("FLOAT", array.size, np.ascontiguousarray(array, dtype=np.float32).ravel())


def uniform_block(entry: Formula, values: dict[str, Any]):
    return gpu.types.GPUUniformBuf(float_buffer(glsl.pack(entry, values)))


def clear_cache() -> None:
    _CACHE.clear()
