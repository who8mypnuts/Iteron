# SPDX-License-Identifier: MIT
"""The quick-start: what the Iteron tab shows with no fractal active. A family picker, that family's formulas as a
thumbnail gallery, the chosen formula's description and Add Fractal; then flames and opening files.

With some forty formulas one gallery would be a wall of thumbnails, so the gallery shows one family at a time
(each family's icon is its first formula's thumbnail)."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty

from ..bridge.props import FORMULA_ITEMS
from ..core.formula import REGISTRY, by_family, slug
from . import icons

_FAMILIES: list = []            # Blender needs dynamic enum items kept alive
_GALLERY: dict[str, list] = {}


def _family_items(_self, _context):
    _FAMILIES[:] = [(slug(family), family, f"{len(entries)} formulas: " + ", ".join(e.name for e in entries),
                     icons.thumbnail(entries[0].id), index) for index, (family, entries) in enumerate(by_family())]
    return _FAMILIES


def family_of(formula_id: str) -> str:
    return slug(REGISTRY[formula_id].family) if formula_id in REGISTRY else ""


def _gallery_items(self, _context):
    """The chosen family's formulas with their thumbnails (numbers match FORMULA_ITEMS, so choices persist)."""
    family = getattr(self, "iteron_new_family", "") or slug(by_family()[0][0])
    items = [(i[0], i[1], i[2], icons.thumbnail(i[0]), i[4]) for i in FORMULA_ITEMS
             if i[0] and family_of(i[0]) == family]
    _GALLERY[family] = items
    return items


def _family_changed(self, _context):
    items = _gallery_items(self, _context)
    if items and self.iteron_new_formula not in {i[0] for i in items}:
        self.iteron_new_formula = items[0][0]


def draw_quick_start(layout, context) -> None:
    wm = context.window_manager
    logo = icons.icon("iteron_logo")
    if logo:
        layout.template_icon(icon_value=logo, scale=4.0)
    layout.prop(wm, "iteron_new_family", text="")
    layout.template_icon_view(wm, "iteron_new_formula", show_labels=True, scale=7.0, scale_popup=5.0)
    entry = REGISTRY.get(wm.iteron_new_formula)
    if entry is not None:
        column = layout.column(align=True)
        column.label(text=entry.name)
        column.label(text=entry.description)
    operator = layout.operator("iteron.add_fractal", text="Add Fractal", icon="ADD")
    operator.formula = wm.iteron_new_formula
    layout.separator()
    row = layout.row(align=True)
    row.menu("VIEW3D_MT_iteron_flame_add", text="Add Flame", icon="OUTLINER_OB_POINTCLOUD")
    row.operator("iteron.import_fractalchemy", text="Open File…", icon="IMPORT")
    layout.label(text="Or Shift+A ▸ Iteron Fractal / Flame", icon="INFO")


def register_extra() -> None:
    wm = bpy.types.WindowManager
    wm.iteron_new_family = EnumProperty(name="Family", items=_family_items, update=_family_changed,
                                        description="Which family of formulas the gallery shows")
    wm.iteron_new_formula = EnumProperty(name="Formula", items=_gallery_items,
                                         description="The fractal Add Fractal creates")


def unregister_extra() -> None:
    del bpy.types.WindowManager.iteron_new_formula
    del bpy.types.WindowManager.iteron_new_family
