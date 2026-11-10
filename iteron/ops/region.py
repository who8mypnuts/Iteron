# SPDX-License-Identifier: MIT
"""Frame View: point the sampling region at what the viewport is looking at — every voxel where you are looking;
Reset Region: back to the whole fractal."""

import math

import bpy
from mathutils import Vector

from ..bridge.state import is_fractal

VIEW_MARGIN = 1.2        # the region covers a little more than the view's half-height at the pivot


def view_region(region_3d, space, matrix_world):
    """`(center, half_size)` in the object's space for the view's pivot at its current zoom."""
    lens = getattr(space, "lens", 50.0)
    half_view = region_3d.view_distance * math.tan(math.atan(36.0 / (2.0 * lens))) * VIEW_MARGIN
    inverse = matrix_world.inverted()
    center = inverse @ Vector(region_3d.view_location)
    scale = max(matrix_world.to_scale()) or 1.0
    return center, half_view / scale


class ITERON_OT_frame_view(bpy.types.Operator):
    """Sample only around the 3D view's pivot at its current zoom: zoom in on a detail, then Frame View and Build
    Final to mesh it at full resolution"""
    bl_idname = "iteron.frame_view"
    bl_label = "Frame View"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return is_fractal(context.active_object) and context.region_data is not None

    def execute(self, context):
        obj = context.active_object
        center, half = view_region(context.region_data, context.space_data, obj.matrix_world)
        s = obj.iteron
        s.auto_fit = False
        s.center = center
        s.size = half
        return {"FINISHED"}


class ITERON_OT_reset_region(bpy.types.Operator):
    """Sample the whole fractal again (auto-fit on, the formula's own box)"""
    bl_idname = "iteron.reset_region"
    bl_label = "Reset Region"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return is_fractal(context.active_object)

    def execute(self, context):
        s = context.active_object.iteron
        s.center = (0.0, 0.0, 0.0)
        s.size = 0.0
        s.auto_fit = True
        return {"FINISHED"}


classes = (ITERON_OT_frame_view, ITERON_OT_reset_region)
