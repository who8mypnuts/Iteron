# SPDX-License-Identifier: MIT
"""The vocabulary formulas are written in: GLSL-named functions that work on either backend.

With numpy values (`NVec`, arrays, numbers) they compute; with symbolic values (`trace.S`) they record GLSL.
One definition therefore serves the CPU fallback and the GPU shader, and the parity tests keep them equal.
Conditions that depend on the point use `select`; runtime-bounded iteration uses `loop`.
"""

from __future__ import annotations

import builtins
import math

import numpy as np

from . import vec
from .trace import S, TraceError, active, code, is_tracing, promote, type_of, widest


def _symbolic(*values) -> bool:
    return is_tracing() or any(isinstance(v, S) for v in values)


def _call(name: str, values, result: str | None = None, same_type: bool = False) -> S:
    """Emit `name(args)`; `same_type` splats scalars where GLSL requires matching operand types."""
    type_ = widest(*values)
    args = [promote(v, type_) if same_type else code(v) for v in values]
    return active().value(result or type_, f"{name}({', '.join(args)})")


def _elementwise(glsl: str, fn, same_type: bool = False):
    def op(*values):
        if _symbolic(*values):
            return _call(glsl, values, same_type=same_type)
        return vec.lift(fn, *values)
    op.__name__ = glsl
    op.__doc__ = f"GLSL `{glsl}`, elementwise."
    return op


# --- elementwise functions ----------------------------------------------------------------------------------------
abs = _elementwise("abs", np.abs)                           # noqa: A001 - GLSL names on purpose
sign = _elementwise("sign", np.sign)
floor = _elementwise("floor", np.floor)
fract = _elementwise("fract", lambda x: x - np.floor(x))
sqrt = _elementwise("sqrt", np.sqrt)
exp = _elementwise("exp", np.exp)
log = _elementwise("log", np.log)
sin = _elementwise("sin", np.sin)
cos = _elementwise("cos", np.cos)
tan = _elementwise("tan", np.tan)
asin = _elementwise("asin", np.arcsin)
acos = _elementwise("acos", np.arccos)
min = _elementwise("min", np.minimum)                       # noqa: A001
max = _elementwise("max", np.maximum)                       # noqa: A001
pow = _elementwise("pow", np.power, same_type=True)        # noqa: A001
mod = _elementwise("mod", lambda x, y: x - y * np.floor(x / y))
atan2 = _elementwise("atan", np.arctan2, same_type=True)   # atan2(y, x) → GLSL atan(y, x)
clamp = _elementwise("clamp", lambda x, lo, hi: np.minimum(np.maximum(x, lo), hi))
mix = _elementwise("mix", lambda a, b, t: a + (b - a) * t)


def radians(degrees):
    return degrees * (math.pi / 180.0)


# --- vectors --------------------------------------------------------------------------------------------------------
def _construct(type_: str, components):
    if _symbolic(*components):
        return active().value(type_, f"{type_}({', '.join(code(c) for c in components)})")
    return vec.make(*components)


def vec3(x, y=None, z=None):
    """`vec3(x, y, z)`, or `vec3(s)` for a splat."""
    return _construct("vec3", (x, x, x) if y is None else (x, y, z))


def vec4(x, y=None, z=None, w=None):
    return _construct("vec4", (x, x, x, x) if y is None else (x, y, z, w))


def dot(a, b):
    if _symbolic(a, b):
        return _call("dot", (a, b), result="float")
    return np.sum(vec.lanes(a) * vec.lanes(b), axis=0)


def length(v):
    if _symbolic(v):
        return _call("length", (v,), result="float")
    return np.sqrt(dot(v, v))


def normalize(v):
    if _symbolic(v):
        return _call("normalize", (v,))
    return v / length(v)


def cross(a, b):
    if _symbolic(a, b):
        return _call("cross", (a, b))
    return vec3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)


# --- choice and iteration -------------------------------------------------------------------------------------------
def select(condition, a, b):
    """`condition ? a : b`, per point. `condition` may be a Python bool (a static choice)."""
    if isinstance(condition, bool):
        return a if condition else b
    if _symbolic(condition, a, b):
        type_ = widest(a, b)
        return active().value(type_, f"({code(condition)} ? {promote(a, type_)} : {promote(b, type_)})")
    return vec.lift(np.where, condition, a, b)


def loop(count, max_count: int, state: tuple, body, until=None):
    """Run `state = body(i, state)` up to `count` times (never more than `max_count`, the GLSL bound), stopping a
    point early once `until(state)` is true for it. Returns `(state, n)`: the final state and the iterations run."""
    if _symbolic(count, *state):
        return _loop_glsl(count, max_count, tuple(state), body, until)
    state, n, alive = tuple(state), 0.0, None
    for i in range(builtins.min(int(count), max_count)):
        new = body(float(i), state)
        state = tuple(new) if alive is None else tuple(select(alive, a, b) for a, b in zip(new, state))
        n = n + (1.0 if alive is None else alive.astype(np.float64))
        if until is not None:
            done = np.asarray(until(state))
            alive = ~done if alive is None else alive & ~done
            if not alive.any():
                break
    return state, n


def _loop_glsl(count, max_count, state, body, until):
    tracer = active()
    types = [type_of(s) for s in state]
    names = [tracer.name("l") for _ in state]
    for name, type_, value in zip(names, types, state):
        tracer.line(f"{type_} {name} = {code(value)};")
    counter, index = tracer.name("n"), tracer.name("i")
    tracer.line(f"float {counter} = 0.0;")
    tracer.open(f"for (int {index} = 0; {index} < {int(max_count)}; {index}++)")
    tracer.line(f"if ({index} >= int({code(count)})) break;")
    current = tuple(S(t, n) for t, n in zip(types, names))
    new = tuple(body(S("float", f"float({index})"), current))
    # the update is simultaneous: a value that *is* a loop variable (state passed through) is copied first, or an
    # earlier assignment would overwrite it before it is read
    settled = []
    for type_, value in zip(types, new):
        if type_of(value) != type_:
            raise TraceError(f"loop state changed type from {type_} to {type_of(value)}")
        settled.append(tracer.value(type_, code(value)) if code(value) in names else value)
    for name, value in zip(names, settled):
        tracer.line(f"{name} = {code(value)};")
    tracer.line(f"{counter} += 1.0;")
    if until is not None:
        tracer.line(f"if ({code(until(current))}) break;")
    tracer.close()
    return current, S("float", counter)



# --- geometry helpers ------------------------------------------------------------------------------------------------
def rotation_xyz(degrees):
    """Rotation (X, then Y, then Z) from Euler angles in degrees, as three row vectors for `mat_mul`."""
    a = radians(degrees)
    cx, sx, cy, sy, cz, sz = cos(a.x), sin(a.x), cos(a.y), sin(a.y), cos(a.z), sin(a.z)
    return (vec3(cy * cz, sx * sy * cz - cx * sz, cx * sy * cz + sx * sz),
            vec3(cy * sz, sx * sy * sz + cx * cz, cx * sy * sz - sx * cz),
            vec3(-sy, sx * cy, cx * cy))


def mat_mul(rows, v):
    return vec3(dot(rows[0], v), dot(rows[1], v), dot(rows[2], v))


def sd_box(p, half_size):
    """Signed distance to an axis-aligned box (Inigo Quilez, MIT)."""
    q = abs(p) - half_size
    outside = length(max(q, 0.0))
    inside = min(max(q.x, max(q.y, q.z)), 0.0)
    return outside + inside


__all__ = ["abs", "acos", "asin", "atan2", "clamp", "cos", "cross", "dot", "exp", "floor", "fract", "length", "log",
           "loop", "mat_mul", "max", "min", "mix", "mod", "normalize", "pow", "radians", "rotation_xyz", "sd_box",
           "select", "sign", "sin", "sqrt", "tan", "vec3", "vec4"]
