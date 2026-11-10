# SPDX-License-Identifier: MIT
"""Presets: apply a built-in or saved one, save the current parameters, delete a saved one, reset."""

import bpy
from bpy.props import EnumProperty, StringProperty

from ..bridge import presets as user
from ..bridge.props import read_values, reset_values, write_values
from ..bridge.state import is_fractal
from ..core.formula import REGISTRY

_ITEMS_CACHE: list = []          # Blender needs dynamic enum items kept alive
_USER_CACHE: list = []


def _formula(context):
    obj = context.active_object if context else None
    return REGISTRY.get(obj.iteron.formula) if is_fractal(obj) else None


def _preset_items(_self, context):
    entry = _formula(context)
    items = [(name, name, f"Apply the built-in {name} preset") for name in (entry.presets if entry else {})]
    saved = user.user_presets(entry.id) if entry else []
    if saved:
        items.append(None)                                      # a separator before your own
        items += [(user.USER_PREFIX + name, name, f"Apply your preset {name}") for name in saved]
    _ITEMS_CACHE[:] = items
    return _ITEMS_CACHE or [("", "(none)", "")]


def _user_items(_self, context):
    entry = _formula(context)
    _USER_CACHE[:] = [(name, name, f"Delete your preset {name}") for name in (user.user_presets(entry.id) if entry else [])]
    return _USER_CACHE or [("", "(no saved presets)", "")]


class _FractalOperator:
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return is_fractal(context.active_object)


class ITERON_OT_apply_preset(_FractalOperator, bpy.types.Operator):
    """Set the formula's parameters to a preset"""
    bl_idname = "iteron.apply_preset"
    bl_label = "Apply Preset"
    bl_property = "preset"

    preset: EnumProperty(name="Preset", items=_preset_items)

    def execute(self, context):
        settings = context.active_object.iteron
        if self.preset.startswith(user.USER_PREFIX):
            values = user.load(settings.formula, self.preset[len(user.USER_PREFIX):])
        else:
            values = REGISTRY[settings.formula].presets.get(self.preset, {})
        reset_values(settings)
        write_values(settings, values)
        return {"FINISHED"}


class ITERON_OT_save_preset(_FractalOperator, bpy.types.Operator):
    """Save the formula's current parameters as a preset of your own"""
    bl_idname = "iteron.save_preset"
    bl_label = "Save Preset"

    name: StringProperty(name="Name", default="My Preset")

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        settings = context.active_object.iteron
        path = user.save(settings.formula, self.name, read_values(settings))
        self.report({"INFO"}, f"Saved preset {path.stem}")
        return {"FINISHED"}


class ITERON_OT_delete_preset(_FractalOperator, bpy.types.Operator):
    """Delete one of your saved presets"""
    bl_idname = "iteron.delete_preset"
    bl_label = "Delete Preset"
    bl_property = "preset"

    preset: EnumProperty(name="Preset", items=_user_items)

    def execute(self, context):
        if self.preset:
            user.delete(context.active_object.iteron.formula, self.preset)
        return {"FINISHED"}


class ITERON_OT_reset_formula(_FractalOperator, bpy.types.Operator):
    """Reset every parameter of the formula to its default"""
    bl_idname = "iteron.reset_formula"
    bl_label = "Reset Parameters"

    def execute(self, context):
        reset_values(context.active_object.iteron)
        return {"FINISHED"}


classes = (ITERON_OT_apply_preset, ITERON_OT_save_preset, ITERON_OT_delete_preset, ITERON_OT_reset_formula)
