# SPDX-License-Identifier: MIT
"""Animation. Keyframed parameters change without their update callbacks firing, so a frame-change handler
rebuilds the preview of any fractal whose shape no longer matches its mesh. For renders (and farms), *Bake
Animation* builds the Final mesh of every frame into a mesh of its own; a baked object swaps meshes on frame
change (before evaluation, so renders see it too) instead of rebuilding, and live rebuilds stop until the bake is
cleared. The live mesh is kept aside and comes back when it is."""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent
from bpy.props import IntProperty, PointerProperty
from bpy.types import PropertyGroup

BAKING: set[int] = set()          # session uids of objects being baked: the handlers leave them alone


class IteronBakedFrame(PropertyGroup):
    frame: IntProperty()
    mesh: PointerProperty(type=bpy.types.Mesh)


def baked(obj) -> bool:
    return len(obj.iteron.baked) > 0


def frame_range(obj) -> tuple[int, int]:
    frames = [item.frame for item in obj.iteron.baked]
    return min(frames), max(frames)


def mesh_for(obj, frame: int):
    """The baked mesh for `frame` (the first or last one outside the baked range)."""
    items = sorted(obj.iteron.baked, key=lambda item: item.frame)
    chosen = next((item for item in reversed(items) if item.frame <= frame), items[0])
    return chosen.mesh


def show(obj, frame: int) -> None:
    mesh = mesh_for(obj, frame)
    if mesh is not None and obj.data != mesh:
        obj.data = mesh


def begin(obj) -> None:
    """Start baking `obj`: any old bake goes, the live mesh is remembered."""
    clear(obj)
    obj.iteron.live_mesh = obj.data
    BAKING.add(obj.session_uid)


def store(obj, frame: int):
    """Keep a copy of the mesh just built as `frame`'s."""
    mesh = obj.iteron.live_mesh.copy()
    mesh.name = f"{obj.name} · frame {frame}"
    item = obj.iteron.baked.add()
    item.frame, item.mesh = frame, mesh
    return mesh


def end(obj, frame: int) -> None:
    BAKING.discard(obj.session_uid)
    if baked(obj):
        show(obj, frame)


def clear(obj) -> None:
    """Drop the baked meshes and put the live mesh back."""
    s = obj.iteron
    if s.live_mesh is not None and obj.data != s.live_mesh:
        obj.data = s.live_mesh
    for item in s.baked:
        if item.mesh is not None and item.mesh != s.live_mesh and item.mesh.users <= 1:
            bpy.data.meshes.remove(item.mesh)
    s.baked.clear()


def _fractals(scene):
    return [o for o in scene.objects if o.type == "MESH" and o.iteron.is_fractal and o.session_uid not in BAKING]


@persistent
def _swap_baked(scene, _depsgraph=None) -> None:
    for obj in _fractals(scene):
        if baked(obj):
            show(obj, scene.frame_current)


@persistent
def _rebuild_animated(scene, _depsgraph=None) -> None:
    if bpy.app.is_job_running("RENDER") or BAKING:
        return
    from ..jobs.scheduler import SCHEDULER
    from .state import is_stale
    for obj in _fractals(scene):
        s = obj.iteron
        if not baked(obj) and s.live and s.preview != "RAYMARCH" and obj.animation_data and is_stale(obj):
            SCHEDULER.request(obj)


_HANDLERS = ((bpy.app.handlers.frame_change_pre, _swap_baked), (bpy.app.handlers.frame_change_post, _rebuild_animated))
classes = (IteronBakedFrame,)


def register_extra() -> None:
    for handlers, fn in _HANDLERS:
        if fn not in handlers:
            handlers.append(fn)


def unregister_extra() -> None:
    BAKING.clear()
    for handlers, fn in _HANDLERS:
        if fn in handlers:
            handlers.remove(fn)
