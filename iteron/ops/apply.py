# SPDX-License-Identifier: MIT
"""Apply as Plain Mesh: freeze the current mesh and detach the object from Iteron."""

from __future__ import annotations

import bpy

from ..bridge.state import is_fractal
from ..jobs.scheduler import SCHEDULER


class ITERON_OT_apply_mesh(bpy.types.Operator):
    """Keep the current mesh and material as an ordinary object; Iteron stops rebuilding it"""
    bl_idname = "iteron.apply_mesh"
    bl_label = "Apply as Plain Mesh"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return is_fractal(context.active_object)

    def execute(self, context):
        obj = context.active_object
        SCHEDULER.cancel(obj)
        obj.iteron.is_fractal = False
        obj.iteron.built_hash = ""
        self.report({"INFO"}, f"{obj.name} is now a plain mesh")
        return {"FINISHED"}


classes = (ITERON_OT_apply_mesh,)
