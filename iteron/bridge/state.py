# SPDX-License-Identifier: MIT
"""Which fractal objects need rebuilding, and the handlers that notice.

A build stores a hash of everything that shapes the mesh (`built_hash`). Undo restores the parameters and the mesh
together, so after an undo the two still agree unless the step being undone was only half done; anything whose
hash no longer matches is rebuilt (when *Live* is on). Opening a file never rebuilds anything.
"""

from __future__ import annotations

import hashlib
import json

import bpy
from bpy.app.handlers import persistent

from ..core.formula import REGISTRY
from .props import read_values


def shape_hash(obj) -> str:
    """A digest of everything that shapes the mesh (not the resolution: preview and final are the same shape)."""
    s = obj.iteron
    entry = REGISTRY[s.formula]
    key = [s.formula, entry.version, read_values(s), s.auto_fit, tuple(round(c, 9) for c in s.center), s.size,
           s.surface_offset]
    return hashlib.sha1(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()[:16]


def is_fractal(obj) -> bool:
    return obj is not None and obj.type == "MESH" and obj.iteron.is_fractal


def is_stale(obj) -> bool:
    return is_fractal(obj) and obj.iteron.built_hash != shape_hash(obj)


def params_changed(obj) -> None:
    """A parameter was edited: schedule a live rebuild."""
    from ..jobs.scheduler import SCHEDULER
    if is_fractal(obj) and obj.iteron.live and obj.mode != "EDIT":
        SCHEDULER.request(obj)


def formula_changed(obj) -> None:
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
