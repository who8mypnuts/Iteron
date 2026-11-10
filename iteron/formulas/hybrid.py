# SPDX-License-Identifier: MIT
"""Hybrids, Mandelbulb3D style: every iteration runs one formula's step a few times, then another's.

The hybrid stores only its own choices (the two formulas, how many steps of each) and the shared options; each
part's parameters are that formula's own, so a Mandelbulb keeps its values whether it is used alone or in a hybrid.
`compose` builds the concrete formula for a choice — its parameters are the parts' prefixed `a_…` / `b_…` — and the
registered entry is the composition of the defaults, so everything that takes a formula takes a hybrid too. (The
same formula twice shares one set of values.)
"""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache

from ..core.formula import ESCAPE, GLOBAL, IFS, REGISTRY, SHARED, Formula, Values
from ..core.params import Enum, Int

ID, PREFIXES = "hybrid", ("a_", "b_")
DEFAULTS = ("mandelbulb", "mandelbox")


def parts() -> list[Formula]:
    """The formulas a hybrid can combine: those with a step function (escape-time and folding IFS)."""
    return [f for f in REGISTRY.values() if f.kind in (ESCAPE, IFS) and f.compose is None]


def _own() -> tuple:
    items = tuple((f.id, f.name, f.description) for f in parts())
    return (Enum("first", DEFAULTS[0], items=items, static=True, description="The formula each iteration starts with"),
            Int("first_steps", 1, min=1, max=4, static=True, label="Steps",
                description="How many times the first formula runs per iteration"),
            Enum("second", DEFAULTS[1], items=items, static=True, description="The formula that follows"),
            Int("second_steps", 1, min=1, max=4, static=True, label="Steps ",
                description="How many times the second formula runs per iteration"))


SHARED_NAMES = {p.name for p in SHARED[ESCAPE] + GLOBAL}


def specific(entry: Formula) -> list:
    """A part's own parameters (not the options every formula shares)."""
    return [p for p in entry.params if p.name not in SHARED_NAMES]


def split(values: dict, prefix: str) -> dict:
    return {k[len(prefix):]: v for k, v in values.items() if k.startswith(prefix)}


@lru_cache(maxsize=64)
def compose_ids(first: str, second: str) -> Formula:
    a, b = REGISTRY[first], REGISTRY[second]
    shared = tuple(replace(p, **({"default": 16.0, "max": 1000.0} if p.name == "bailout" else {}))
                   for p in SHARED[ESCAPE] + GLOBAL)
    own = _own()
    prefixed = tuple(replace(p, name=prefix + p.name, group=f"{part.name}", label=p.title)
                     for prefix, part in zip(PREFIXES, (a, b)) for p in specific(part))

    def prepare(p):
        shared_values = {name: getattr(p, name) for name in SHARED_NAMES}
        out = {}
        for key, prefix, part in (("_a", "a_", a), ("_b", "b_", b)):
            values = Values({**shared_values, **{q.name: getattr(p, prefix + q.name) for q in specific(part)}})
            out[key] = values.extend(part.prepare(values)) if part.prepare else values
        return out

    def step(z, dr, c, p):
        for _ in range(p.first_steps):
            z, dr = a.fn(z, dr, c, p._a)
        for _ in range(p.second_steps):
            z, dr = b.fn(z, dr, c, p._b)
        return z, dr

    return Formula(id=ID, name="Hybrid", family="Hybrids", kind=ESCAPE, fn=step, params=shared + own + prefixed,
                   description="Two formulas alternating every iteration, Mandelbulb3D style",
                   distance=a.distance, shape=(lambda z, p: a.shape(z, p._a)) if a.shape else None, prepare=prepare,
                   bounds=max(a.bounds, b.bounds), surface_offset=max(a.surface_offset, b.surface_offset),
                   presets=PRESETS, version=100 * a.version + b.version,
                   compose=compose, stored=tuple(p.name for p in shared + own))


def compose(values: dict) -> Formula:
    """The concrete hybrid for the object's own values (`first`, `second`)."""
    return compose_ids(values.get("first", DEFAULTS[0]), values.get("second", DEFAULTS[1]))


PRESETS = {
    "Bulb + Box": {"first": "mandelbulb", "second": "mandelbox", "b_scale": -1.5},
    "ABox + Bulb": {"first": "aboxmod1", "second": "mandelbulb", "a_scale": -1.8, "iterations": 10},
    "Bulb + Menger": {"first": "mandelbulb", "second": "menger_sponge", "iterations": 5},
    "Bulb + Octahedral": {"first": "mandelbulb", "second": "octahedral_kifs", "iterations": 6},
    "Int Pow + Box": {"first": "folding_int_pow", "second": "mandelbox", "b_scale": -1.5, "iterations": 10},
    "Lambda + Box": {"first": "lambdabulb", "second": "mandelbox", "b_scale": -1.5, "iterations": 10},
}
REGISTRY[ID] = compose_ids(*DEFAULTS)
