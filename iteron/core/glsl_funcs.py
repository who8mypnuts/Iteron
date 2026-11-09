# SPDX-License-Identifier: MIT
"""The scalar function vocabulary `core.ops` traces: one name, a GLSL meaning and a Python meaning, together.

Most names are native GLSL functions, so nothing needs to be added to a shader for them. A few have no GLSL
equivalent (`select`, `atan2`) and get one small helper each in `PRELUDE`, inserted once per generated shader.
`PY_NAMESPACE` gives `tests/core` the same names as plain Python callables, so it can `eval()` the exact GLSL text
a formula produced and compare it with the numpy path — this project's stand-in for compiling on a real GPU
(see PLAN.md §11 on the sandbox's limits).
"""

from __future__ import annotations

import math

PRELUDE = """
float select(bool cond, float a, float b) { return cond ? a : b; }
float atan2(float y, float x) { return atan(y, x); }
"""


def _sign(x: float) -> float:
    return 0.0 if x == 0.0 else math.copysign(1.0, x)


def _mod(x: float, y: float) -> float:
    return x - y * math.floor(x / y) if y != 0.0 else 0.0


def _mix(a: float, b: float, t: float) -> float:
    return a * (1.0 - t) + b * t


def _clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


PY_NAMESPACE = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "acos": lambda x: math.acos(_clamp(x, -1.0, 1.0)),
    "asin": lambda x: math.asin(_clamp(x, -1.0, 1.0)), "floor": math.floor, "abs": abs, "min": min, "max": max,
    "pow": math.pow, "sign": _sign, "mod": _mod,
    "mix": _mix, "clamp": _clamp, "select": lambda cond, a, b: a if cond else b, "atan2": math.atan2,
}
