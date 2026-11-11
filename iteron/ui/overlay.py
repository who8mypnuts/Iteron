# SPDX-License-Identifier: MIT
"""The viewport draw callback for the live preview: every visible fractal whose preview is showing, ray-marched."""

from __future__ import annotations

import traceback

import bpy
import gpu
import numpy as np

from ..bridge.colors import ramp_lut
from ..bridge.display import overlay_active
from ..bridge.kinds import kind_of
from ..core.grid import region
from ..prefs import preferences

_HANDLE = None
_FAILED: set = set()          # (formula id, version) whose preview failed: reported once, then skipped


def box(obj) -> tuple[np.ndarray, np.ndarray]:
    """The object's sampling region (the box the preview marches in), in object space."""
    s = obj.iteron
    return region(kind_of(obj).entry(obj).bounds, s.center, s.size)


def draw_object(obj, perspective_matrix, viewport) -> None:
    from ..gpu_eval import raymarch
    s, kind = obj.iteron, kind_of(obj)
    entry = kind.entry(obj)
    key = (entry.id, entry.version)
    if key in _FAILED:
        return
    values = entry.values(kind.read(obj))
    mvp = np.array(perspective_matrix @ obj.matrix_world)
    prefs = preferences()
    try:
        raymarch.draw(entry, values, mvp, viewport, box(obj), ramp_lut(obj), s.color_mode,
                      (tuple(s.channel_lo), tuple(s.channel_hi)), prefs.preview_detail, prefs.preview_steps,
                      kind.textures(obj))
    except Exception:                   # noqa: BLE001 - a shader that doesn't compile: say so once
        _FAILED.add(key)
        raise


def _draw() -> None:
    context = bpy.context
    region_3d = context.region_data
    if region_3d is None:
        return
    try:
        viewport = gpu.state.viewport_get()
        for obj in context.visible_objects:
            if obj.type == "MESH" and overlay_active(obj):
                try:
                    draw_object(obj, region_3d.perspective_matrix, viewport)
                except ValueError:      # a fragment whose source doesn't parse: the panel says why
                    continue
    except Exception:                   # noqa: BLE001 - never break viewport drawing
        traceback.print_exc()


def register() -> None:
    global _HANDLE
    _HANDLE = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_VIEW")


def unregister() -> None:
    global _HANDLE
    if _HANDLE is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_HANDLE, "WINDOW")
        _HANDLE = None
