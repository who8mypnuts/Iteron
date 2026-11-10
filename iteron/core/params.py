# SPDX-License-Identifier: MIT
"""Parameter specs: the single description of a formula's inputs.

Everything else is generated from these — the Blender properties and their widgets, the GLSL uniform block,
the numpy values, presets and tooltips. A *runtime* parameter lives in the uniform block (changing it needs no
shader rebuild); a *static* one is a plain Python value while the formula is traced, so Python `if`s on it are
allowed, and changing it rebuilds the shader.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Param:
    """Common fields. `name` is the Python / property identifier; `label` defaults to a title-cased name."""
    name: str
    default: Any
    label: str = ""
    description: str = ""
    group: str = ""          # sub-section of the Shape panel ("" = the main list)
    static: bool = False
    kind = "param"
    lanes = 1                # vec4 components the value occupies in the uniform block

    @property
    def title(self) -> str:
        return self.label or self.name.replace("_", " ").title()

    def coerce(self, value: Any) -> Any:
        """`value` converted to this parameter's Python type (presets and stored values go through this)."""
        return value


@dataclass(frozen=True)
class Float(Param):
    min: float = -1e9        # soft range: the slider's span
    max: float = 1e9
    hard_min: float | None = None
    hard_max: float | None = None
    subtype: str = "NONE"    # Blender property subtype: NONE, FACTOR, ANGLE, DISTANCE …
    kind = "float"

    def coerce(self, value: Any) -> float:
        return float(value)


@dataclass(frozen=True)
class Int(Param):
    min: int = 0             # hard range; `max` is also the GLSL loop bound when used as a count
    max: int = 100
    kind = "int"

    def coerce(self, value: Any) -> int:
        return int(round(float(value)))


@dataclass(frozen=True)
class Bool(Param):
    kind = "bool"

    def coerce(self, value: Any) -> bool:
        return bool(value)


@dataclass(frozen=True)
class Vec3(Param):
    min: float = -1e9
    max: float = 1e9
    subtype: str = "XYZ"     # XYZ, TRANSLATION, EULER (degrees shown), COLOR, DIRECTION
    kind = "vec3"
    lanes = 3

    def coerce(self, value: Any) -> tuple[float, float, float]:
        x, y, z = (float(v) for v in value)
        return (x, y, z)


@dataclass(frozen=True)
class Vec2(Vec3):
    """Two floats (fragments' `vec2` uniforms)."""
    subtype: str = "NONE"
    kind = "vec2"
    lanes = 2

    def coerce(self, value: Any) -> tuple[float, float]:
        x, y = (float(v) for v in tuple(value)[:2])
        return (x, y)


@dataclass(frozen=True)
class Vec4(Vec3):
    """Four floats (fragments' `vec4` uniforms; a `COLOR` one is an RGB colour and a value, in that order)."""
    subtype: str = "NONE"
    kind = "vec4"
    lanes = 4

    def coerce(self, value: Any) -> tuple[float, float, float, float]:
        x, y, z, w = (float(v) for v in tuple(value)[:4])
        return (x, y, z, w)


VECTOR_KINDS = ("vec2", "vec3", "vec4")


@dataclass(frozen=True)
class Enum(Param):
    """A choice; its value is the item identifier, seen by formulas as the item's index."""
    items: tuple[tuple[str, str, str], ...] = field(default_factory=tuple)   # (identifier, label, description)
    kind = "enum"

    def index(self, value: str) -> int:
        return [item[0] for item in self.items].index(value)

    def coerce(self, value: Any) -> str:
        ids = [item[0] for item in self.items]
        if value not in ids:
            raise ValueError(f"{self.name}: {value!r} is not one of {ids}")
        return value


def defaults(params: tuple[Param, ...]) -> dict[str, Any]:
    """Every parameter at its default."""
    return {p.name: p.coerce(p.default) for p in params}


def resolve(params: tuple[Param, ...], values: dict[str, Any] | None) -> dict[str, Any]:
    """Defaults overlaid with `values` (unknown keys are ignored, known ones coerced)."""
    out = defaults(params)
    for p in params:
        if values and p.name in values:
            out[p.name] = p.coerce(values[p.name])
    return out


def layout(params: tuple[Param, ...]) -> dict[str, tuple[int, int]]:
    """Runtime parameter → (vec4 slot, first component) in the uniform block. A vector takes a slot of its own;
    scalars share slots four to a vec4."""
    slots: dict[str, tuple[int, int]] = {}
    slot, lane = 0, 0
    for p in params:
        if p.static:
            continue
        if p.lanes > 1:
            if lane:
                slot, lane = slot + 1, 0
            slots[p.name] = (slot, 0)
            slot += 1
            continue
        slots[p.name] = (slot, lane)
        lane += 1
        if lane == 4:
            slot, lane = slot + 1, 0
    return slots


def slot_count(params: tuple[Param, ...]) -> int:
    """vec4 slots the runtime parameters need (at least one, so the block is never empty)."""
    slots = layout(params)
    return max((slot + 1 for slot, _lane in slots.values()), default=1)


def numeric(param: Param, value: Any) -> tuple[float, ...]:
    """The value as the floats written into the uniform block."""
    if param.kind in VECTOR_KINDS:
        return tuple(float(v) for v in value)
    if param.kind == "enum":
        return (float(param.index(value)),)
    if param.kind == "bool":
        return (1.0 if value else 0.0,)
    return (float(value),)
