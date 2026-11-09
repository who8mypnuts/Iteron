# SPDX-License-Identifier: MIT
"""Symbolic values for the GPU path: calling a formula with `S` values records GLSL instead of computing.

Every operation emits one SSA line (`float t12 = t3 * t7;`) into the active `Tracer`. Python control flow over
ordinary values (static parameters, fixed fold counts) simply unrolls; a data-dependent choice must use
`ops.select`, and using a symbolic bool in a Python `if` raises at trace time. Runtime-bounded loops are
`ops.loop`, which the tracer turns into a GLSL `for` with a `break`.
"""

from __future__ import annotations

import math
from contextlib import contextmanager

VEC_TYPES = ("vec2", "vec3", "vec4")
_STACK: list["Tracer"] = []


class TraceError(TypeError):
    """A formula did something the GLSL path cannot express."""


class Tracer:
    """Collects the GLSL statements of one function body."""

    def __init__(self):
        self.lines: list[str] = []
        self.depth = 1
        self.count = 0

    def name(self, prefix: str = "t") -> str:
        self.count += 1
        return f"{prefix}{self.count}"

    def line(self, text: str) -> None:
        self.lines.append("    " * self.depth + text)

    def value(self, type_: str, expr: str) -> "S":
        name = self.name()
        self.line(f"{type_} {name} = {expr};")
        return S(type_, name)

    def open(self, header: str) -> None:
        self.line(header + " {")
        self.depth += 1

    def close(self) -> None:
        self.depth -= 1
        self.line("}")

    def source(self) -> str:
        return "\n".join(self.lines)


@contextmanager
def tracing(tracer: Tracer):
    _STACK.append(tracer)
    try:
        yield tracer
    finally:
        _STACK.pop()


def is_tracing() -> bool:
    """True inside `tracing()`: every operation is then symbolic, even on plain constants."""
    return bool(_STACK)


def active() -> Tracer:
    if not _STACK:
        raise TraceError("symbolic values used outside a tracer")
    return _STACK[-1]


def literal(value) -> str:
    """A Python number or bool as GLSL."""
    if isinstance(value, bool):
        return "true" if value else "false"
    value = float(value)
    if not math.isfinite(value):
        raise TraceError(f"non-finite constant {value!r} in a formula")
    text = repr(value)
    return text if ("." in text or "e" in text) else text + ".0"


def code(value) -> str:
    return value.code if isinstance(value, S) else literal(value)


def type_of(value) -> str:
    if isinstance(value, S):
        return value.type
    if isinstance(value, bool):
        return "bool"
    return "float"


def widest(*values) -> str:
    """The result type of an elementwise operation: the vector type if any operand is a vector."""
    types = [type_of(v) for v in values]
    vectors = {t for t in types if t in VEC_TYPES}
    if len(vectors) > 1:
        raise TraceError(f"mixed vector sizes {sorted(vectors)}")
    return vectors.pop() if vectors else "float"


def promote(value, type_: str) -> str:
    """`value` as GLSL of `type_` (a scalar is splatted to a vector where GLSL needs equal types)."""
    if type_ in VEC_TYPES and type_of(value) == "float":
        return f"{type_}({code(value)})"
    return code(value)


class S:
    """A symbolic GLSL value: its type and the expression (usually an SSA name) that holds it."""
    __slots__ = ("type", "code")

    def __init__(self, type_: str, code_: str):
        self.type, self.code = type_, code_

    def _bin(self, other, op, reflected=False):
        a, b = (other, self) if reflected else (self, other)
        return active().value(widest(a, b), f"{code(a)} {op} {code(b)}")

    def __add__(self, o): return self._bin(o, "+")
    def __radd__(self, o): return self._bin(o, "+", True)
    def __sub__(self, o): return self._bin(o, "-")
    def __rsub__(self, o): return self._bin(o, "-", True)
    def __mul__(self, o): return self._bin(o, "*")
    def __rmul__(self, o): return self._bin(o, "*", True)
    def __truediv__(self, o): return self._bin(o, "/")
    def __rtruediv__(self, o): return self._bin(o, "/", True)
    def __neg__(self): return active().value(self.type, f"-{self.code}")

    def _cmp(self, other, op):
        if widest(self, other) != "float":
            raise TraceError("comparisons are between scalars")
        return active().value("bool", f"{code(self)} {op} {code(other)}")

    def __lt__(self, o): return self._cmp(o, "<")
    def __le__(self, o): return self._cmp(o, "<=")
    def __gt__(self, o): return self._cmp(o, ">")
    def __ge__(self, o): return self._cmp(o, ">=")

    def _logic(self, other, op):
        return active().value("bool", f"{code(self)} {op} {code(other)}")

    def __and__(self, o): return self._logic(o, "&&")
    def __rand__(self, o): return self._logic(o, "&&")
    def __or__(self, o): return self._logic(o, "||")
    def __ror__(self, o): return self._logic(o, "||")
    def __invert__(self): return active().value("bool", f"!{self.code}")

    def __bool__(self):
        raise TraceError("a point-dependent condition was used in a Python `if`/`and`/`or`; use select() instead")

    def _component(self, index: int) -> "S":
        if self.type not in VEC_TYPES:
            raise TraceError(f"component access on a {self.type}")
        return S("float", f"{self.code}.{'xyzw'[index]}")

    x = property(lambda self: self._component(0))
    y = property(lambda self: self._component(1))
    z = property(lambda self: self._component(2))
    w = property(lambda self: self._component(3))

    def __repr__(self) -> str:
        return f"S({self.type}, {self.code})"
