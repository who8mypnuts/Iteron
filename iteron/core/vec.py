# SPDX-License-Identifier: MIT
"""numpy vectors for the CPU path: `NVec` holds a `(k, N)` array (k = 2…4 lanes, N points or 1 for constants).

Scalars are plain `(N,)` arrays or Python numbers; mixing them with an `NVec` broadcasts like GLSL's scalar-vector
arithmetic. Formulas never see this module directly — they use `ops`, which accepts either backend.
"""

from __future__ import annotations

import numpy as np


class NVec:
    """A batch of vectors; immutable in practice (every operation returns a new one)."""
    __slots__ = ("a",)
    __array_priority__ = 100            # so `ndarray (op) NVec` defers to NVec's reflected operators

    def __init__(self, array: np.ndarray):
        self.a = array

    @property
    def dims(self) -> int:
        return int(self.a.shape[0])

    x = property(lambda self: self.a[0])
    y = property(lambda self: self.a[1])
    z = property(lambda self: self.a[2])
    w = property(lambda self: self.a[3])

    def _op(self, other, fn, reflected=False):
        a, b = lanes(self), lanes(other)
        return NVec(fn(b, a) if reflected else fn(a, b))

    def __add__(self, o): return self._op(o, np.add)
    def __radd__(self, o): return self._op(o, np.add, True)
    def __sub__(self, o): return self._op(o, np.subtract)
    def __rsub__(self, o): return self._op(o, np.subtract, True)
    def __mul__(self, o): return self._op(o, np.multiply)
    def __rmul__(self, o): return self._op(o, np.multiply, True)
    def __truediv__(self, o): return self._op(o, np.divide)
    def __rtruediv__(self, o): return self._op(o, np.divide, True)
    def __neg__(self): return NVec(-self.a)

    def __repr__(self) -> str:
        return f"NVec({self.a!r})"


def lanes(value):
    """The value in lane layout: an NVec's array, a scalar array as `(1, N)`, numbers unchanged."""
    if isinstance(value, NVec):
        return value.a
    if isinstance(value, np.ndarray) and value.ndim == 1:
        return value[None, :]
    return value


def any_vec(*values) -> bool:
    return any(isinstance(v, NVec) for v in values)


def lift(fn, *values):
    """Apply an elementwise numpy function; the result is an NVec when any input is one."""
    if any_vec(*values):
        return NVec(np.asarray(fn(*(lanes(v) for v in values)), dtype=np.float64))
    return fn(*values)


def make(*components) -> NVec:
    """A vector from scalar components (numbers or `(N,)` arrays), broadcast to a common length."""
    arrays = np.broadcast_arrays(*(np.atleast_1d(np.asarray(c, dtype=np.float64)) for c in components))
    return NVec(np.stack(arrays))


def constant(values) -> NVec:
    """A vector parameter as a `(k, 1)` NVec, broadcasting against any batch."""
    return NVec(np.asarray(values, dtype=np.float64).reshape(-1, 1))
