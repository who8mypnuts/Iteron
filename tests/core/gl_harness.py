# SPDX-License-Identifier: MIT
"""Run Iteron's probe shader outside Blender (moderngl on any OpenGL 3.3 context, e.g. Mesa's llvmpipe), to check
the traced GLSL compiles and agrees with numpy. Development only; the add-on uses Blender's `gpu` module."""

from __future__ import annotations

import numpy as np

from iteron.core import glsl
from iteron.core.grid import GridPlan

try:
    import moderngl
except ImportError:          # the tests skip when moderngl is missing
    moderngl = None

_TYPES = {"VEC3": "vec3", "FLOAT": "float", "INT": "int"}


def context():
    if moderngl is None:
        return None
    for backend in ("egl", None):
        try:
            return moderngl.create_standalone_context(backend=backend) if backend else moderngl.create_standalone_context()
        except Exception:    # noqa: BLE001 - no display / no EGL: try the next backend
            continue
    return None


def fragment_source(source: glsl.KernelSource) -> str:
    constants = "\n".join(f"uniform {_TYPES[t]} {n};" for t, n in glsl.PROBE_CONSTANTS)
    return (f"#version 330\n{source.typedef}\nlayout(std140) uniform IteronBlock {{ {glsl.STRUCT} {glsl.UNIFORM}; }};\n"
            f"{constants}\nout vec4 fragColor;\n{source.kernel}\n{glsl.PROBE_MAIN}")


def sample(ctx, entry, values, plan: GridPlan) -> np.ndarray:
    """`(nx, ny, nz, 4)` samples of the whole plan in one draw."""
    source = glsl.kernel_source(entry, values)
    program = ctx.program(vertex_shader="#version 330\nin vec2 pos;\nvoid main() { gl_Position = vec4(pos, 0.0, 1.0); }",
                          fragment_shader=fragment_source(source))
    nx, ny, nz = plan.shape
    block = ctx.buffer(glsl.pack(entry, values).tobytes())
    program["IteronBlock"].binding = 0
    block.bind_to_uniform_block(0)
    for name, value in (("probe_origin", plan.origin), ("probe_spacing", plan.spacing), ("probe_res_y", ny),
                        ("probe_first", 0)):
        if name in program:
            program[name].value = value
    target = ctx.framebuffer(color_attachments=[ctx.texture((nx, ny * nz), 4, dtype="f4")])
    quad = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4").tobytes())
    vao = ctx.vertex_array(program, [(quad, "2f", "pos")])
    target.use()
    vao.render(moderngl.TRIANGLE_STRIP)
    data = np.frombuffer(target.read(components=4, dtype="f4"), dtype=np.float32).reshape(nz, ny, nx, 4)
    return data.transpose(2, 1, 0, 3).copy()
