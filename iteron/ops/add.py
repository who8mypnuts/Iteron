# SPDX-License-Identifier: MIT
"""Add a fractal object at the 3D cursor."""

import bpy
from bpy.props import EnumProperty

from ..bridge import material
from ..bridge.props import FORMULA_ITEMS
from ..core.formula import REGISTRY
from ..jobs.scheduler import SCHEDULER


def add_fractal(context, formula_id: str):
    """Create the object, select it, and schedule (or, in background mode, run) its first build."""
    entry = REGISTRY[formula_id]
    mesh = bpy.data.meshes.new(entry.name)
    obj = bpy.data.objects.new(entry.name, mesh)
    context.collection.objects.link(obj)
    obj.location = context.scene.cursor.location
    obj.iteron.is_fractal = True
    obj.iteron.formula = formula_id
    obj.iteron.surface_offset = entry.surface_offset
    material.ensure(obj)
    for other in context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    if bpy.app.background:
        SCHEDULER.run_now(obj)
    else:
        SCHEDULER.request(obj)
    return obj


class ITERON_OT_add_fractal(bpy.types.Operator):
    """Add an Iteron fractal at the 3D cursor"""
    bl_idname = "iteron.add_fractal"
    bl_label = "Add Fractal"
    bl_options = {"REGISTER", "UNDO"}

    formula: EnumProperty(name="Formula", items=FORMULA_ITEMS, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, _context, properties):
        entry = REGISTRY.get(properties.formula)
        return f"Add a {entry.name}: {entry.description}" if entry else cls.__doc__

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        add_fractal(context, self.formula)
        return {"FINISHED"}


classes = (ITERON_OT_add_fractal,)
