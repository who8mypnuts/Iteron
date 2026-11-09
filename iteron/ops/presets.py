# SPDX-License-Identifier: MIT
"""Apply one of the formula's presets, or reset it to its defaults."""

import bpy
from bpy.props import EnumProperty

from ..bridge.props import reset_values, write_values
from ..bridge.state import is_fractal
from ..core.formula import REGISTRY

_ITEMS_CACHE: list = []          # Blender needs the dynamic enum items kept alive


def _preset_items(_self, context):
    obj = context.active_object if context else None
    entry = REGISTRY.get(obj.iteron.formula) if is_fractal(obj) else None
    _ITEMS_CACHE[:] = [(name, name, f"Apply the {name} preset") for name in (entry.presets if entry else {})]
    return _ITEMS_CACHE or [("", "(none)", "")]


class ITERON_OT_apply_preset(bpy.types.Operator):
    """Set the formula's parameters to a preset"""
    bl_idname = "iteron.apply_preset"
    bl_label = "Apply Preset"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "preset"

    preset: EnumProperty(name="Preset", items=_preset_items)

    @classmethod
    def poll(cls, context):
        return is_fractal(context.active_object)

    def execute(self, context):
        settings = context.active_object.iteron
        entry = REGISTRY[settings.formula]
        reset_values(settings)
        write_values(settings, entry.presets.get(self.preset, {}))
        return {"FINISHED"}


class ITERON_OT_reset_formula(bpy.types.Operator):
    """Reset every parameter of the formula to its default"""
    bl_idname = "iteron.reset_formula"
    bl_label = "Reset Parameters"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return is_fractal(context.active_object)

    def execute(self, context):
        reset_values(context.active_object.iteron)
        return {"FINISHED"}


classes = (ITERON_OT_apply_preset, ITERON_OT_reset_formula)
