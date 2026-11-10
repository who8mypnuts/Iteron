# SPDX-License-Identifier: MIT
"""When the ray-marched preview is on, and hiding the mesh behind it.

While the preview draws an object, the object shows as its bounds (the stale mesh would otherwise fight with it);
the display type it had is kept in `saved_display` and put back afterwards. Before a file is saved every object gets
its own display type back, so `.blend` files never keep the temporary one.
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from .state import is_fractal, is_stale


def overlay_active(obj) -> bool:
    """Whether the viewport draws `obj` ray-marched right now."""
    if not is_fractal(obj) or obj.mode == "EDIT" or obj.iteron.kind == "FLAME":
        return False
    mode = obj.iteron.preview
    if mode == "RAYMARCH":
        return True
    if mode == "AUTO":
        from ..jobs.scheduler import SCHEDULER
        return is_stale(obj) or SCHEDULER.busy(obj)
    return False


def sync(obj, showing: bool | None = None) -> None:
    """Show the bounds while the preview draws the object, its own display type otherwise."""
    if obj is None or obj.type != "MESH":
        return
    s = obj.iteron
    showing = overlay_active(obj) if showing is None else showing
    if showing and obj.display_type != "BOUNDS":
        s.saved_display = obj.display_type
        obj.display_type = "BOUNDS"
    elif not showing and s.saved_display:
        obj.display_type = s.saved_display
        s.saved_display = ""


def sync_all(showing: bool | None = None) -> None:
    for obj in bpy.data.objects:
        if obj.type == "MESH" and (obj.iteron.is_fractal or obj.iteron.saved_display):
            sync(obj, showing)


@persistent
def _before_save(*_args) -> None:
    sync_all(showing=False)


@persistent
def _after_save_or_load(*_args) -> None:
    sync_all()


_HANDLERS = ((bpy.app.handlers.save_pre, _before_save), (bpy.app.handlers.save_post, _after_save_or_load),
             (bpy.app.handlers.load_post, _after_save_or_load))


def register() -> None:
    for handlers, fn in _HANDLERS:
        if fn not in handlers:
            handlers.append(fn)


def unregister() -> None:
    sync_all(showing=False)
    for handlers, fn in _HANDLERS:
        if fn in handlers:
            handlers.remove(fn)
