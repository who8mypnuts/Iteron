# SPDX-License-Identifier: MIT
"""Rebuild the preview, build the final mesh (Esc cancels), cancel."""

from __future__ import annotations

import bpy

from ..bridge.state import final_estimate, is_fractal
from ..jobs.scheduler import SCHEDULER
from ..prefs import preferences


class _FractalOperator:
    @classmethod
    def poll(cls, context):
        return is_fractal(context.active_object)


class ITERON_OT_rebuild(_FractalOperator, bpy.types.Operator):
    """Rebuild the preview mesh now"""
    bl_idname = "iteron.rebuild"
    bl_label = "Rebuild Preview"

    def execute(self, context):
        obj = context.active_object
        if bpy.app.background:
            SCHEDULER.run_now(obj)
        else:
            SCHEDULER.request(obj)
        return {"FINISHED"}


class ITERON_OT_build_final(_FractalOperator, bpy.types.Operator):
    """Build the mesh at the Final resolution (Esc cancels)"""
    bl_idname = "iteron.build_final"
    bl_label = "Build Final"

    _timer = None

    def _check(self, obj) -> bool:
        limit = preferences().max_resolution
        if obj.iteron.final_resolution > limit:
            self.report({"ERROR"}, f"Final resolution is above the limit set in the preferences ({limit})")
            return False
        return True

    def execute(self, context):
        obj = context.active_object
        if not self._check(obj):
            return {"CANCELLED"}
        SCHEDULER.run_now(obj, final=True)
        return {"FINISHED"}

    def invoke(self, context, _event):
        obj = context.active_object
        if not self._check(obj):
            return {"CANCELLED"}
        if bpy.app.background:
            return self.execute(context)
        SCHEDULER.request(obj, final=True)
        self._object = obj
        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        estimate = final_estimate(obj)
        about = f" (about {estimate[0] / 1e6:.1f} M faces)" if estimate else ""
        context.workspace.status_text_set(f"Iteron: building {obj.name} at {obj.iteron.final_resolution}{about} "
                                          "— Esc to cancel")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC":
            SCHEDULER.cancel(self._object)
            self._end(context)
            self.report({"INFO"}, "Build cancelled")
            return {"CANCELLED"}
        if event.type == "TIMER" and not SCHEDULER.busy(self._object):
            self._end(context)
            return {"FINISHED"}
        return {"PASS_THROUGH"}

    def _end(self, context):
        context.window_manager.event_timer_remove(self._timer)
        context.workspace.status_text_set(None)


class ITERON_OT_cancel(_FractalOperator, bpy.types.Operator):
    """Stop the build in progress; the current mesh is kept"""
    bl_idname = "iteron.cancel"
    bl_label = "Cancel Build"

    def execute(self, context):
        SCHEDULER.cancel(context.active_object)
        return {"FINISHED"}


classes = (ITERON_OT_rebuild, ITERON_OT_build_final, ITERON_OT_cancel)
