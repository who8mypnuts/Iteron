# SPDX-License-Identifier: MIT
"""Regenerate every Iteron branding asset from the geometry in this folder.

    pip install -r requirements.txt        (cairosvg needs the cairo library: present on most Linux / macOS setups)
    python build.py

Writes ../svg, ../png and ../addon. Everything is derived from palette.py, menger.py and wordmark.py — change a
colour or a proportion there and rebuild; never edit the outputs by hand.
"""

from __future__ import annotations

import io
from pathlib import Path

import cairosvg
from PIL import Image

from compose import INK_DARK, INK_LIGHT, app_icon_svg, logo_svg, social_svg
from mark import mark_svg

ROOT = Path(__file__).resolve().parent.parent
SVG_DIR, PNG_DIR, ADDON_DIR = ROOT / "svg", ROOT / "png", ROOT / "addon"

MARK_SIZES = (64, 128, 256, 512, 1024)
SMALL_MARK_SIZES = (16, 24, 32, 48)       # below ~48 px the level-1 sponge reads better than level 2
APP_ICON_SIZES = (180, 256, 512, 1024)
LOGO_HEIGHTS = (80, 160, 320)
FAVICON_SIZES = (16, 32, 48)


def _png(svg: str, path: Path, width: int | None = None, height: int | None = None) -> None:
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(path), output_width=width, output_height=height)


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def build() -> list[Path]:
    for folder in (SVG_DIR, PNG_DIR, ADDON_DIR):
        folder.mkdir(exist_ok=True)
    mark, small = mark_svg(2), mark_svg(1)
    sources = {
        "iteron-mark.svg": mark,
        "iteron-mark-small.svg": small,
        "iteron-logo-on-dark.svg": logo_svg(INK_LIGHT),
        "iteron-logo-on-light.svg": logo_svg(INK_DARK),
        "iteron-app-icon.svg": app_icon_svg(),
        "iteron-social-preview.svg": social_svg(),
    }
    for name, text in sources.items():
        _write(SVG_DIR / name, text)

    for size in MARK_SIZES:
        _png(mark, PNG_DIR / f"iteron-mark-{size}.png", size, size)
    for size in SMALL_MARK_SIZES:
        _png(small, PNG_DIR / f"iteron-mark-small-{size}.png", size, size)
    for size in APP_ICON_SIZES:
        _png(sources["iteron-app-icon.svg"], PNG_DIR / f"iteron-app-icon-{size}.png", size, size)
    for variant in ("on-dark", "on-light"):
        for height in LOGO_HEIGHTS:
            _png(sources[f"iteron-logo-{variant}.svg"], PNG_DIR / f"iteron-logo-{variant}-{height}.png", height=height)
    _png(sources["iteron-social-preview.svg"], PNG_DIR / "iteron-social-preview.png", 1280, 640)

    # favicon: the small mark at each size, in one .ico
    frames = [Image.open(io.BytesIO(cairosvg.svg2png(bytestring=small.encode(), output_width=s, output_height=s)))
              for s in FAVICON_SIZES]
    frames[-1].save(PNG_DIR / "favicon.ico", sizes=[(s, s) for s in FAVICON_SIZES], append_images=frames[:-1])

    # inside the add-on (copied into iteron/icons/ by the extension build): a UI icon and a large panel image
    _png(small, ADDON_DIR / "iteron_icon.png", 64, 64)
    _png(mark, ADDON_DIR / "iteron_logo.png", 256, 256)
    return sorted(p for folder in (SVG_DIR, PNG_DIR, ADDON_DIR) for p in folder.iterdir())


if __name__ == "__main__":
    for written in build():
        print(written.relative_to(ROOT))
