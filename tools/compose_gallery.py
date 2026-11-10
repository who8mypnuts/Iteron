# SPDX-License-Identifier: MIT
"""Lay the thumbnails (iteron/thumbnails/) out as docs/images/gallery.png for the README. Plain Python + Pillow.

    python tools/compose_gallery.py
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
COLUMNS, CELL, CAPTION, GAP = 5, 256, 30, 6
NIGHT, INK = (11, 12, 24), (201, 207, 234)


def font(size: int):
    for name in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> int:
    import iteron.formulas  # noqa: F401  (registers the formulas)
    from iteron.core.formula import by_family
    entries = [e for _family, members in by_family() for e in members]
    rows = -(-len(entries) // COLUMNS)
    sheet = Image.new("RGB", (COLUMNS * (CELL + GAP) + GAP, rows * (CELL + CAPTION + GAP) + GAP), NIGHT)
    draw, text_font = ImageDraw.Draw(sheet), font(15)
    for index, entry in enumerate(entries):
        x = GAP + (index % COLUMNS) * (CELL + GAP)
        y = GAP + (index // COLUMNS) * (CELL + CAPTION + GAP)
        path = ROOT / "iteron" / "thumbnails" / f"{entry.id}.png"
        if path.is_file():
            thumb = Image.open(path).convert("RGBA").resize((CELL, CELL), Image.LANCZOS)
            sheet.paste(thumb, (x, y), thumb)
        width = draw.textlength(entry.name, font=text_font)
        draw.text((x + (CELL - width) / 2, y + CELL + 6), entry.name, fill=INK, font=text_font)
    out = ROOT / "docs" / "images" / "gallery.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, optimize=True)
    print(out, f"{len(entries)} formulas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
