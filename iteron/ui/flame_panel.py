# SPDX-License-Identifier: MIT
"""The sidebar for a flame object: output, points, the density solid's settings, materials, the transforms
(read-only) and the holon instances."""

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
    column.prop(f, "per_transform")
    layout.operator("iteron.build_final", icon="MESH_ICOSPHERE")
    draw_bake(layout, obj)
    _draw_instances(layout, f.instancer, split)
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


def _draw_instances(layout, settings, split) -> None:
    """The holons: a header checkbox, then placement, size and what is instanced."""
    header, body = layout.panel("iteron_flame_instances", default_closed=True)
    header.prop(settings, "enabled", text="Instances")
    if body is None:
        return
    column = split(body.column())
    column.active = settings.enabled
    column.prop(settings, "mode")
    column.prop(settings, "count" if settings.mode == "CHAOS" else "leaves_only")
    column.prop(settings, "depth")
    column.prop(settings, "frames")
    column.separator()
    column.prop(settings, "size")
    column.prop(settings, "falloff")
    column.prop(settings, "min_size")
    column.prop(settings, "cap")
    column.prop(settings, "seed")
    column.separator()
    column.prop(settings, "shape")
    if settings.shape == "OBJECT":
        column.prop(settings, "object")
    column.prop(settings, "palette")
