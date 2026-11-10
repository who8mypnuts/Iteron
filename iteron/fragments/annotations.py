# SPDX-License-Identifier: MIT
"""Annotated uniforms — FragM's slider grammar — turned into Iteron parameter specs.

    uniform float Power; slider[1,8,16]                           → Float
    uniform vec3 Offset; slider[(-1,-1,-1),(0,0,0),(1,1,1)]        → Vec3 (also vec2, vec4)
    uniform vec3 Tint; color[1,0.5,0]   ·   uniform vec4 Glow; color[0,0.2,1, 1,1,1]  → Vec3 / Vec4 colours
    uniform int Iterations; slider[1,12,100]  ·  menu[2, A;B;C]  ·  uniform bool Julia; checkbox[false]

`double` / `dvec` types read as their float forms (the GPU path is float32). The regular expressions are
Fractalchemy's translation of FragM's (`fragments/preprocessor.py`, Stan Ragets, MIT). Trailing `Locked`,
`Logarithmic` and similar words are accepted and ignored.
"""

from __future__ import annotations

import re

from ..core.params import Bool, Enum, Float, Int, Param, Vec2, Vec3, Vec4

NUMF = r"\s*([-+]?\d*(?:[.]\d*)?(?:[eE][+-]?\d+)?)\s*"
NUMI = r"\s*([-+]?\d+)\s*"
TAIL = r"\s*(?:Linear|Logarithmic)?\s*(?:AlwaysLocked|Locked|NotLocked|NotLockable)?\s*.?\s*$"


def _vec(n: int) -> str:
    return r"\s*\(" + ",".join([NUMF] * n) + r"\)\s*"


def _decl(types: str) -> str:
    return r"^\s*uniform\s+(" + types + r")\s+(\w+)\s*;\s*"


RE_VECTOR = {n: re.compile(_decl(f"d?vec{n}") + r"slider\s*\[" + ",".join([_vec(n)] * 3) + r"\]" + TAIL)
             for n in (2, 3, 4)}
RE_FLOAT = re.compile(_decl("float|double") + r"slider\s*\[" + ",".join([NUMF] * 3) + r"\]" + TAIL)
RE_COLOR = re.compile(_decl("d?vec3") + r"color\s*\[" + ",".join([NUMF] * 3) + r"\]" + TAIL)
RE_FLOAT_COLOR = re.compile(_decl("d?vec4") + r"color\s*\[" + ",".join([NUMF] * 6) + r"\]" + TAIL)
RE_MENU = re.compile(_decl("int") + r"menu\s*\[" + NUMI + r",(.*)\]" + TAIL)
RE_INT = re.compile(_decl("int") + r"slider\s*\[" + ",".join([NUMI] * 3) + r"\]" + TAIL)
RE_BOOL = re.compile(_decl("bool") + r"checkbox\s*\[\s*(true|false)\s*\]" + TAIL, re.IGNORECASE)
RE_SAMPLER = re.compile(r"^\s*uniform\s+([iu]?sampler\w*)\s+(\w+)\s*;")
RE_PLAIN = re.compile(r"^\s*uniform\s+((?:lowp|mediump|highp)\s+)?(\w+)\s+(\w+)\s*(\[\s*\w*\s*\])?\s*;")


def _f(text: str) -> float:
    try:
        return float(text) if text.strip() else 0.0
    except ValueError:
        return 0.0


def parse(line: str, group: str, comment: str) -> Param | None:
    """The parameter an annotated uniform declares (None: not an annotated uniform)."""
    common = {"group": group, "description": comment}
    if m := RE_FLOAT.match(line):
        lo, default, hi = (_f(t) for t in m.groups()[2:5])
        return Float(m.group(2), default, label=m.group(2), min=min(lo, hi), max=max(lo, hi), **common)
    for n, regex in RE_VECTOR.items():
        if m := regex.match(line):
            values = [_f(t) for t in m.groups()[2:2 + 3 * n]]
            lo, default, hi = values[:n], tuple(values[n:2 * n]), values[2 * n:]
            low, high = min(lo + hi), max(lo + hi)
            if low == high:                      # FragM: equal bounds mean a direction
                low, high = -1.0, 1.0
            return {2: Vec2, 3: Vec3, 4: Vec4}[n](m.group(2), default, label=m.group(2), min=low, max=high, **common)
    if m := RE_COLOR.match(line):
        return Vec3(m.group(2), tuple(_f(t) for t in m.groups()[2:5]), label=m.group(2), min=0.0, max=1.0,
                    subtype="COLOR", **common)
    if m := RE_FLOAT_COLOR.match(line):
        lo, value, hi, r, g, b = (_f(t) for t in m.groups()[2:8])
        return Vec4(m.group(2), (r, g, b, value), label=m.group(2), min=min(lo, hi), max=max(lo, hi),
                    subtype="COLOR", **common)
    if m := RE_MENU.match(line):
        texts = [t.strip() for t in m.group(4).split(";")]
        items = tuple((str(i), t or str(i), t) for i, t in enumerate(texts))
        default = min(max(int(m.group(3)), 0), len(items) - 1)
        return Enum(m.group(2), str(default), label=m.group(2), items=items, **common)
    if m := RE_INT.match(line):
        lo, default, hi = (int(t) for t in m.groups()[2:5])
        return Int(m.group(2), default, label=m.group(2), min=min(lo, hi), max=max(lo, hi), **common)
    if m := RE_BOOL.match(line):
        return Bool(m.group(2), m.group(3).lower() == "true", label=m.group(2), **common)
    return None


def from_text(param: Param, text: str):
    """A preset's value text for `param` (FragM's settings format: `1.5`, `0.3,0.55,-0.3`, `true`, `2`)."""
    from .document import numbers
    if param.kind == "bool":
        return text.strip().lower() == "true"
    if param.kind == "enum":
        return str(min(max(int(numbers(text, 1)[0]), 0), len(param.items) - 1))
    if param.lanes > 1:
        return numbers(text, param.lanes)
    value = numbers(text, 1)[0]
    return int(round(value)) if param.kind == "int" else value
