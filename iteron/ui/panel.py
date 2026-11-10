# SPDX-License-Identifier: MIT
"""The Iteron tab in the 3D Viewport sidebar: the quick-start, or the active fractal's controls."""

from __future__ import annotations

import bpy

from ..bridge import material
from ..bridge.kinds import FormulaKind
from ..bridge.props import locate
from ..bridge.state import final_estimate, is_fractal, is_stale
from ..jobs.scheduler import SCHEDULER, Running
from . import icons
from .quick_start import draw_quick_start
from .draw import REGION_GROUPS, Source, draw_group, draw_params


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


def draw_fractal(layout, obj) -> None:
    kind = obj.iteron.kind
    if kind == "FLAME":
        from .flame_panel import draw_flame
        draw_flame(layout, obj, _draw_status, _split)
        return
    if kind == "FRAGMENT":
        from .fragment_panel import draw_fragment
        draw_fragment(layout, obj)
        return
    s = obj.iteron
    layout.label(text=obj.name, icon="OUTLINER_OB_MESH")
    layout.prop(s, "formula", text="")
    draw_body(layout, obj, FormulaKind.entry(obj), Source(lambda name: locate(s, name)))


def draw_body(layout, obj, entry, source: Source) -> None:
    """Everything below a formula's or fragment's header: preview mode, presets, status, Shape, Region, Mesh,
    Color."""
    layout.row().prop(obj.iteron, "preview", expand=True)
    row = layout.row(align=True)
    row.operator_menu_enum("iteron.apply_preset", "preset", text="Presets", icon="PRESET")
    row.operator("iteron.save_preset", text="", icon="ADD")
    row.operator_menu_enum("iteron.delete_preset", "preset", text="", icon="REMOVE")
    row.operator("iteron.reset_formula", text="", icon="LOOP_BACK")
    _draw_status(layout, obj)
    header, body = layout.panel("iteron_shape", default_closed=False)
    header.label(text="Shape")
    if body is not None:
        draw_params(body, source, entry)
    _draw_region(layout, obj.iteron, entry, source)
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


def _draw_region(layout, s, entry, source: Source) -> None:
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
            draw_group(body, source, entry, name)


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
    column.separator()
    column.prop(s, "output")
    if s.output == "VOLUME":
        column.prop(s, "volume_density")
        column.prop(s, "volume_voxel")
    body.operator("iteron.build_final", icon="MESH_ICOSPHERE")
    draw_bake(body, obj)
    body.operator("iteron.apply_mesh", icon="CHECKMARK")


def draw_bake(layout, obj) -> None:
    """Bake Animation, or what is baked and Clear Bake."""
    from ..bridge.animation import baked, frame_range
    if baked(obj):
        first, last = frame_range(obj)
        row = layout.row(align=True)
        row.label(text=f"Baked frames {first}–{last}", icon="RENDER_ANIMATION")
        row.operator("iteron.clear_bake", text="", icon="TRASH")
    else:
        layout.operator("iteron.bake_animation", icon="RENDER_ANIMATION")


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
