# SPDX-License-Identifier: MIT
"""The Iteron tab in the 3D Viewport sidebar: the quick-start, or the active fractal's controls."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty

from ..bridge import material
from ..bridge.props import FORMULA_ITEMS, group
from ..bridge.state import final_estimate, is_fractal, is_stale
from ..core.formula import REGISTRY
from ..jobs.scheduler import SCHEDULER, Running
from . import icons
from .draw import REGION_GROUPS, draw_group, draw_params


class ITERON_PT_main(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Iteron"
    bl_label = "Iteron"

    def draw_header(self, _context):
        self.layout.label(icon_value=icons.icon("iteron_icon"))

    def draw_header_preset(self, context):
        obj = context.active_object
        if is_fractal(obj):
            row = self.layout.row(align=True)
            row.prop(obj.iteron, "live", text="", icon="PLAY" if obj.iteron.live else "PAUSE", emboss=False)
            row.operator("iteron.rebuild", text="", icon="FILE_REFRESH", emboss=False)

    def draw(self, context):
        obj = context.active_object
        if is_fractal(obj):
            draw_fractal(self.layout, obj)
        else:
            draw_quick_start(self.layout, context)


def draw_quick_start(layout, context) -> None:
    wm = context.window_manager
    logo = icons.icon("iteron_logo")
    if logo:
        layout.template_icon(icon_value=logo, scale=4.0)
    layout.template_icon_view(wm, "iteron_new_formula", show_labels=True, scale=7.0, scale_popup=5.0)
    entry = REGISTRY.get(wm.iteron_new_formula)
    if entry is not None:
        layout.label(text=entry.name)
        layout.label(text=entry.description)
    operator = layout.operator("iteron.add_fractal", text="Add Fractal", icon="ADD")
    operator.formula = wm.iteron_new_formula
    layout.label(text="Or Shift+A ▸ Iteron Fractal", icon="INFO")


def draw_fractal(layout, obj) -> None:
    s = obj.iteron
    entry = REGISTRY[s.formula]
    layout.label(text=obj.name, icon="OUTLINER_OB_MESH")
    layout.prop(s, "formula", text="")
    row = layout.row(align=True)
    row.operator_menu_enum("iteron.apply_preset", "preset", text="Presets", icon="PRESET")
    row.operator("iteron.save_preset", text="", icon="ADD")
    row.operator_menu_enum("iteron.delete_preset", "preset", text="", icon="REMOVE")
    row.operator("iteron.reset_formula", text="", icon="LOOP_BACK")
    _draw_status(layout, obj)
    header, body = layout.panel("iteron_shape", default_closed=False)
    header.label(text="Shape")
    if body is not None:
        draw_params(body, group(s), entry)
    _draw_region(layout, s, entry)
    _draw_mesh(layout, obj)
    _draw_color(layout, obj)


def _draw_status(layout, obj) -> None:
    s, status = obj.iteron, SCHEDULER.status(obj)
    if isinstance(status, Running):
        row = layout.row(align=True)
        row.progress(factor=status.step.fraction, type="BAR",
                     text=f"{'Final' if status.final else 'Preview'} · {status.step.message}")
        row.operator("iteron.cancel", text="", icon="X")
    elif status is not None:
        layout.label(text="Queued…", icon="TIME")
    elif s.built_hash:
        kind = "Final" if s.built_final else "Preview"
        text = f"{kind} {s.built_resolution} · {s.built_faces:,} faces · {s.built_seconds:.1f} s · {s.built_device}"
        layout.label(text=text + (" · stale" if is_stale(obj) else ""), icon="ERROR" if is_stale(obj) else "CHECKMARK")
    else:
        layout.label(text="Not built yet", icon="TIME")
    if s.message:
        layout.label(text=s.message, icon="ERROR" if "failed" in s.message.lower() else "INFO")


def _draw_region(layout, s, entry) -> None:
    header, body = layout.panel("iteron_region", default_closed=True)
    header.label(text="Region")
    if body is not None:
        row = body.row(align=True)
        row.operator("iteron.frame_view", icon="ZOOM_SELECTED")
        row.operator("iteron.reset_region", text="", icon="LOOP_BACK")
        column = _split(body.column())
        column.prop(s, "auto_fit")
        column.prop(s, "center")
        column.prop(s, "size")
        for name in REGION_GROUPS:
            draw_group(body, group(s), entry, name)


def _count(n: int) -> str:
    return f"{n / 1e6:.1f} M" if n >= 1e6 else f"{n / 1e3:.0f} k"


def _draw_mesh(layout, obj) -> None:
    s = obj.iteron
    header, body = layout.panel("iteron_mesh", default_closed=True)
    header.label(text="Mesh")
    if body is None:
        return
    column = _split(body.column())
    column.prop(s, "preview_resolution")
    column.prop(s, "surface_offset")
    column.prop(s, "refine_steps")
    column.prop(s, "shading")
    column.separator()
    column.prop(s, "final_resolution")
    column.prop(s, "simplify")
    estimate = final_estimate(obj)
    if estimate is not None:
        faces, size = estimate
        column.label(text=f"About {_count(faces)} faces · {size / 1e9:.1f} GB", icon="INFO")
    body.operator("iteron.build_final", icon="MESH_ICOSPHERE")
    body.operator("iteron.apply_mesh", icon="CHECKMARK")


def _draw_color(layout, obj) -> None:
    header, body = layout.panel("iteron_color", default_closed=True)
    header.label(text="Color")
    if body is None:
        return
    _split(body.column()).prop(obj.iteron, "color_mode", text="Source")
    ramp = material.ramp_node(obj)
    if ramp is not None:
        body.template_color_ramp(ramp, "color_ramp", expand=True)
    else:
        body.label(text="The Iteron material was removed", icon="INFO")


def _split(layout):
    layout.use_property_split = True
    layout.use_property_decorate = False
    return layout


classes = (ITERON_PT_main,)


_GALLERY: list = []              # Blender needs dynamic enum items kept alive


def _gallery_items(_self, _context):
    """The formulas with their thumbnails, for the quick-start's icon view (the numbers match FORMULA_ITEMS)."""
    _GALLERY[:] = [(i[0], i[1], i[2], icons.thumbnail(i[0]), i[4]) for i in FORMULA_ITEMS if i[0]]
    return _GALLERY


def register_extra() -> None:
    bpy.types.WindowManager.iteron_new_formula = EnumProperty(name="Formula", items=_gallery_items,
                                                              description="The fractal Add Fractal creates")


def unregister_extra() -> None:
    del bpy.types.WindowManager.iteron_new_formula
