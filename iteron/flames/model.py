# SPDX-License-Identifier: MIT
"""The flame model: transforms, camera and palette, read from (and written to) Fractalchemy's dict form.

Conventions are flam3's / Apophysis's, as in Fractalchemy (`fractal/scene.py`): an affine `(a, b, c, d, e, f)` maps
`(x, y)` to `(a·x + c·y + e, b·x + d·y + f)`; a transform applies `pre` → `coefs` → variations → `post`;
`color_speed` blends `c' = c·(1 − speed) + color·speed`; fractal-space y points down on screen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

Affine = tuple[float, float, float, float, float, float]
IDENTITY: Affine = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


@dataclass
class XForm:
    weight: float = 0.5
    color: float = 0.0
    color_speed: float = 0.5
    opacity: float = 1.0
    coefs: Affine = IDENTITY
    post: Affine = IDENTITY
    pre: Affine = IDENTITY
    variations: dict[str, float] = field(default_factory=lambda: {"linear": 1.0})
    params: dict[str, float] = field(default_factory=dict)
    chaos: list[float] | None = None
    var_color: float = 1.0
    name: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "XForm":
        return cls(float(d.get("weight", 0.5)), float(d.get("color", 0.0)), float(d.get("color_speed", 0.5)),
                   float(d.get("opacity", 1.0)), tuple(d.get("coefs", IDENTITY)), tuple(d.get("post", IDENTITY)),
                   tuple(d.get("pre", IDENTITY)), {k: float(v) for k, v in d.get("variations", {"linear": 1.0}).items()},
                   {k: float(v) for k, v in d.get("params", {}).items()}, d.get("chaos"), float(d.get("var_color", 1.0)),
                   d.get("name", ""))

    def to_dict(self) -> dict:
        return {"weight": self.weight, "color": self.color, "color_speed": self.color_speed, "opacity": self.opacity,
                "coefs": list(self.coefs), "post": list(self.post), "pre": list(self.pre),
                "variations": dict(self.variations), "params": dict(self.params), "chaos": self.chaos,
                "var_color": self.var_color, "name": self.name}


@dataclass
class Camera:
    """The flame's 3D camera (Apophysis `cam_*`), in Fractalchemy's form."""
    center: tuple[float, float] = (0.0, 0.0)
    scale: float = 200.0
    zoom: float = 0.0
    rotate: float = 0.0
    width: int = 800
    height: int = 600
    pitch: float = 0.0
    yaw: float = 0.0
    perspective: float = 0.0
    zpos: float = 0.0
    dof: float = 0.0
    pitch_y: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "Camera":
        return cls(tuple(d.get("center", (0.0, 0.0))), float(d.get("scale", 200.0)), float(d.get("zoom", 0.0)),
                   float(d.get("rotate", 0.0)), int(d.get("width", 800)), int(d.get("height", 600)),
                   float(d.get("pitch", 0.0)), float(d.get("yaw", 0.0)), float(d.get("perspective", 0.0)),
                   float(d.get("zpos", 0.0)), float(d.get("dof", 0.0)), float(d.get("pitch_y", 0.0)))

    def to_dict(self) -> dict:
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.__dict__.items()}

    def matrix(self) -> list[list[float]]:
        """Apophysis's yaw-then-pitch matrix (row = source axis), then the tilt about the vertical axis."""
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        cy, sy = math.cos(-self.yaw), math.sin(-self.yaw)
        m = [[cy, cp * sy, sp * sy], [-sy, cp * cy, sp * cy], [0.0, -sp, cp]]
        if self.pitch_y:
            cq, sq = math.cos(self.pitch_y), math.sin(self.pitch_y)
            m = [[r[0] * cq + r[2] * sq, r[1], -r[0] * sq + r[2] * cq] for r in m]
        return m


@dataclass
class Flame:
    name: str = "flame"
    xforms: list[XForm] = field(default_factory=list)
    final: XForm | None = None
    camera: Camera = field(default_factory=Camera)
    palette: list[tuple[int, int, int]] = field(default_factory=lambda: [(i, i, i) for i in range(256)])
    background: tuple[int, int, int] = (0, 0, 0)

    @classmethod
    def from_dict(cls, d: dict) -> "Flame":
        palette = [tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) for h in d.get("palette", [])]
        background = tuple(d.get("coloring", {}).get("background", (0, 0, 0)))
        return cls(d.get("name", "flame"), [XForm.from_dict(x) for x in d.get("xforms", [])],
                   XForm.from_dict(d["final"]) if d.get("final") else None, Camera.from_dict(d.get("camera", {})),
                   palette or cls().palette, background)

    def to_dict(self) -> dict:
        return {"name": self.name, "xforms": [x.to_dict() for x in self.xforms],
                "final": self.final.to_dict() if self.final else None, "camera": self.camera.to_dict(),
                "palette": ["%02x%02x%02x" % tuple(c) for c in self.palette],
                "coloring": {"background": list(self.background)}}

    def variation_names(self) -> set[str]:
        names = {n for x in self.xforms for n, w in x.variations.items() if w}
        if self.final is not None:
            names |= {n for n, w in self.final.variations.items() if w}
        return names
