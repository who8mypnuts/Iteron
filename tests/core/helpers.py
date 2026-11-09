# SPDX-License-Identifier: MIT
"""Replaying a `Sym` trace's GLSL text with plain Python: the stand-in this project uses for compiling on a real
GPU, since every line `core.sym.Context` emits is deliberately valid as both GLSL and Python (see core/sym.py and
PLAN.md §11 on the sandbox's limits). Test-only; not part of the add-on.
"""

from __future__ import annotations

import re

from iteron.core.glsl_funcs import PY_NAMESPACE
from iteron.core.sym import Sym

_ASSIGNMENT = re.compile(r"^\s*(?:float|bool|int)\s+(\w+)\s*=\s*(.+);\s*$")


def replay(lines: list[str], initial: dict | None = None) -> dict:
    """Every temporary's value, after evaluating `lines` (flat SSA assignments, no control flow) in order."""
    namespace = dict(PY_NAMESPACE)
    namespace.update(initial or {})
    for line in lines:
        match = _ASSIGNMENT.match(line)
        assert match, f"not a flat assignment (this helper can't replay control flow): {line!r}"
        name, expr = match.groups()
        namespace[name] = eval(expr, {"__builtins__": {}}, namespace)  # noqa: S307 - our own generated text only
    return namespace


def value(namespace: dict, result):
    """The concrete number `result` (a `Sym` or a plain constant) evaluates to in `namespace`."""
    if isinstance(result, Sym):
        return namespace[result.ref] if result.ref in namespace else eval(result.ref, {"__builtins__": {}}, namespace)
    return result
