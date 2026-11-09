# SPDX-License-Identifier: MIT
"""Fractalchemy's `.fa` flame files: JSON, one document holding any number of flames (PLAN.md \u00a77).

    {"format": "fractalchemy", "version": 1, "flames": [ <flame>, ... ]}

Only what Iteron can eventually use is modelled here \u2014 the IFS itself (transforms, weights, variations,
colour), the camera and the palette \u2014 not the tone-curve or xaos details a renderer would also need; unknown
keys are simply ignored, the same forward-compatible reading Fractalchemy's own `Flame.from_dict` does.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

FORMAT_ID = "fractalchemy"


class FaFormatError(ValueError):
    """The text is not a `.fa` document."""


@dataclass
class XForm:
    """One transform of the iterated function system."""
    weight: float = 0.5
    color: float = 0.0
    coefs: tuple[float, float, float, float, float, float] = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    post: tuple[float, float, float, float, float, float] = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    variations: dict[str, float] = field(default_factory=dict)
    params: dict[str, float] = field(default_factory=dict)
    name: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "XForm":
        return cls(weight=float(data.get("weight", 0.5)), color=float(data.get("color", 0.0)),
                   coefs=_affine(data.get("coefs")), post=_affine(data.get("post")),
                   variations=dict(data.get("variations", {})), params=dict(data.get("params", {})),
                   name=str(data.get("name", "")))


@dataclass
class Flame:
    """A flame's IFS, camera and palette \u2014 enough to run the chaos game (Phase 4) and show where it came from."""
    name: str = "flame"
    xforms: list[XForm] = field(default_factory=list)
    final: XForm | None = None
    camera_center: tuple[float, float] = (0.0, 0.0)
    camera_scale: float = 200.0
    camera_pitch: float = 0.0
    camera_yaw: float = 0.0
    palette: list[tuple[int, int, int]] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Flame":
        camera = data.get("camera", {})
        palette = [tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) for h in data.get("palette", [])]
        return cls(
            name=str(data.get("name", "flame")),
            xforms=[XForm.from_dict(x) for x in data.get("xforms", [])],
            final=XForm.from_dict(data["final"]) if data.get("final") else None,
            camera_center=tuple(camera.get("center", (0.0, 0.0))),
            camera_scale=float(camera.get("scale", 200.0)),
            camera_pitch=float(camera.get("pitch", 0.0)),
            camera_yaw=float(camera.get("yaw", 0.0)),
            palette=palette,
            unsupported=list(data.get("unsupported", [])),
        )

    @property
    def variation_names(self) -> set[str]:
        names = {name for x in self.xforms for name in x.variations}
        if self.final:
            names |= set(self.final.variations)
        return names


def _affine(values) -> tuple[float, float, float, float, float, float]:
    if not values or len(values) != 6:
        return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    return tuple(float(v) for v in values)


def parse_text(text: str) -> list[Flame]:
    """Every flame in a `.fa` document's text.

    Raises:
        FaFormatError: When the text isn't a `.fa` document.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FaFormatError(f"not a .fa file: {exc}") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT_ID or not isinstance(data.get("flames"), list):
        raise FaFormatError("not a .fa file (no 'format': 'fractalchemy' / 'flames')")
    return [Flame.from_dict(d) for d in data["flames"]]


def parse_file(path: str | Path) -> list[Flame]:
    return parse_text(Path(path).read_text(encoding="utf-8"))
