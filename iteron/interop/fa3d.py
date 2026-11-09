# SPDX-License-Identifier: MIT
"""Fractalchemy's `.fa3d` 3D Editor scenes (PLAN.md \u00a77): a flame plus per-transform materials, up to eight
lights, environment and mesh settings \u2014 JSON, with the flame in the `.fa` shape.

    {"format": "fa3d", "version": 1, "scene": {"fractal": <flame>, "materials": […], "lights": […], …}}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .fa import Flame

FORMAT_ID = "fa3d"


class Fa3dFormatError(ValueError):
    """The text is not a `.fa3d` scene."""


@dataclass
class Material:
    diffuse: float = 0.8
    ambient: float = 0.25
    specular: float = 0.35
    shininess: float = 24.0
    color_mode: str = "palette"
    color: tuple[int, int, int] = (200, 200, 200)

    @classmethod
    def from_dict(cls, data: dict) -> "Material":
        return cls(diffuse=float(data.get("diffuse", 0.8)), ambient=float(data.get("ambient", 0.25)),
                    specular=float(data.get("specular", 0.35)), shininess=float(data.get("shininess", 24.0)),
                    color_mode=str(data.get("color_mode", "palette")), color=tuple(data.get("color", (200, 200, 200))))


@dataclass
class Light:
    """A distant (Sun-like) or point light, in the 3D Editor's own camera-relative convention."""
    kind: str = "distant"
    altitude: float = 45.0
    azimuth: float = 0.0
    color: tuple[int, int, int] = (255, 255, 255)
    intensity: float = 1.0
    position: tuple[float, float, float] = (0.0, 0.0, 1.0)

    @classmethod
    def from_dict(cls, data: dict) -> "Light":
        return cls(kind=str(data.get("kind", "distant")), altitude=float(data.get("altitude", 45.0)),
                   azimuth=float(data.get("azimuth", 0.0)), color=tuple(data.get("color", (255, 255, 255))),
                   intensity=float(data.get("intensity", 1.0)), position=tuple(data.get("position", (0.0, 0.0, 1.0))))

    @property
    def is_distant(self) -> bool:
        return self.kind != "point"


@dataclass
class Environment:
    color: tuple[int, int, int] = (0, 0, 0)
    ambient: float = 0.3
    exposure: float = 1.0
    visible: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "Environment":
        return cls(color=tuple(data.get("color", (0, 0, 0))), ambient=float(data.get("ambient", 0.3)),
                    exposure=float(data.get("exposure", 1.0)), visible=bool(data.get("visible", True)))


@dataclass
class MeshSettings:
    resolution: int = 128
    threshold: float = 0.15
    target_faces: int = 200_000

    @classmethod
    def from_dict(cls, data: dict) -> "MeshSettings":
        return cls(resolution=int(data.get("resolution", 128)), threshold=float(data.get("threshold", 0.15)),
                    target_faces=int(data.get("target_faces", 200_000)))


@dataclass
class Scene3D:
    name: str = "scene"
    fractal: Flame = field(default_factory=Flame)
    materials: list[Material] = field(default_factory=list)
    lights: list[Light] = field(default_factory=list)
    environment: Environment = field(default_factory=Environment)
    mesh: MeshSettings = field(default_factory=MeshSettings)

    @classmethod
    def from_dict(cls, data: dict) -> "Scene3D":
        return cls(name=str(data.get("name", "scene")), fractal=Flame.from_dict(data.get("fractal", {})),
                   materials=[Material.from_dict(m) for m in data.get("materials", [])],
                   lights=[Light.from_dict(l) for l in data.get("lights", [])],
                   environment=Environment.from_dict(data.get("environment", {})),
                   mesh=MeshSettings.from_dict(data.get("mesh", {})))

    def material_for(self, transform_index: int) -> Material:
        """The material for transform `transform_index` (the last one, Fractalchemy's own rule, beyond the list)."""
        if not self.materials:
            return Material()
        return self.materials[min(transform_index, len(self.materials) - 1)]


def parse_text(text: str) -> Scene3D:
    """Raises `Fa3dFormatError` when `text` isn't a `.fa3d` scene."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise Fa3dFormatError(f"not a .fa3d file: {exc}") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT_ID or not isinstance(data.get("scene"), dict):
        raise Fa3dFormatError("not a .fa3d file (no 'format': 'fa3d' / 'scene')")
    return Scene3D.from_dict(data["scene"])


def parse_file(path: str | Path) -> Scene3D:
    return parse_text(Path(path).read_text(encoding="utf-8"))
