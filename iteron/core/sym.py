# SPDX-License-Identifier: MIT
"""Symbolic tracing: run a formula's kernel once with `Sym` values instead of numpy arrays, and collect a GLSL
function body instead of a picture.

Every expression this module emits is deliberately both valid GLSL *and* valid Python (infix arithmetic and
comparisons, plain `name(args)` calls). `tests/core` replays the very text a shader would compile, with a small
Python namespace standing in for GLSL's built-ins (`core.glsl_funcs`), which is the project's stand-in for a real
GPU parity test (see PLAN.md §11). Each line is one static-single-assignment temporary, so a value used many times
(common once folds iterate) is computed once, not re-expanded — without this a dozen loop iterations would blow the
generated source up exponentially.
"""

from __future__ import annotations


def _literal(value: float) -> str:
    text = f"{float(value):.9g}"
    if "." not in text and "e" not in text and "inf" not in text and "nan" not in text:
        text += ".0"
    return text


def _ref(value) -> str:
    return value.ref if isinstance(value, Sym) else _literal(value)


class Context:
    """One shader function's worth of temporaries. `lines` is the GLSL body in order; `declare` gives the leading
    `vec3 z = p;`-style statements for loop-carried variables."""

    def __init__(self, counter: list[int] | None = None) -> None:
        self.lines: list[str] = []
        self._counter = counter if counter is not None else [0]

    def child(self) -> "Context":
        """A nested block (a loop body) that shares this context's temporary names, so none collide."""
        return Context(self._counter)

    def emit(self, expr: str, type_: str = "float") -> "Sym":
        name = f"_t{self._counter[0]}"
        self._counter[0] += 1
        self.lines.append(f"{type_} {name} = {expr};")
        return Sym(self, name)

    def call(self, fn: str, *args, type_: str = "float") -> "Sym":
        return self.emit(f"{fn}({', '.join(_ref(a) for a in args)})", type_)

    def ref(self, name: str) -> "Sym":
        """A bare reference to something already in scope (a uniform, a loop-carried variable): no new line."""
        return Sym(self, name)

    def assign(self, name: str, value) -> None:
        """`name = value;` — how a loop-carried variable is updated between iterations."""
        self.lines.append(f"{name} = {_ref(value)};")


class Sym:
    """One scalar value in the trace: either a bare reference (`z.x`, `params.power`) or a temporary's name."""

    __slots__ = ("ctx", "ref")

    def __init__(self, ctx: Context, ref: str):
        self.ctx, self.ref = ctx, ref

    def __repr__(self) -> str:           # pragma: no cover - debugging aid
        return f"Sym({self.ref})"

    def _bin(self, other, op: str) -> "Sym":
        return self.ctx.emit(f"({_ref(self)} {op} {_ref(other)})")

    def _rbin(self, other, op: str) -> "Sym":
        return self.ctx.emit(f"({_ref(other)} {op} {_ref(self)})")

    def __add__(self, other):
        return self._bin(other, "+")

    def __radd__(self, other):
        return self._rbin(other, "+")

    def __sub__(self, other):
        return self._bin(other, "-")

    def __rsub__(self, other):
        return self._rbin(other, "-")

    def __mul__(self, other):
        return self._bin(other, "*")

    def __rmul__(self, other):
        return self._rbin(other, "*")

    def __truediv__(self, other):
        return self._bin(other, "/")

    def __rtruediv__(self, other):
        return self._rbin(other, "/")

    def __neg__(self):
        return self.ctx.emit(f"(-{_ref(self)})")

    def __lt__(self, other):
        return self.ctx.emit(f"({_ref(self)} < {_ref(other)})", type_="bool")

    def __le__(self, other):
        return self.ctx.emit(f"({_ref(self)} <= {_ref(other)})", type_="bool")

    def __gt__(self, other):
        return self.ctx.emit(f"({_ref(self)} > {_ref(other)})", type_="bool")

    def __ge__(self, other):
        return self.ctx.emit(f"({_ref(self)} >= {_ref(other)})", type_="bool")


def is_symbolic(*values) -> bool:
    return any(isinstance(v, Sym) for v in values)


def literal(value) -> str:
    """`value.ref` if it is already a `Sym`, else its text as a GLSL / Python literal."""
    return _ref(value)
