# SPDX-License-Identifier: MIT
"""The Iteron icon and logo as Blender previews (`icon_value`).

Loaded from `iteron/icons/` (filled by the build from `branding/addon/`); when running from the repository the
branding folder is used directly, so the artwork exists in one place only.
"""

from __future__ import annotations

from pathlib import Path

import bpy.utils.previews

NAMES = ("iteron_icon", "iteron_logo")
_FOLDERS = (Path(__file__).resolve().parent.parent / "icons",
            Path(__file__).resolve().parent.parent.parent / "branding" / "addon")
_PREVIEWS = None


def icon(name: str) -> int:
    """The preview's `icon_value`, or 0 (no icon) when the image is missing."""
    if _PREVIEWS is None or name not in _PREVIEWS:
        return 0
    return _PREVIEWS[name].icon_id


def register() -> None:
    global _PREVIEWS
    _PREVIEWS = bpy.utils.previews.new()
    for name in NAMES:
        path = next((folder / f"{name}.png" for folder in _FOLDERS if (folder / f"{name}.png").is_file()), None)
        if path is not None:
            _PREVIEWS.load(name, str(path), "IMAGE")


def unregister() -> None:
    global _PREVIEWS
    if _PREVIEWS is not None:
        bpy.utils.previews.remove(_PREVIEWS)
        _PREVIEWS = None
