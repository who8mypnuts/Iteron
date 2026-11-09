# SPDX-License-Identifier: MIT
"""The ITERON wordmark, drawn from geometry (no font needed): monoline capitals with a hexagonal O
that echoes the silhouette of the mark. Units: cap height 100, baseline at y = 100, top at y = 0.
"""

from __future__ import annotations

import math

CAP = 100.0
STROKE = 16.0
TRACKING = 24.0          # space between letters
OVERSHOOT = 3.0          # the hexagon's points rise above / sink below the cap line, as round letters do


def _rect(x0: float, y0: float, x1: float, y1: float) -> str:
    return f"M{x0:.2f},{y0:.2f}H{x1:.2f}V{y1:.2f}H{x0:.2f}Z"


def _poly(points) -> str:
    return "M" + "L".join(f"{x:.2f},{y:.2f}" for x, y in points) + "Z"


def letter_i():
    return [_rect(0, 0, STROKE, CAP)], STROKE


def letter_t():
    width = 74.0
    stem = (width - STROKE) / 2
    return [_rect(0, 0, width, STROKE), _rect(stem, 0, stem + STROKE, CAP)], width


def letter_e():
    width, middle = 60.0, 52.0
    mid = (CAP - STROKE) / 2
    return [_rect(0, 0, STROKE, CAP), _rect(0, 0, width, STROKE), _rect(0, mid, middle, mid + STROKE),
            _rect(0, CAP - STROKE, width, CAP)], width


def letter_r():
    bowl = 57.0                       # bowl height, cap line to the bottom of its lower stroke
    radius = bowl / 2
    reach = 38.0                      # where the straight part of the bowl ends
    width = reach + radius
    inner = radius - STROKE
    outer_path = f"M0,0H{reach:.2f}A{radius:.2f},{radius:.2f} 0 0 1 {reach:.2f},{bowl:.2f}H0Z"
    inner_path = (f"M{STROKE:.2f},{STROKE:.2f}H{reach:.2f}A{inner:.2f},{inner:.2f} 0 0 1 {reach:.2f},{bowl - STROKE:.2f}"
                  f"H{STROKE:.2f}Z")
    # the leg: a parallelogram from the bowl's lower stroke to the baseline, of true width STROKE
    top_y, x_top = bowl - STROKE, reach - 10.0
    x_bottom_right = width + 2.0
    dx, dy = x_bottom_right - (x_top + STROKE), CAP - top_y
    horizontal = STROKE / math.cos(math.atan2(dx, dy))
    leg = _poly([(x_top, top_y), (x_top + horizontal, top_y), (x_bottom_right, CAP), (x_bottom_right - horizontal, CAP)])
    return [_rect(0, 0, STROKE, CAP), outer_path + inner_path, leg], x_bottom_right


def letter_o():
    """A pointy-top hexagon ring — the cube's silhouette."""
    half_height = CAP / 2 + OVERSHOOT
    half_width = half_height * math.cos(math.radians(30))
    cx, cy = half_width, CAP / 2

    def ring(h):
        w = h * math.cos(math.radians(30))
        return [(cx, cy - h), (cx + w, cy - h / 2), (cx + w, cy + h / 2), (cx, cy + h), (cx - w, cy + h / 2), (cx - w, cy - h / 2)]

    inner_h = half_height - STROKE / math.cos(math.radians(30))   # keeps the vertical sides STROKE thick
    return [_poly(ring(half_height)) + _poly(list(reversed(ring(inner_h))))], 2 * half_width


def letter_n():
    width = 74.0
    dx, dy = width - 2 * STROKE, CAP
    horizontal = STROKE / math.cos(math.atan2(dx, dy))
    diagonal = _poly([(0, 0), (horizontal, 0), (width, CAP), (width - horizontal, CAP)])
    return [_rect(0, 0, STROKE, CAP), _rect(width - STROKE, 0, width, CAP), diagonal], width


LETTERS = {"I": letter_i, "T": letter_t, "E": letter_e, "R": letter_r, "O": letter_o, "N": letter_n}


def wordmark(text: str = "ITERON", o_fill: str | None = None) -> tuple[list[str], float]:
    """Path data for the word (translated per letter) and its total width. `o_fill` paints the hexagonal O
    (e.g. the brand gradient); the other letters take the group's fill."""
    paths, x = [], 0.0
    for index, char in enumerate(text):
        letter_paths, width = LETTERS[char]()
        fill = f' fill="{o_fill}"' if char == "O" and o_fill else ""
        paths.append(f'<g transform="translate({x:.2f},0)"{fill}>' + "".join(f'<path d="{d}"/>' for d in letter_paths) + "</g>")
        x += width + (TRACKING if index < len(text) - 1 else 0.0)
    return paths, x
