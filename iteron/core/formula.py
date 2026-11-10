# SPDX-License-Identifier: MIT
"""Formulas: the `@formula` decorator, the registry, and the parameter values a formula sees.

A formula is one small Python function written against `ops`:

* `ESCAPE` / `IFS` kinds: `step(z, dr, c, p) -> (z, dr)`, one iteration; the runner owns the loop, the bailout,
  the distance estimate and the colour channels. `ESCAPE` formulas also get the shared Julia option.
* `DIRECT` kind: `de(pos, p) -> (distance, trap)`, the whole estimator (it may use `ops.loop` itself).

Options every formula of a kind shares (iterations, bailout, Julia) are declared once here, not per formula.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any, Callable

from . import vec
from .params import Bool, Enum, Float, Int, Param, Vec3, layout, resolve
from .trace import S, literal

ESCAPE, IFS, DIRECT = "escape", "ifs", "direct"
LOG, LINEAR = "log", "linear"
FAMILIES = ("Bulbs", "Boxes", "Sponges & Cubes", "Kaleidoscopic IFS", "Hypercomplex", "Inversions", "Hybrids")
UNIFORM = "iteron_u"          # the uniform block instance the GLSL reads parameters from

SHARED: dict[str, tuple[Param, ...]] = {
    ESCAPE: (
        Int("iterations", 12, min=1, max=64, description="Iterations of the formula per point"),
        Float("bailout", 4.0, min=1.0, max=64.0, hard_min=0.5, description="Radius beyond which a point has escaped"),
        Bool("julia", False, group="Julia", description="Iterate with a fixed constant C (a Julia set) instead of the point"),
        Vec3("julia_c", (0.0, 0.0, 0.0), min=-2.0, max=2.0, label="C", group="Julia", description="The Julia constant"),
    ),
    IFS: (
        Int("iterations", 8, min=1, max=40, description="Folding iterations per point"),
        Float("bailout", 50.0, min=2.0, max=1000.0, hard_min=1.0, description="Radius beyond which a point has escaped"),
    ),
    DIRECT: (),
}
# options every formula has, whatever its kind
GLOBAL: tuple[Param, ...] = (
    Bool("cut", False, group="Cut", description="Slice the fractal open with a plane (the cut face is closed)"),
    Enum("cut_axis", "Z", items=(("X", "X", "Cut across x"), ("Y", "Y", "Cut across y"), ("Z", "Z", "Cut across z")),
         label="Axis", group="Cut", description="The axis the cutting plane is square to"),
    Float("cut_offset", 0.0, min=-2.0, max=2.0, label="Offset", group="Cut", subtype="DISTANCE",
          description="Where the plane sits along its axis"),
    Bool("cut_flip", False, label="Flip", group="Cut", description="Keep the other side"),
)


@dataclass(frozen=True)
class Formula:
    id: str
    name: str
    family: str
    kind: str
    fn: Callable
    params: tuple[Param, ...]
    description: str = ""
    distance: str = LINEAR                  # ESCAPE / IFS without `shape`: LOG (bulbs) or LINEAR (boxes, folds)
    shape: Callable | None = None           # IFS: the final shape's distance, `shape(z, p)`, divided by |dr|
    prepare: Callable | None = None         # values derived once from the parameters, `prepare(p) -> dict`
    bounds: float = 2.0                     # half-size of the default sampling cube
    surface_offset: float = 0.6             # recommended surface offset, voxels of true distance (see refine.py):
                                            # higher for fine, dense detail that would alias (Mandelbox), lower
                                            # where holes matter (sponges)
    presets: dict[str, dict[str, Any]] = field(default_factory=dict)
    version: int = 1                        # bump when the maths changes, so cached meshes count as stale
    compose: Callable | None = None         # a formula made of others (a hybrid): `compose(own values)` → the
                                            # concrete formula; this entry is the composition of the defaults
    stored: tuple[str, ...] | None = None   # the parameters an object stores for it (None: all)

    def param(self, name: str) -> Param:
        return next(p for p in self.params if p.name == name)

    def values(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        """Defaults overlaid with `overrides`."""
        return resolve(self.params, overrides)

    def static_key(self, values: dict[str, Any]) -> tuple:
        """The static parameter values: shaders are cached per formula and this key."""
        return tuple((p.name, values[p.name]) for p in self.params if p.static)


REGISTRY: dict[str, Formula] = {}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def formula(name: str, *, family: str, kind: str, params: tuple[Param, ...] = (),
            overrides: dict[str, dict[str, Any]] | None = None, **options):
    """Register the decorated function as a formula. `overrides` changes a shared parameter's fields, e.g.
    `{"iterations": {"default": 20}}`."""
    if family not in FAMILIES or kind not in SHARED:
        raise ValueError(f"{name}: unknown family {family!r} or kind {kind!r}")
    shared = tuple(replace(p, **(overrides or {}).get(p.name, {})) for p in SHARED[kind] + GLOBAL)

    def register(fn: Callable) -> Callable:
        entry = Formula(id=slug(name), name=name, family=family, kind=kind, fn=fn, params=shared + tuple(params),
                        **options)
        names = [p.name for p in entry.params]
        if len(set(names)) != len(names):
            raise ValueError(f"{name}: duplicate parameter names")
        for preset, values in entry.presets.items():
            unknown = set(values) - set(names)
            if unknown:
                raise ValueError(f"{name}: preset {preset!r} sets unknown parameters {sorted(unknown)}")
        REGISTRY[entry.id] = entry
        return fn
    return register


def concrete(entry: Formula, values: dict[str, Any] | None = None) -> Formula:
    """The formula that runs for `values`: a hybrid composed from its choices, any other formula as it is."""
    return entry.compose(entry.values(values)) if entry.compose is not None else entry


def by_family() -> list[tuple[str, list[Formula]]]:
    """The registered formulas grouped by family, in menu order."""
    return [(fam, [f for f in REGISTRY.values() if f.family == fam]) for fam in FAMILIES
            if any(f.family == fam for f in REGISTRY.values())]


class Values:
    """The parameter values a formula reads as attributes (`p.power`), plus anything `prepare` derives."""

    def __init__(self, items: dict[str, Any]):
        self.__dict__.update(items)

    def extend(self, items: dict[str, Any] | None) -> "Values":
        if items:
            self.__dict__.update(items)
        return self


def numpy_values(entry: Formula, values: dict[str, Any]) -> Values:
    """Values for the CPU path: vectors as broadcasting constants, enums as their index."""
    items = {}
    for p in entry.params:
        value = values[p.name]
        items[p.name] = vec.constant(value) if p.kind == "vec3" else (p.index(value) if p.kind == "enum" else value)
    return _prepared(entry, Values(items))


def symbolic_values(entry: Formula, values: dict[str, Any]) -> Values:
    """Values for the GLSL path: runtime parameters read from the uniform block, static ones as constants."""
    slots = layout(entry.params)
    items = {}
    for p in entry.params:
        if p.static:
            value = values[p.name]
            if p.kind == "vec3":
                value = S("vec3", f"vec3({', '.join(literal(v) for v in value)})")
            elif p.kind == "enum":
                value = p.index(value)
            items[p.name] = value
            continue
        slot, lane = slots[p.name]
        ref = f"{UNIFORM}.v[{slot}]"
        if p.lanes > 1:
            items[p.name] = S(p.kind, f"{ref}.{'xyzw'[:p.lanes]}")
        elif p.kind == "bool":
            items[p.name] = S("bool", f"({ref}.{'xyzw'[lane]} > 0.5)")
        else:
            items[p.name] = S("float", f"{ref}.{'xyzw'[lane]}")
    return _prepared(entry, Values(items))


def _prepared(entry: Formula, values: Values) -> Values:
    return values.extend(entry.prepare(values)) if entry.prepare else values
