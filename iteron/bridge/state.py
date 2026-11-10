# SPDX-License-Identifier: MIT
"""Which fractal objects need rebuilding, and the handlers that notice.

A build stores a hash of everything that shapes the mesh (`built_hash`). Undo restores the parameters and the mesh
together, so after an undo the two still agree unless the step being undone was only half done; anything whose
hash no longer matches is rebuilt (when *Live* is on). Opening a file never rebuilds anything.
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from ..core.grid import estimate_bytes, estimate_faces


def shape_hash(obj) -> str:
    """A digest of everything that shapes the mesh (not the resolution: preview and final are the same shape)."""
    from .kinds import kind_of
    return kind_of(obj).shape_hash(obj)


def is_fractal(obj) -> bool:
    return obj is not None and obj.type == "MESH" and obj.iteron.is_fractal


def is_stale(obj) -> bool:
    return is_fractal(obj) and obj.iteron.built_hash != shape_hash(obj)


def final_estimate(obj) -> tuple[int, int] | None:
    """About `(faces, bytes)` for Build Final, scaled from the current mesh (None before the first build)."""
    s = obj.iteron
    if not s.built_faces or not s.built_resolution:
        return None
    faces = estimate_faces(s.built_faces, s.built_resolution, s.final_resolution)
    return faces, estimate_bytes(faces)


def params_changed(obj) -> None:
    """A parameter was edited: schedule a live rebuild (not when the preview is ray-marched only) and show the
    ray-marched preview meanwhile."""
    from ..jobs.scheduler import SCHEDULER
    from .animation import BAKING, baked
    from .display import sync
    if not is_fractal(obj) or obj.session_uid in BAKING:
        return
    if baked(obj):
        obj.iteron.message = "Baked: clear the bake to rebuild"
        return
    if obj.iteron.live and obj.mode != "EDIT" and obj.iteron.preview != "RAYMARCH":
        SCHEDULER.request(obj)
    sync(obj)


def formula_changed(obj) -> None:
    """A new formula: take its recommended surface offset (this also schedules the rebuild)."""
    from ..core.formula import REGISTRY
    if is_fractal(obj) and obj.iteron.kind == "FORMULA":
        obj.iteron.surface_offset = REGISTRY[obj.iteron.formula].surface_offset
    params_changed(obj)


@persistent
def _after_undo(_scene, _depsgraph=None) -> None:
    for obj in bpy.data.objects:
        if is_stale(obj) and obj.iteron.live:
            params_changed(obj)


@persistent
def _before_load(_file, _unused=None) -> None:
    from ..jobs.scheduler import SCHEDULER
    SCHEDULER.reset()


_HANDLERS = ((bpy.app.handlers.undo_post, _after_undo), (bpy.app.handlers.redo_post, _after_undo),
             (bpy.app.handlers.load_pre, _before_load))


def register() -> None:
    for handlers, fn in _HANDLERS:
        if fn not in handlers:
            handlers.append(fn)


def unregister() -> None:
    for handlers, fn in _HANDLERS:
        if fn in handlers:
            handlers.remove(fn)
