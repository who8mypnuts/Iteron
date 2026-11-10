# SPDX-License-Identifier: MIT
"""The sidebar for a flame object: output, points, the density solid's settings, the transforms (read-only)."""

from __future__ import annotations

from .panel import draw_bake


def draw_flame(layout, obj, draw_status, split) -> None:
    s, f = obj.iteron, obj.iteron.flame
    flame = f.flame_dict()
    layout.label(text=f"{obj.name}  ·  {flame.get('name', 'flame')}", icon="OUTLINER_OB_POINTCLOUD")
    layout.row().prop(f, "output", expand=True)
    draw_status(layout, obj)
    if f.unsupported:
        layout.label(text=f"Not available, ignored: {f.unsupported}", icon="ERROR")
    column = split(layout.column())
    column.prop(f, "points")
    column.prop(f, "seed")
    if f.output == "POINTS":
        column.prop(f, "point_radius")
    else:
        column.prop(f, "threshold")
        column.prop(f, "smoothing")
        column.prop(s, "preview_resolution")
        column.prop(s, "final_resolution")
    layout.operator("iteron.build_final", icon="MESH_ICOSPHERE")
    draw_bake(layout, obj)
    header, body = layout.panel("iteron_flame_xforms", default_closed=True)
    header.label(text=f"Transforms ({len(flame.get('xforms', []))})")
    if body is not None:
        for index, xform in enumerate(flame.get("xforms", [])):
            variations = ", ".join(f"{name} {weight:g}" for name, weight in xform.get("variations", {}).items())
            body.label(text=f"{index + 1}  ·  weight {xform.get('weight', 0):g}  ·  {variations}")
        if flame.get("final"):
            variations = ", ".join(f"{n} {w:g}" for n, w in flame["final"].get("variations", {}).items())
            body.label(text=f"final  ·  {variations}")
    layout.operator("iteron.apply_mesh", icon="CHECKMARK")
