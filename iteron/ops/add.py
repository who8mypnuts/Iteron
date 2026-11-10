# SPDX-License-Identifier: MIT
"""Add a fractal (a formula) or a flame at the 3D cursor."""

import json

import bpy
from bpy.props import EnumProperty

from ..bridge import material
from ..bridge.props import FORMULA_ITEMS
from ..core.formula import REGISTRY
from ..flames.library import bundled
from ..jobs.scheduler import SCHEDULER


def new_object(context, name: str):
    """An empty Iteron mesh object at the 3D cursor, linked, selected and active."""
    obj = bpy.data.objects.new(name, bpy.data.meshes.new(name))
    context.collection.objects.link(obj)
    obj.location = context.scene.cursor.location
    for other in context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    obj.iteron.is_fractal = True
    return obj


def build_first(obj) -> None:
    """Schedule the first build (run it at once in background mode, where nothing ticks)."""
    if bpy.app.background:
        SCHEDULER.run_now(obj)
    else:
        SCHEDULER.request(obj)


def add_fractal(context, formula_id: str):
    entry = REGISTRY[formula_id]
    obj = new_object(context, entry.name)
    obj.iteron.formula = formula_id
    obj.iteron.surface_offset = entry.surface_offset
    material.ensure(obj)
    build_first(obj)
    return obj


def add_flame(context, flame: dict, output: str = "POINTS", **settings):
    """A flame object from Fractalchemy's flame dict; `settings` set `obj.iteron.flame` fields (points, threshold…)."""
    obj = new_object(context, flame.get("name") or "Flame")
    obj.iteron.kind = "FLAME"
    f = obj.iteron.flame
    f.source = json.dumps(flame)
    f.output = output
    for key, value in settings.items():
        setattr(f, key, value)
    material.ensure_flame(obj)
    build_first(obj)
    return obj


def _flame_items(_self, _context):
    _FLAMES[:] = [(key, flame.get("name", key), f"Add the {flame.get('name', key)} flame")
                  for key, flame in bundled().items()]
    return _FLAMES


_FLAMES: list = []


class _AddOperator:
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        self.add(context)
        return {"FINISHED"}


class ITERON_OT_add_fractal(_AddOperator, bpy.types.Operator):
    """Add an Iteron fractal at the 3D cursor"""
    bl_idname = "iteron.add_fractal"
    bl_label = "Add Fractal"

    formula: EnumProperty(name="Formula", items=FORMULA_ITEMS, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, _context, properties):
        entry = REGISTRY.get(properties.formula)
        return f"Add a {entry.name}: {entry.description}" if entry else cls.__doc__

    def add(self, context):
        add_fractal(context, self.formula)


class ITERON_OT_add_flame(_AddOperator, bpy.types.Operator):
    """Add one of Iteron's fractal flames at the 3D cursor"""
    bl_idname = "iteron.add_flame"
    bl_label = "Add Flame"

    flame: EnumProperty(name="Flame", items=_flame_items, options={"SKIP_SAVE"})

    def add(self, context):
        add_flame(context, bundled()[self.flame])


classes = (ITERON_OT_add_fractal, ITERON_OT_add_flame)
