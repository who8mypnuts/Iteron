# SPDX-License-Identifier: MIT
"""Set a short line of text as SVG paths (so the SVG needs no fonts), using DejaVu Sans from the system.

DejaVu's licence (Bitstream Vera derivative) allows this; only the social card's tagline uses it.
"""

from __future__ import annotations

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONT_CANDIDATES = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
LETTER_SPACING = 0.04    # em


def _font() -> TTFont:
    for path in FONT_CANDIDATES:
        try:
            return TTFont(path)
        except OSError:
            continue
    raise FileNotFoundError("DejaVu Sans is needed for the tagline: " + ", ".join(FONT_CANDIDATES))


def text_paths(text: str, x: float, baseline: float, size: float, fill: str) -> str:
    """`text` as one SVG path, left-aligned at `x` on `baseline`, `size` px per em."""
    font = _font()
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    scale = size / font["head"].unitsPerEm
    pen = SVGPathPen(glyphs)
    cursor = 0.0
    for char in text:
        name = cmap.get(ord(char))
        if name is None:
            continue
        # font units → px: flip y, place at the cursor
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x + cursor, baseline)))
        cursor += glyphs[name].width * scale + LETTER_SPACING * size
    return f'<path d="{pen.getCommands()}" fill="{fill}"/>'
