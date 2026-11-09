# SPDX-License-Identifier: MIT
"""Turning a fragment's annotated uniforms into `core.params.Param`, so the shared parameter drawer
(`iteron.ui.draw`) can show them exactly like a built-in formula's (PLAN.md \u00a77).

    // Mandelbulb exponent (8 is standard)
    uniform float Power; slider[0,8,16]
    uniform bool Julia; checkbox[false]
    uniform vec3 JuliaC; slider[(-2,-2,-2),(0,0,0),(2,2,2)]
"""

from __future__ import annotations

import re

from ...core.params import Bool, Float, Int, Param, Vec3

_UNIFORM = re.compile(r"^\s*uniform\s+(int|float|bool|vec3)\s+(\w+)\s*;\s*(?:(slider|checkbox)\s*\[(.*)\])?")
_NUMBER = re.compile(r"-?\d+\.?\d*(?:[eE][+-]?\d+)?")
_VEC3 = re.compile(r"\(([^()]*)\)")


def _numbers(text: str) -> list[float]:
    return [float(m) for m in _NUMBER.findall(text)]


def parse(source: str) -> list[Param]:
    """Every `uniform` the text annotates with `slider[…]` or `checkbox[…]`, in the order they appear. A `//`
    comment on its own line right before a uniform becomes its description, as the examples all write them."""
    params: list[Param] = []
    pending_comment = ""
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("//") and not _UNIFORM.match(line):
            pending_comment = stripped.lstrip("/").strip()
            continue
        match = _UNIFORM.match(line)
        if not match:
            if stripped:
                pending_comment = ""
            continue
        kind, name, widget, body = match.groups()
        param = _build(kind, name, widget, body or "", pending_comment)
        if param is not None:
            params.append(param)
        pending_comment = ""
    return params


def _build(kind: str, name: str, widget: str | None, body: str, description: str) -> Param | None:
    if kind == "bool":
        default = body.strip().lower() == "true" if widget == "checkbox" else False
        return Bool(name, default, description)
    if widget != "slider":
        return None            # an un-annotated uniform: Fractalchemy's own editor hides these too
    if kind == "vec3":
        groups = _VEC3.findall(body)
        if len(groups) != 3:
            return None
        lo, default, hi = (tuple(_numbers(g)) for g in groups)
        return Vec3(name, default, min(lo), max(hi), description)
    numbers = _numbers(body)
    if len(numbers) != 3:
        return None
    lo, default, hi = numbers
    return (Int(name, int(default), int(lo), int(hi), description) if kind == "int"
            else Float(name, default, lo, hi, description))
