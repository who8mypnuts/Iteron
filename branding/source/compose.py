# SPDX-License-Identifier: MIT
"""Lock-ups built from the mark and the wordmark: the horizontal logo, the app icon and the social card."""

from __future__ import annotations

from mark import mark_group
from palette import INK_DARK, INK_LIGHT, MUTED, NIGHT, NIGHT_GLOW, SWEEP
from tagline import text_paths
from wordmark import CAP, wordmark

SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.2f} {h:.2f}">'


def _o_gradient(gid: str) -> str:
    """The brand sweep across the hexagonal O, in wordmark units (top point to bottom point)."""
    stops = "".join(f'<stop offset="{offset:.2f}" stop-color="{colour}"/>' for offset, colour in SWEEP)
    return f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="0" y1="-3" x2="0" y2="103">{stops}</linearGradient>'


def _word(x: float, y: float, cap: float, ink: str, gid: str) -> tuple[str, str]:
    """(defs, group) for ITERON with its cap height `cap` and top-left at (x, y); the O wears the brand sweep."""
    letters, _width = wordmark(o_fill=f"url(#{gid})")
    return _o_gradient(gid), (f'<g transform="translate({x:.2f},{y:.2f}) scale({cap / CAP:.5f})" fill="{ink}" '
                              f'fill-rule="evenodd">' + "".join(letters) + "</g>")


def _placed_mark(level: int, x: float, y: float, height: float, prefix: str) -> tuple[str, str]:
    """(defs, group) for the mark scaled to `height` with its top-left at (x, y)."""
    defs, body, (x0, y0, x1, y1) = mark_group(level, prefix)
    scale = height / (y1 - y0)
    return defs, f'<g transform="translate({x:.2f},{y:.2f}) scale({scale:.5f}) translate({-x0:.4f},{-y0:.4f})">{body}</g>'


def mark_width(height: float, level: int = 2) -> float:
    _defs, _body, (x0, y0, x1, y1) = mark_group(level)
    return height * (x1 - x0) / (y1 - y0)


def logo_svg(ink: str, height: float = 160.0) -> str:
    """Mark + ITERON, side by side; `ink` colours the letters (INK_LIGHT on dark backgrounds, INK_DARK on light)."""
    pad = height * 0.08
    mark_h = height - 2 * pad
    _letters, word_w = wordmark()
    cap = mark_h * 0.46                              # cap height of the word relative to the mark
    gap = mark_h * 0.26
    mw = mark_width(mark_h)
    width = pad + mw + gap + word_w * cap / CAP + pad
    defs, mark = _placed_mark(2, pad, pad, mark_h, "lg")
    word_defs, word = _word(pad + mw + gap, (height - cap) / 2, cap, ink, "lg-o")
    return SVG.format(w=width, h=height) + f"<title>Iteron</title><defs>{defs}{word_defs}</defs>{mark}{word}</svg>\n"


def _glow(cx: float, cy: float, r: float, gid: str) -> tuple[str, str]:
    grad = (f'<radialGradient id="{gid}" cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="{NIGHT_GLOW}"/><stop offset="1" stop-color="{NIGHT}" stop-opacity="0"/></radialGradient>')
    return grad, f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="url(#{gid})"/>'


def app_icon_svg(side: float = 1024.0, level: int = 2) -> str:
    """The mark on a rounded night-blue tile with a soft glow: avatars, the GitHub org icon, launchers."""
    radius = side * 0.22
    mark_h = side * 0.72
    x = (side - mark_width(mark_h, level)) / 2
    defs, mark = _placed_mark(level, x, (side - mark_h) / 2, mark_h, "ai")
    glow_def, glow = _glow(side / 2, side / 2, side * 0.55, "ai-glow")
    return (SVG.format(w=side, h=side) + f"<title>Iteron</title><defs>{defs}{glow_def}</defs>"
            f'<rect width="{side}" height="{side}" rx="{radius:.1f}" fill="{NIGHT}"/>{glow}{mark}</svg>\n')


def social_svg(width: float = 1280.0, height: float = 640.0) -> str:
    """The GitHub social preview (1280 × 640): mark, wordmark and tagline on night blue."""
    mark_h = height * 0.56
    mw = mark_width(mark_h)
    _letters, word_w = wordmark()
    cap = height * 0.16
    word_px = word_w * cap / CAP
    gap = height * 0.09
    block_w = mw + gap + word_px
    x0 = (width - block_w) / 2
    mark_y = (height - mark_h) / 2
    defs, mark = _placed_mark(2, x0, mark_y, mark_h, "sc")
    glow_def, glow = _glow(x0 + mw / 2, height / 2, height * 0.62, "sc-glow")
    wx = x0 + mw + gap
    wy = height / 2 - cap * 0.78
    word_defs, word = _word(wx, wy, cap, INK_LIGHT, "sc-o")
    tag_size = cap * 0.30
    tagline = text_paths("3D fractals for Blender", wx + cap * 0.02, wy + cap + tag_size * 2.3, tag_size, MUTED)
    return (SVG.format(w=width, h=height) + f"<title>Iteron — 3D fractals for Blender</title><defs>{defs}{glow_def}{word_defs}</defs>"
            f'<rect width="{width}" height="{height}" fill="{NIGHT}"/>{glow}{mark}{word}{tagline}</svg>\n')


__all__ = ["logo_svg", "app_icon_svg", "social_svg", "mark_width", "INK_DARK", "INK_LIGHT"]
