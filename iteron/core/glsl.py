# SPDX-License-Identifier: MIT
"""Shader sources for a formula: the traced kernel, the uniform block that feeds it, and the probe `main`.

The pieces are plain strings so any host can assemble them — Blender's `GPUShaderCreateInfo` in the add-on, a
moderngl program in the development tests. The block is `struct IteronParams { vec4 v[N]; }`: every runtime
parameter sits at a fixed (slot, component), which `params.layout` decides and `pack` fills.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .formula import UNIFORM, Formula, symbolic_values
from .params import layout, numeric, slot_count
from .runners import kernel
from .trace import S, Tracer, code, tracing

STRUCT = "IteronParams"

# One voxel per pixel: x → i, y → (slice row, j); rows of `probe_res_y` pixels are consecutive z slices.
PROBE_MAIN = """
void main() {
    int py = int(gl_FragCoord.y);
    int row = py / probe_res_y;
    int j = py - row * probe_res_y;
    vec3 p = probe_origin + vec3(float(int(gl_FragCoord.x)), float(j), float(probe_first + row)) * probe_spacing;
    fragColor = iteron_kernel(p);
}
"""
PROBE_CONSTANTS = (("VEC3", "probe_origin"), ("FLOAT", "probe_spacing"), ("INT", "probe_res_y"), ("INT", "probe_first"))

# Arbitrary points: one per pixel, read from an RGBA32F texture (refinement, normals, exact vertex colours).
POINTS_MAIN = """
void main() {
    fragColor = iteron_kernel(texelFetch(probe_points, ivec2(gl_FragCoord.xy), 0).xyz);
}
"""
POINTS_SAMPLER = "probe_points"


@dataclass(frozen=True)
class KernelSource:
    typedef: str      # the struct declaration
    kernel: str       # `vec4 iteron_kernel(vec3 pos)`
    slots: int        # vec4s in the uniform block


def kernel_source(entry: Formula, values: dict[str, Any]) -> KernelSource:
    """Trace `entry` (with its static parameters taken from `values`) into GLSL."""
    tracer = Tracer()
    with tracing(tracer):
        channels = kernel(entry, S("vec3", "pos"), symbolic_values(entry, values))
        result = ", ".join(code(c) for c in channels)
    body = f"vec4 iteron_kernel(vec3 pos) {{\n{tracer.source()}\n    return vec4({result});\n}}\n"
    slots = slot_count(entry.params)
    return KernelSource(f"struct {STRUCT} {{ vec4 v[{slots}]; }};", body, slots)


def pack(entry: Formula, values: dict[str, Any]) -> np.ndarray:
    """The uniform block contents, `(slots * 4,)` float32, for `values`."""
    data = np.zeros(slot_count(entry.params) * 4, dtype=np.float32)
    params = {p.name: p for p in entry.params}
    for name, (slot, lane) in layout(entry.params).items():
        floats = numeric(params[name], values[name])
        data[slot * 4 + lane: slot * 4 + lane + len(floats)] = floats
    return data


__all__ = ["KernelSource", "kernel_source", "pack", "PROBE_MAIN", "PROBE_CONSTANTS", "POINTS_MAIN", "POINTS_SAMPLER",
           "STRUCT", "UNIFORM"]
