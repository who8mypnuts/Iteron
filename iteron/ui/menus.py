# SPDX-License-Identifier: MIT
"""Shift+A ▸ Iteron Fractal ▸ one entry per formula, grouped by family."""

from __future__ import annotations

import bpy

from ..core.formula import by_family
from . import icons


class VIEW3D_MT_iteron_add(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_iteron_add"
    bl_label = "Iteron Fractal"

    def draw(self, _context):
        layout = self.layout
        layout.operator_context = "EXEC_DEFAULT"
        for index, (family, entries) in enumerate(by_family()):
            if index:
                layout.separator()
            layout.label(text=family)
            for entry in entries:
                layout.operator("iteron.add_fractal", text=entry.name, icon_value=icons.thumbnail(entry.id)).formula = entry.id


class VIEW3D_MT_iteron_flame_add(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_iteron_flame_add"
    bl_label = "Iteron Flame"

    def draw(self, _context):
        from ..flames.library import bundled
        layout = self.layout
        layout.operator_context = "EXEC_DEFAULT"
        for key, flame in bundled().items():
            layout.operator("iteron.add_flame", text=flame.get("name", key)).flame = key
        layout.separator()
        layout.operator_context = "INVOKE_DEFAULT"
        layout.operator("iteron.import_fractalchemy", text="Import Fractalchemy…", icon="IMPORT")


def _add_menu(self, _context):
    self.layout.menu(VIEW3D_MT_iteron_add.bl_idname, icon_value=icons.icon("iteron_icon"))
    self.layout.menu(VIEW3D_MT_iteron_flame_add.bl_idname, icon_value=icons.icon("iteron_icon"))


classes = (VIEW3D_MT_iteron_add, VIEW3D_MT_iteron_flame_add)


def register_extra() -> None:
    bpy.types.VIEW3D_MT_add.append(_add_menu)


def unregister_extra() -> None:
    bpy.types.VIEW3D_MT_add.remove(_add_menu)
