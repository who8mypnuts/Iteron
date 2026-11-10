# SPDX-License-Identifier: MIT
"""Shift+A ▸ Iteron Fractal ▸ a submenu per family (its icon the family's first thumbnail) ▸ one entry per formula;
Shift+A ▸ Iteron Flame ▸ the bundled flames and opening a file."""

from __future__ import annotations

import bpy

from ..core.formula import by_family, slug
from . import icons


def _family_menu(family: str) -> type:
    def draw(self, _context):
        layout = self.layout
        layout.operator_context = "EXEC_DEFAULT"
        for entry in dict(by_family())[family]:
            layout.operator("iteron.add_fractal", text=entry.name, icon_value=icons.thumbnail(entry.id)).formula = entry.id
    return type(f"VIEW3D_MT_iteron_add_{slug(family)}", (bpy.types.Menu,),
                {"bl_idname": f"VIEW3D_MT_iteron_add_{slug(family)}", "bl_label": family, "draw": draw})


FAMILY_MENUS = tuple(_family_menu(family) for family, _entries in by_family())


class VIEW3D_MT_iteron_add(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_iteron_add"
    bl_label = "Iteron Fractal"

    def draw(self, _context):
        families = dict(by_family())
        for menu in FAMILY_MENUS:
            first = families[menu.bl_label][0]
            self.layout.menu(menu.bl_idname, icon_value=icons.thumbnail(first.id))


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
        layout.operator("iteron.import_fractalchemy", text="Open a Flame File…", icon="IMPORT")


def _add_menu(self, _context):
    self.layout.menu(VIEW3D_MT_iteron_add.bl_idname, icon_value=icons.icon("iteron_icon"))
    self.layout.menu(VIEW3D_MT_iteron_flame_add.bl_idname, icon_value=icons.icon("iteron_icon"))


classes = FAMILY_MENUS + (VIEW3D_MT_iteron_add, VIEW3D_MT_iteron_flame_add)


def register_extra() -> None:
    bpy.types.VIEW3D_MT_add.append(_add_menu)


def unregister_extra() -> None:
    bpy.types.VIEW3D_MT_add.remove(_add_menu)
