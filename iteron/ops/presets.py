# SPDX-License-Identifier: MIT
"""Presets: apply a built-in or saved one, save the current parameters, delete a saved one, reset. The same
operators serve built-in formulas and fragments (whose presets are their `#preset` blocks)."""

import bpy
from bpy.props import EnumProperty, StringProperty

from ..bridge import presets as user
from ..bridge.kinds import kind_of
from ..bridge.state import is_fractal

_ITEMS_CACHE: list = []          # Blender needs dynamic enum items kept alive
_USER_CACHE: list = []


def _entry(context):
    obj = context.active_object if context else None
    if not is_fractal(obj) or obj.iteron.kind == "FLAME":
        return None
    try:
        return kind_of(obj).entry(obj)
    except ValueError:              # a fragment that doesn't parse
        return None


def _preset_items(_self, context):
    entry = _entry(context)
    items = [(name, name, f"Apply the built-in {name} preset") for name in (entry.presets if entry else {})]
    saved = user.user_presets(entry.id) if entry else []
    if saved:
        items.append(None)                                      # a separator before your own
        items += [(user.USER_PREFIX + name, name, f"Apply your preset {name}") for name in saved]
    _ITEMS_CACHE[:] = items
    return _ITEMS_CACHE or [("", "(none)", "")]


def _user_items(_self, context):
    entry = _entry(context)
    _USER_CACHE[:] = [(name, name, f"Delete your preset {name}") for name in (user.user_presets(entry.id) if entry else [])]
    return _USER_CACHE or [("", "(no saved presets)", "")]


def reset(obj) -> None:
    kind = kind_of(obj)
    kind.write(obj, kind.entry(obj).values())


class _FractalOperator:
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _entry(context) is not None


class ITERON_OT_apply_preset(_FractalOperator, bpy.types.Operator):
    """Set the parameters to a preset"""
    bl_idname = "iteron.apply_preset"
    bl_label = "Apply Preset"
    bl_property = "preset"

    preset: EnumProperty(name="Preset", items=_preset_items)

    def execute(self, context):
        obj, entry = context.active_object, _entry(context)
        if self.preset.startswith(user.USER_PREFIX):
            values = user.load(entry, self.preset[len(user.USER_PREFIX):])
        else:
            values = entry.presets.get(self.preset, {})
        reset(obj)
        kind_of(obj).write(obj, values)
        return {"FINISHED"}


class ITERON_OT_save_preset(_FractalOperator, bpy.types.Operator):
    """Save the current parameters as a preset of your own"""
    bl_idname = "iteron.save_preset"
    bl_label = "Save Preset"

    name: StringProperty(name="Name", default="My Preset")

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = context.active_object
        path = user.save(_entry(context).id, self.name, kind_of(obj).read(obj))
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
            user.delete(_entry(context).id, self.preset)
        return {"FINISHED"}


class ITERON_OT_reset_formula(_FractalOperator, bpy.types.Operator):
    """Reset every parameter to its default"""
    bl_idname = "iteron.reset_formula"
    bl_label = "Reset Parameters"

    def execute(self, context):
        reset(context.active_object)
        return {"FINISHED"}


classes = (ITERON_OT_apply_preset, ITERON_OT_save_preset, ITERON_OT_delete_preset, ITERON_OT_reset_formula)
