# SPDX-License-Identifier: MIT
"""A GPU sampler outside Blender: the probe shaders (`core/glsl.py`) through moderngl on any OpenGL 3.3 context
(a desktop driver, or Mesa's llvmpipe through EGL). The same interface as the add-on's samplers, so the build
pipeline runs unchanged; the development tests use it too. moderngl is optional: `context()` is None without it."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from ..core import glsl
from ..core.cpu_eval import sanitize
from ..core.grid import GridPlan
from ..core.samples import Samples
from ..jobs.steps import GpuTurn

try:
    import moderngl
except ImportError:          # optional: only the --gpu / fragment paths need it
    moderngl = None

TYPES = {"VEC3": "vec3", "FLOAT": "float", "INT": "int"}
PIXEL_BUDGET = 1 << 20
POINTS_WIDTH = 1024
VERTEX = "#version 330\nin vec2 pos;\nvoid main() { gl_Position = vec4(pos, 0.0, 1.0); }"


def context():
    """A standalone OpenGL 3.3 context, or None (no moderngl, no driver)."""
    if moderngl is None:
        return None
    for backend in ("egl", None):
        try:
            options = {"backend": backend} if backend else {}
            return moderngl.create_standalone_context(**options)
        except Exception:    # noqa: BLE001 - no display / no EGL: try the next backend
            continue
    return None


def fragment_source(source: glsl.KernelSource, mode: str = "grid") -> str:
    if mode == "grid":
        inputs = "\n".join(f"uniform {TYPES[t]} {n};" for t, n in glsl.PROBE_CONSTANTS)
    else:
        inputs = f"uniform sampler2D {glsl.POINTS_SAMPLER};"
    main = glsl.PROBE_MAIN if mode == "grid" else glsl.POINTS_MAIN
    return (f"#version 330\n{source.typedef}\nlayout(std140) uniform IteronBlock {{ {glsl.STRUCT} {glsl.UNIFORM}; }};\n"
            f"{inputs}\nout vec4 fragColor;\n{source.kernel}\n{main}")


class GlSampler:
    name = "GPU"

    def __init__(self, ctx):
        self.ctx = ctx
        self._programs: dict[tuple, Any] = {}
        self._quad = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4").tobytes())

    def program(self, entry, values, mode: str):
        key = (entry.id, entry.version, entry.static_key(values), mode)
        if key not in self._programs:
            source = glsl.kernel_source(entry, values)
            program = self.ctx.program(vertex_shader=VERTEX, fragment_shader=fragment_source(source, mode))
            program["IteronBlock"].binding = 0
            self._programs[key] = (program, self.ctx.vertex_array(program, [(self._quad, "2f", "pos")]))
        return self._programs[key]

    def _draw(self, vao, entry, values, width: int, height: int) -> np.ndarray:
        block = self.ctx.buffer(glsl.pack(entry, values).tobytes())
        block.bind_to_uniform_block(0)
        target = self.ctx.framebuffer(color_attachments=[self.ctx.texture((width, height), 4, dtype="f4")])
        target.use()
        vao.render(moderngl.TRIANGLE_STRIP)
        pixels = np.frombuffer(target.read(components=4, dtype="f4"), dtype=np.float32).reshape(height, width, 4)
        target.color_attachments[0].release()
        target.release()
        block.release()
        return pixels

    def sample(self, entry, values: dict[str, Any], plan: GridPlan):
        nx, ny, nz = plan.shape
        program, vao = self.program(entry, values, "grid")
        k = int(max(1, min(nz, self.ctx.info["GL_MAX_TEXTURE_SIZE"] // ny, PIXEL_BUDGET // (nx * ny))))
        out = Samples.empty(plan.shape)
        for first in range(0, nz, k):
            count = min(k, nz - first)
            for name, value in (("probe_origin", tuple(plan.origin)), ("probe_spacing", plan.spacing),
                                ("probe_res_y", ny), ("probe_first", first)):
                if name in program:
                    program[name].value = value
            pixels = self._draw(vao, entry, values, nx, ny * count)
            out.store(first, sanitize(pixels.reshape(count, ny, nx, 4).transpose(2, 1, 0, 3).copy()))
            yield GpuTurn((first + count) / nz)
        return out

    def evaluate(self, entry, values: dict[str, Any], points: np.ndarray):
        program, vao = self.program(entry, values, "points")
        out = np.empty((len(points), 4), dtype=np.float32)
        rows = max(1, PIXEL_BUDGET // POINTS_WIDTH)
        for start in range(0, len(points), POINTS_WIDTH * rows):
            chunk = points[start:start + POINTS_WIDTH * rows]
            height = math.ceil(len(chunk) / POINTS_WIDTH)
            texels = np.zeros((POINTS_WIDTH * height, 4), dtype=np.float32)
            texels[:len(chunk), :3] = chunk
            texture = self.ctx.texture((POINTS_WIDTH, height), 4, texels.tobytes(), dtype="f4")
            texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
            texture.use(0)
            if glsl.POINTS_SAMPLER in program:
                program[glsl.POINTS_SAMPLER].value = 0
            pixels = self._draw(vao, entry, values, POINTS_WIDTH, height)
            out[start:start + len(chunk)] = pixels.reshape(-1, 4)[:len(chunk)]
            texture.release()
            yield GpuTurn((start + len(chunk)) / len(points))
        return sanitize(out)
