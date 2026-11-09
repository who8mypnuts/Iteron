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
                layout.operator("iteron.add_fractal", text=entry.name).formula = entry.id


def _add_menu(self, _context):
    self.layout.menu(VIEW3D_MT_iteron_add.bl_idname, icon_value=icons.icon("iteron_icon"))


classes = (VIEW3D_MT_iteron_add,)


def register_extra() -> None:
    bpy.types.VIEW3D_MT_add.append(_add_menu)


def unregister_extra() -> None:
    bpy.types.VIEW3D_MT_add.remove(_add_menu)
