# SPDX-License-Identifier: MIT
"""Add-on preferences: what is set once, not per fractal."""

import bpy
from bpy.props import EnumProperty, IntProperty

PACKAGE = __package__


class IteronPreferences(bpy.types.AddonPreferences):
    bl_idname = PACKAGE

    device: EnumProperty(name="Compute Device", default="AUTO",
                         items=(("AUTO", "Automatic", "The GPU when Blender can draw with it, otherwise the CPU"),
                                ("GPU", "GPU", "Always try the GPU first (falls back to the CPU on failure)"),
                                ("CPU", "CPU", "numpy on the CPU: slower, float64, works everywhere")))
    debounce: IntProperty(name="Live Update Delay", default=120, min=0, max=2000, subtype="TIME_ABSOLUTE",
                          description="Milliseconds to wait after a change before rebuilding the preview")
    max_resolution: IntProperty(name="Resolution Limit", default=512, min=64, max=1024,
                                description="The highest Final resolution Build Final accepts (memory grows with its cube)")

    def draw(self, _context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "device")
        layout.prop(self, "debounce")
        layout.prop(self, "max_resolution")


class _Defaults:
    """Preference values when the add-on is not registered as an extension (scripts, tests)."""
    device, debounce, max_resolution = "AUTO", 120, 512


def preferences():
    addon = bpy.context.preferences.addons.get(PACKAGE)
    return addon.preferences if addon is not None else _Defaults


classes = (IteronPreferences,)
