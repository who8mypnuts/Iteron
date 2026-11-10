# SPDX-License-Identifier: MIT
"""Bake Animation (the Final mesh of every frame in the scene's range, kept per frame) and Clear Bake. In the UI
the bake runs frame by frame through the scheduler (Esc cancels and drops what was baked); in background mode
(farms, scripts) it runs synchronously."""

from __future__ import annotations

import bpy

from ..bridge import animation
from ..bridge.state import is_fractal
from ..jobs.scheduler import SCHEDULER


class _Operator:
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return is_fractal(context.active_object)


class ITERON_OT_bake_animation(_Operator, bpy.types.Operator):
    """Build the Final mesh for every frame of the scene's range and keep them: playback and renders swap meshes
    instead of rebuilding (animated parameters, render farms)"""
    bl_idname = "iteron.bake_animation"
    bl_label = "Bake Animation"

    def _start(self, context):
        scene = context.scene
        self._object, self._return = context.active_object, scene.frame_current
        self._frames = list(range(scene.frame_start, scene.frame_end + 1))
        animation.begin(self._object)
        scene.render.use_lock_interface = True          # renders then read the swapped meshes safely

    def _frame(self, context, frame: int) -> None:
        context.scene.frame_set(frame)
        self._object.data = self._object.iteron.live_mesh

    def _finish(self, context) -> None:
        context.scene.frame_set(self._return)
        animation.end(self._object, self._return)

    def execute(self, context):
        self._start(context)
        for frame in self._frames:
            self._frame(context, frame)
            SCHEDULER.run_now(self._object, final=True)
            animation.store(self._object, frame)
        self._finish(context)
        self.report({"INFO"}, f"Baked {len(self._frames)} frames")
        return {"FINISHED"}

    def invoke(self, context, _event):
        if bpy.app.background:
            return self.execute(context)
        self._start(context)
        self._index, self._waiting = 0, False
        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC":
            SCHEDULER.cancel(self._object)
            self._stop(context)
            animation.clear(self._object)
            self.report({"INFO"}, "Bake cancelled")
            return {"CANCELLED"}
        if event.type != "TIMER" or SCHEDULER.busy(self._object):
            return {"PASS_THROUGH"}
        if self._waiting:                                   # the frame's build finished
            animation.store(self._object, self._frames[self._index])
            self._index, self._waiting = self._index + 1, False
        if self._index == len(self._frames):
            self._stop(context)
            self.report({"INFO"}, f"Baked {len(self._frames)} frames")
            return {"FINISHED"}
        self._frame(context, self._frames[self._index])
        SCHEDULER.request(self._object, final=True)
        self._waiting = True
        context.workspace.status_text_set(f"Iteron: baking {self._object.name}, frame {self._frames[self._index]} "
                                          f"({self._index + 1}/{len(self._frames)}) — Esc to cancel")
        return {"PASS_THROUGH"}

    def _stop(self, context) -> None:
        context.window_manager.event_timer_remove(self._timer)
        context.workspace.status_text_set(None)
        self._finish(context)


class ITERON_OT_clear_bake(_Operator, bpy.types.Operator):
    """Drop the baked meshes; the fractal rebuilds live again"""
    bl_idname = "iteron.clear_bake"
    bl_label = "Clear Bake"

    @classmethod
    def poll(cls, context):
        return super().poll(context) and animation.baked(context.active_object)

    def execute(self, context):
        obj = context.active_object
        animation.clear(obj)
        from ..bridge.state import params_changed
        params_changed(obj)
        return {"FINISHED"}


classes = (ITERON_OT_bake_animation, ITERON_OT_clear_bake)
