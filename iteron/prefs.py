# SPDX-License-Identifier: MIT
"""Add-on preferences: what is set once, not per fractal."""

import bpy
from bpy.props import EnumProperty, FloatProperty, IntProperty, StringProperty

PACKAGE = __package__


class IteronPreferences(bpy.types.AddonPreferences):
    bl_idname = PACKAGE

    device: EnumProperty(name="Compute Device", default="AUTO",
                         items=(("AUTO", "Automatic", "The GPU when Blender can draw with it, otherwise the CPU"),
                                ("GPU", "GPU", "Always try the GPU first (falls back to the CPU on failure)"),
                                ("CPU", "CPU", "numpy on the CPU: slower, float64, works everywhere")))
    debounce: IntProperty(name="Live Update Delay", default=120, min=0, max=2000, subtype="TIME_ABSOLUTE",
                          description="Milliseconds to wait after a change before rebuilding the preview")
    max_resolution: IntProperty(name="Resolution Limit", default=1024, min=64, max=2048,
                                description="The highest Final resolution Build Final accepts (faces, time and memory "
                                "grow about as its 2.5th power)")

    preview_detail: FloatProperty(name="Preview Detail", default=1.0, min=0.25, max=8.0,
                                  description="The live preview's hit threshold, in pixels: lower resolves finer "
                                  "detail, higher draws faster")
    preview_steps: IntProperty(name="Preview Steps", default=256, min=32, max=1024,
                               description="Most steps a preview ray takes: more reaches into deep crevices, fewer "
                               "draws faster")
    include_folders: StringProperty(name="Include Folders",
                                    description="Folders searched for the files fragments #include (for example "
                                    "Fractalchemy's or FragM's include folder), separated by ';'. Iteron's own "
                                    "stand-ins serve the ray tracers, MathUtils, Triplex and Primitives")

    def draw(self, _context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "device")
        layout.prop(self, "debounce")
        layout.prop(self, "max_resolution")
        layout.prop(self, "preview_detail")
        layout.prop(self, "preview_steps")
        row = layout.row(align=True)
        row.prop(self, "include_folders")
        row.operator("iteron.add_include_folder", text="", icon="FILE_FOLDER")


class _Defaults:
    """Preference values when the add-on is not registered as an extension (scripts, tests)."""
    device, debounce, max_resolution, include_folders = "AUTO", 120, 1024, ""
    preview_detail, preview_steps = 1.0, 256


def preferences():
    addon = bpy.context.preferences.addons.get(PACKAGE)
    return addon.preferences if addon is not None else _Defaults


def include_folders() -> tuple[str, ...]:
    return tuple(f.strip() for f in preferences().include_folders.split(";") if f.strip())


classes = (IteronPreferences,)
