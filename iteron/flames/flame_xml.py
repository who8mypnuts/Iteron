# SPDX-License-Identifier: MIT
"""Apophysis / flam3 `.flame` files (`<Flames><flame …><xform …/>…<palette>…</palette></flame></Flames>`) → flames.

After Fractalchemy's `fractal/formats/flame_xml.py` (Stan Ragets, MIT), reading only: an xform's attributes are its
affine (`coefs`, `post`), weight, colour, `symmetry` (or flam3's `color_speed`), opacity, xaos (`chaos`), and the
variations with their parameters — an attribute that isn't a known xform field is a variation unless a known
variation (or another attribute's name, as a prefix) claims it as a parameter. The 3D camera is Apophysis 7X's
`cam_*` attributes; `angle` (radians, flam3) or `rotate` (degrees) sets the roll. Variations Iteron lacks are kept by
name and reported when the flame is built, as for `.fa` files.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .formats import FormatError
from .model import IDENTITY, Camera, Flame, XForm
from .variations import parameter_owner, resolve

XFORM_FIELDS = {"weight", "color", "symmetry", "color_speed", "opacity", "coefs", "post", "chaos", "name", "animate",
                "plotmode", "var_color", "enabled", "var", "var1", "vars", "pre_affine", "motion_frequency",
                "motion_function", "motion_offset"}
HEX = re.compile(r"[0-9A-Fa-f]{6}")


def read_flame(path: Path) -> list[Flame]:
    """Every flame in the file that has at least one transform."""
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        raise FormatError(f"{Path(path).name} is not a flame file: {error}") from error
    elements = [root] if root.tag == "flame" else root.findall("flame")
    flames = [flame_from_element(e) for e in elements if e.find("xform") is not None]
    if not flames:
        raise FormatError(f"{Path(path).name} holds no flame with transforms")
    return flames


def flame_from_element(el: ET.Element) -> Flame:
    width, height = _numbers(el.get("size"), 2, (800.0, 600.0))
    center = _numbers(el.get("center"), 2, (0.0, 0.0))
    rotate = _number(el.get("rotate"), None)
    if rotate is None:
        rotate = -_number(el.get("angle"), 0.0) * 180.0 / math.pi
    perspective = _number(el.get("cam_perspective"), None)
    if perspective is None:
        distance = _number(el.get("cam_dist"), 0.0)
        perspective = 1.0 / distance if distance else 0.0
    camera = Camera(center, _number(el.get("scale"), 200.0), _number(el.get("zoom"), 0.0), rotate, int(width),
                    int(height), _number(el.get("cam_pitch"), 0.0), _number(el.get("cam_yaw"), 0.0), perspective,
                    _number(el.get("cam_zpos"), 0.0), abs(_number(el.get("cam_dof"), 0.0)),
                    _number(el.get("cam_pitch_y"), 0.0))
    flame = Flame(el.get("name", "flame"), [_xform(x) for x in el.findall("xform")], None, camera)
    final = el.find("finalxform")
    if final is not None and final.get("enabled", "1") != "0":
        flame.final = _xform(final)
    flame.palette = _palette(el) or flame.palette
    flame.background = tuple(max(0, min(255, round(v * 255))) for v in _numbers(el.get("background"), 3, (0, 0, 0)))
    return flame


def _xform(el: ET.Element) -> XForm:
    attrs = dict(el.attrib)
    speed = (_number(attrs["color_speed"], 0.5) if "color_speed" in attrs
             else (1.0 - _number(attrs.get("symmetry"), 0.0)) / 2.0)
    chaos = [float(v) for v in attrs["chaos"].split()] if attrs.get("chaos", "").strip() else None
    variations, params = split_variations(attrs)
    return XForm(_number(attrs.get("weight"), 0.5), _number(attrs.get("color"), 0.0), speed,
                 _number(attrs.get("opacity"), 1.0), _affine(attrs.get("coefs")), _affine(attrs.get("post")),
                 _affine(attrs.get("pre_affine")), variations, params, chaos, _number(attrs.get("var_color"), 1.0),
                 attrs.get("name", ""))


def split_variations(attrs: dict[str, str]) -> tuple[dict[str, float], dict[str, float]]:
    """An xform's attributes that aren't its fields, as `(variation weights, parameters)`: a known variation is a
    variation; a parameter that a known variation declares, or one prefixed by another attribute's name
    (`plugin_amount` beside `plugin`), is a parameter; anything else is a variation — reported by name when Iteron
    doesn't know it."""
    candidates = [k for k in attrs if k not in XFORM_FIELDS]
    names = set()
    for key in candidates:
        if resolve(key) is not None:
            names.add(key)
        elif not parameter_owner(key) and not any(key.startswith(other + "_") for other in candidates if other != key):
            names.add(key)
    variations = {k: _number(attrs[k], 0.0) for k in names if _number(attrs[k], 0.0)}
    params = {k: _number(attrs[k], 0.0) for k in candidates if k not in names}
    return variations, params


def _palette(el: ET.Element) -> list[tuple[int, int, int]]:
    palette = el.find("palette")
    if palette is not None and palette.text:
        return [tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) for h in HEX.findall(palette.text)]
    colours = sorted(el.findall("color"), key=lambda c: int(_number(c.get("index"), 0)))   # flam3's older form
    return [tuple(int(v) for v in _numbers(c.get("rgb"), 3, (0, 0, 0))) for c in colours]


def _number(text: str | None, default):
    try:
        return float(text) if text is not None else default
    except ValueError:
        return default


def _numbers(text: str | None, count: int, default: tuple) -> tuple:
    try:
        values = [float(v) for v in (text or "").split()]
    except ValueError:
        return default
    return tuple(values[:count]) if len(values) >= count else default


def _affine(text: str | None):
    values = _numbers(text, 6, None)
    return tuple(values) if values else IDENTITY
