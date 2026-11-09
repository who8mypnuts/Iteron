# SPDX-License-Identifier: MIT
"""`#preset NAME … #endpreset` blocks: FragM's way of saving a set of uniform values (PLAN.md \u00a77).

    #preset Default
    FOV = 0.4
    Eye = 1.44674,0.992411,-0.508827
    CycleColors = true
    #endpreset
"""

from __future__ import annotations

import re

_PRESET = re.compile(r"#preset\s+(.+?)\s*\n(.*?)\n#endpreset", re.DOTALL)
_ENTRY = re.compile(r"^\s*([A-Za-z_][\w.]*)\s*=\s*(.+?)\s*$")


def _value(text: str):
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    parts = text.split(",")
    try:
        numbers = [float(p) for p in parts]
    except ValueError:
        return text
    return numbers[0] if len(numbers) == 1 else tuple(numbers)


def parse(source: str) -> dict[str, dict[str, object]]:
    """Every preset's name \u2192 its settings (uniform name \u2192 number / tuple / bool / text), in file order."""
    presets: dict[str, dict[str, object]] = {}
    for name, body in _PRESET.findall(source):
        settings = {}
        for line in body.splitlines():
            match = _ENTRY.match(line)
            if match:
                settings[match.group(1)] = _value(match.group(2))
        presets[name] = settings
    return presets
