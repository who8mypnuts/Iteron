# SPDX-License-Identifier: MIT
"""Iteron's default colours: the brand sweep every new fractal's ramp starts with (branding/source/palette.py)."""

from __future__ import annotations

import numpy as np

SWEEP = ((0.00, "#1FF0FF"), (0.30, "#2F9BFF"), (0.55, "#6A4DFF"), (0.80, "#B23CFF"), (1.00, "#FF3F93"))


def srgb(hex_colour: str) -> tuple[float, float, float]:
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def linear(hex_colour: str) -> tuple[float, float, float, float]:
    """sRGB hex → scene-linear RGBA (Blender's ramp colours are linear)."""
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (*(channel(c) for c in srgb(hex_colour)), 1.0)


def sweep(values: np.ndarray) -> np.ndarray:
    """`(N, 3)` sRGB colours of the sweep at `values` in 0…1."""
    stops = np.array([p for p, _h in SWEEP])
    colours = np.array([srgb(h) for _p, h in SWEEP])
    v = np.clip(np.asarray(values, dtype=np.float64), 0.0, 1.0)
    return np.stack([np.interp(v, stops, colours[:, c]) for c in range(3)], axis=-1)
