# SPDX-License-Identifier: MIT
"""The Iteron icon, the logo and the formula thumbnails as Blender previews (`icon_value`).

The icon and logo come from `iteron/icons/` (filled by the build from `branding/addon/`; from a checkout the branding
folder is read directly, so the artwork exists in one place only). Thumbnails are `iteron/thumbnails/<formula>.png`
(rendered by tools/render_thumbnails.py) and are named `thumb_<formula>`.
"""

from __future__ import annotations

from pathlib import Path

import bpy.utils.previews

PACKAGE = Path(__file__).resolve().parent.parent
NAMES = ("iteron_icon", "iteron_logo")
_FOLDERS = (PACKAGE / "icons", PACKAGE.parent / "branding" / "addon")
THUMBNAILS = PACKAGE / "thumbnails"
_PREVIEWS = None


def icon(name: str) -> int:
    """The preview's `icon_value`, or 0 (no icon) when the image is missing."""
    if _PREVIEWS is None or name not in _PREVIEWS:
        return 0
    return _PREVIEWS[name].icon_id


def thumbnail(formula_id: str) -> int:
    return icon(f"thumb_{formula_id}")


def register() -> None:
    global _PREVIEWS
    _PREVIEWS = bpy.utils.previews.new()
    for name in NAMES:
        path = next((folder / f"{name}.png" for folder in _FOLDERS if (folder / f"{name}.png").is_file()), None)
        if path is not None:
            _PREVIEWS.load(name, str(path), "IMAGE")
    for path in sorted(THUMBNAILS.glob("*.png")):
        _PREVIEWS.load(f"thumb_{path.stem}", str(path), "IMAGE")


def unregister() -> None:
    global _PREVIEWS
    if _PREVIEWS is not None:
        bpy.utils.previews.remove(_PREVIEWS)
        _PREVIEWS = None
