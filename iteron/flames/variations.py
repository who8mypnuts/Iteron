# SPDX-License-Identifier: MIT
"""Flame variations: the registry and how one is applied (numpy, vectorised over points).

A variation function takes a `Point` (the point after the transform's affine: `x, y, z`; the accumulator
`px, py, pz`; its weight `w`, parameters, the affine `coefs`, a random generator) and returns its weighted
contribution `(dx, dy)` or `(dx, dy, dz)`. Apophysis's order is kept: `pre_` variations rewrite the input point, the
others add to the accumulator, `post_` ones run last on it. A 2D variation passes the depth through (`dz = w·z`) when
Apophysis's built-in does (`z="pass"`). Ported from Fractalchemy (`fractal/variations.py`, Stan Ragets, MIT).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

EPS = 1e-10
PI = np.pi
NORMAL, PRE, POST = "normal", "pre", "post"
NONE, PASS, FORMULA = "none", "pass", "formula"


class Point:
    """A batch of points for the variation functions, with flam3's lazily computed polar helpers."""
    __slots__ = ("x", "y", "z", "px", "py", "pz", "w", "coefs", "params", "rng", "_r2", "_r", "_theta", "_phi")

    def __init__(self, x, y, z, px, py, pz, w, coefs, params, rng):
        self.x, self.y, self.z, self.px, self.py, self.pz = x, y, z, px, py, pz
        self.w, self.coefs, self.params, self.rng = w, coefs, params, rng
        self._r2 = self._r = self._theta = self._phi = None

    @property
    def r2(self):
        if self._r2 is None:
            self._r2 = self.x * self.x + self.y * self.y
        return self._r2

    @property
    def r(self):
        if self._r is None:
            self._r = np.sqrt(self.r2)
        return self._r

    @property
    def theta(self):                        # flam3's "theta" is atan2(x, y)
        if self._theta is None:
            self._theta = np.arctan2(self.x, self.y)
        return self._theta

    @property
    def phi(self):
        if self._phi is None:
            self._phi = np.arctan2(self.y, self.x)
        return self._phi

    def p(self, name: str) -> float:
        return self.params[name]

    def rnd(self) -> np.ndarray:
        return self.rng.random(self.x.shape[0])


@dataclass(frozen=True)
class Variation:
    name: str
    fn: Callable
    params: dict[str, float] = field(default_factory=dict)   # full flame-file names → defaults
    kind: str = NORMAL
    z: str = NONE

    def apply(self, p: Point):
        """The point's state after this variation: `(x, y, z, px, py, pz)`."""
        out = self.fn(p)
        dx, dy = out[0], out[1]
        dz = out[2] if len(out) == 3 else (p.w * p.z if self.z == PASS else 0.0)
        if self.kind == PRE:
            return p.x + dx, p.y + dy, p.z + dz, p.px, p.py, p.pz
        return p.x, p.y, p.z, p.px + dx, p.py + dy, p.pz + dz


REGISTRY: dict[str, Variation] = {}
ALIASES: dict[str, str] = {}


def variation(name: str, params: dict[str, float] | None = None, *, kind: str = NORMAL, z: str = NONE,
              aliases: tuple[str, ...] = (), prefix: str = ""):
    """Register the decorated function; short parameter names (`power`) get the variation's prefix (or `prefix`,
    for plugins whose files use another, like oscilloscope's `oscope_`)."""
    def register(fn: Callable) -> Callable:
        head = (prefix or name) + "_"
        full = {(k if k.startswith(head) else head + k): float(v) for k, v in (params or {}).items()}
        REGISTRY[name] = Variation(name, fn, full, kind, z)
        for alias in aliases:
            ALIASES[alias] = name
        return fn
    return register


def resolve(name: str) -> Variation | None:
    _load()
    return REGISTRY.get(ALIASES.get(name, name))


def canonical(name: str) -> str:
    _load()
    return ALIASES.get(name, name)


def parameter_owner(key: str) -> str | None:
    """The variation that declares parameter `key` (a flame file's attribute), if any."""
    _load()
    return next((var.name for var in REGISTRY.values() if key in var.params), None)


def _load() -> None:
    if not REGISTRY:
        from . import var_classic, var_depth, var_flam3, var_plugins  # noqa: F401  (registration by import)
