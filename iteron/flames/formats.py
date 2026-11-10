# SPDX-License-Identifier: MIT
"""Fractalchemy's flame files, and its 3D camera and lights turned into world-space terms Blender can use.

* `.fa` — `{"format": "fractalchemy", "version": 1, "flames": [flame dict, …]}`
* `.fa3d` — `{"format": "fa3d", "version": 1, "scene": {"fractal": flame dict, "lights": …, "environment": …,
  "mesh": …, …}}`

The camera and light conversions follow Fractalchemy's own Blender export (`solid/io/blender.py`, Stan Ragets,
MIT): the flame's 3D camera matrix gives the view's right / up / back vectors in fractal space (which the Blender
object keeps as its local space), the eye sits `1 / perspective` from the view plane, and distant lights are placed
relative to the camera (altitude above the view plane, azimuth around it).

Fractal space has y pointing down the screen and z towards the eye — a mirror image of a right-handed space. Iteron
turns it into Blender's space by negating y (`TO_BLENDER`), for points, cameras and lights alike, so the camera is a
proper rotation and the picture matches Fractalchemy's rather than its mirror image.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .model import Camera, Flame


TO_BLENDER = np.diag([1.0, -1.0, 1.0])


class FormatError(ValueError):
    """Not a Fractalchemy file this reader understands."""


def read_json(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FormatError(f"{Path(path).name}: {error}") from error


def read_fa(path: Path) -> list[Flame]:
    data = read_json(path)
    if not isinstance(data, dict) or data.get("format") != "fractalchemy" or not isinstance(data.get("flames"), list):
        raise FormatError(f"{Path(path).name} is not a Fractalchemy .fa document")
    return [Flame.from_dict(f) for f in data["flames"]]


@dataclass
class Light:
    kind: str                       # "distant" or "point"
    colour: tuple[float, float, float]
    intensity: float
    shadows: bool
    direction: np.ndarray | None = None     # distant: towards the light, world space
    position: np.ndarray | None = None      # point: world space
    radius: float = 1.0


@dataclass
class Scene:
    flame: Flame
    lights: list[Light] = field(default_factory=list)
    background: tuple[float, float, float] = (0.12, 0.125, 0.16)
    ambient: float = 0.6
    background_visible: bool = True
    mesh: dict = field(default_factory=dict)          # Fractalchemy's mesh settings (points, resolution, threshold …)
    solid: bool = True                                # the scene was shown as a lit solid (else points)
    materials: list[dict] = field(default_factory=list)  # per transform: diffuse, specular, shininess …

    def surface(self) -> tuple[float, float]:
        """`(roughness, specular)` for a Principled BSDF from the first transform's Blinn–Phong material, as
        Fractalchemy's own Blender export does."""
        material = self.materials[0] if self.materials else {}
        roughness = min(1.0, max(0.05, 1.0 - float(material.get("shininess", 24.0)) / 200.0))
        return roughness, min(1.0, float(material.get("specular", 0.35)))


def read_fa3d(path: Path) -> Scene:
    data = read_json(path)
    if not isinstance(data, dict) or data.get("format") != "fa3d" or not isinstance(data.get("scene"), dict):
        raise FormatError(f"{Path(path).name} is not a Fractalchemy .fa3d scene")
    scene = data["scene"]
    if not isinstance(scene.get("fractal"), dict):
        raise FormatError(f"{Path(path).name} holds no fractal")
    flame = Flame.from_dict(scene["fractal"])
    matrix = np.array(flame.camera.matrix())
    lights = [_light(light, matrix) for light in scene.get("lights", [])]
    env = scene.get("environment", {})
    colour = tuple(c / 255.0 for c in env.get("color", (30, 32, 40)))
    return Scene(flame, lights, colour, float(env.get("ambient", 0.6)), bool(env.get("visible", True)),
                 dict(scene.get("mesh", {})), scene.get("solid", {}).get("display", "solid") != "points",
                 [m for m in scene.get("materials", []) if isinstance(m, dict)])


def light_direction(altitude: float, azimuth: float) -> np.ndarray:
    """Towards a distant light in view space: altitude above the view plane, azimuth around the view axis."""
    alt, az = math.radians(altitude), math.radians(azimuth)
    return np.array([math.cos(alt) * math.cos(az), -math.cos(alt) * math.sin(az), math.sin(alt)])


def _light(data: dict, matrix: np.ndarray) -> Light:
    colour = tuple(c / 255.0 for c in data.get("color", (255, 255, 255)))
    intensity = float(data.get("intensity", 0.8))
    if data.get("kind") == "point":
        position = TO_BLENDER @ np.array(data.get("position", (0.0, 0.0, 1.0)), float)
        return Light("point", colour, intensity, False, position=position,
                     radius=float(data.get("radius", 1.0)))
    direction = TO_BLENDER @ (light_direction(float(data.get("altitude", 55.0)), float(data.get("azimuth", -22.0))) @ matrix.T)
    return Light("distant", colour, intensity, bool(data.get("shadows", True)), direction=direction)


@dataclass
class CameraFrame:
    """The flame's camera in Blender's terms (the flame object's local space, see `TO_BLENDER`)."""
    right: np.ndarray
    up: np.ndarray
    back: np.ndarray                # towards the eye
    target: np.ndarray              # the world point at the image centre
    distance: float
    perspective: bool
    fov: float                      # radians, across the width
    ortho_width: float
    width: int
    height: int
    roll: float                     # radians about the view axis (the flame's 2D rotation)

    @property
    def location(self) -> np.ndarray:
        return self.target + self.back * self.distance

    def matrix(self) -> np.ndarray:
        """4 × 4 camera-to-world (columns right, up, back; Blender cameras look down −z with +y up)."""
        c, s = math.cos(self.roll), math.sin(self.roll)
        right, up = c * self.right + s * self.up, -s * self.right + c * self.up
        m = np.eye(4)
        m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = right, up, self.back, self.location
        return m


def camera_frame(camera: Camera, extent: float = 2.0) -> CameraFrame:
    m = np.array(camera.matrix(), dtype=np.float64)
    right, up, back = TO_BLENDER @ m[:, 0], TO_BLENDER @ -m[:, 1], TO_BLENDER @ m[:, 2]
    ppu = camera.scale * (2.0 ** camera.zoom)
    visible_width = max(camera.width, 1) / max(ppu, 1e-9)
    cx, cy = camera.center
    target = TO_BLENDER @ (cx * m[:, 0] + cy * m[:, 1] + np.array([0.0, 0.0, camera.zpos]))
    if camera.perspective > 0:
        distance = 1.0 / camera.perspective
        fov = 2.0 * math.atan(visible_width / 2.0 * camera.perspective)
    else:
        distance, fov = max(extent, 1e-6) * 3.0, math.radians(40.0)
    return CameraFrame(right, up, back, target, distance, camera.perspective > 0, fov, visible_width,
                       max(1, camera.width), max(1, camera.height), math.radians(camera.rotate))
