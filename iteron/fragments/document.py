# SPDX-License-Identifier: MIT
"""A fragment file's text: Fractalchemy's metadata block, the `#preset` blocks, and the camera a preset holds.

A `.fafrag` is a `.frag` plus at most one JSON block FragM reads as a comment (`/*[fractalchemy] … [/fractalchemy]*/`);
it is dropped here. Presets are FragM's `#preset Name … #endpreset` blocks of `Key = value` lines. Ported from
Fractalchemy (`fragments/document_format.py`, `fragments/presets.py`, Stan Ragets, MIT).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

RE_METADATA = re.compile(r"\n?/\*\[fractalchemy\]\s*\n.*?\n\[/fractalchemy\]\*/\s*", re.DOTALL)
RE_PRESET = re.compile(r"^\s*#preset\s+(.*?)\s*$(.*?)^\s*#endpreset\s*$", re.IGNORECASE | re.MULTILINE | re.DOTALL)
RE_SUFFIX = re.compile(r"\s+(AlwaysLocked|Locked|NotLocked|NotLockable|Logarithmic)\s*$", re.IGNORECASE)
NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
KEYFRAME, RANGE = "keyframe.", "range"


def read(path: Path) -> str:
    """A fragment file's source without Fractalchemy's metadata block."""
    return strip_metadata(Path(path).read_text(encoding="utf-8", errors="replace"))


def strip_metadata(text: str) -> str:
    return RE_METADATA.sub("\n", text)


def presets(text: str) -> dict[str, dict[str, str]]:
    """Preset name → {key: value text}, in file order; camera-path keyframes and easing ranges are left out."""
    found: dict[str, dict[str, str]] = {}
    for match in RE_PRESET.finditer(text):
        name = match.group(1).strip() or "Default"
        if name.lower().startswith((KEYFRAME, RANGE)):
            continue
        values = {}
        for line in match.group(2).splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip():
                values[key.strip()] = RE_SUFFIX.sub("", value.strip())
        found[name] = values
    return found


def remove_presets(text: str) -> str:
    """The text without its preset blocks (line count kept, so compile errors still point at the right line)."""
    return RE_PRESET.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def numbers(text: str, count: int) -> tuple[float, ...]:
    """The first `count` numbers in `text` (missing ones read as 0, as FragM does)."""
    found = [float(n) for n in NUMBER.findall(text)]
    return tuple((found + [0.0] * count)[:count])


@dataclass(frozen=True)
class FragCamera:
    """The 3D camera of a preset (`Eye`, `Target`, `Up`, `FOV`: FragM's `3D.frag` convention, y up)."""
    eye: tuple[float, float, float]
    target: tuple[float, float, float]
    up: tuple[float, float, float]
    fov: float

    @property
    def vertical_angle(self) -> float:
        """FragM's rays are `dir + (x·right + y·up)·FOV` with y in −1…1: the vertical field of view."""
        return 2.0 * math.atan(self.fov)

    @property
    def distance(self) -> float:
        return math.dist(self.eye, self.target)


def camera(values: dict[str, str]) -> FragCamera | None:
    if "Eye" not in values or "Target" not in values:
        return None
    return FragCamera(numbers(values["Eye"], 3), numbers(values["Target"], 3),
                      numbers(values.get("Up", "0,1,0"), 3), numbers(values.get("FOV", "0.4"), 1)[0])
