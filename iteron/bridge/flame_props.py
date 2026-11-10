# SPDX-License-Identifier: MIT
"""What a flame object stores: the flame itself (Fractalchemy's dict, as JSON) and how it is turned into geometry."""

from __future__ import annotations

import json

from bpy.props import EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup

OUTPUTS = (("POINTS", "Points", "The orbit as a point cloud (rendered as tiny spheres: a Geometry Nodes modifier)"),
           ("MESH", "Solid", "The orbit's dense regions as a closed mesh"))
PREVIEW_POINTS = 250_000      # live previews iterate at most this many points


def _changed(self, _context):
    from .state import params_changed
    params_changed(self.id_data)


def _radius_changed(self, _context):
    from .flame_write import update_point_radius
    update_point_radius(self.id_data)


class IteronFlameSettings(PropertyGroup):
    source: StringProperty(options={"HIDDEN"}, description="The flame, as Fractalchemy's JSON")
    points: IntProperty(name="Points", default=1_000_000, min=1_000, soft_max=10_000_000, max=100_000_000,
                        description="Orbit points for Build Final (previews use at most 250 000)")
    seed: IntProperty(name="Seed", default=1, min=0, update=_changed, description="Random seed of the chaos game")
    output: EnumProperty(name="Output", items=OUTPUTS, default="POINTS", update=_changed)
    point_radius: FloatProperty(name="Point Size", default=0.005, min=0.00001, soft_max=0.05, precision=4,
                                subtype="DISTANCE", update=_radius_changed, description="Radius of each point")
    threshold: FloatProperty(name="Density Threshold", default=0.15, min=0.0001, max=1.0, precision=3,
                             update=_changed, description="Solid where the normalised point density exceeds this")
    smoothing: FloatProperty(name="Smoothing", default=1.0, min=0.0, max=4.0, update=_changed,
                             description="Gaussian blur of the density, in voxels")
    unsupported: StringProperty(options={"HIDDEN"}, description="Variations the flame uses that Iteron cannot run")

    def flame_dict(self) -> dict:
        return json.loads(self.source) if self.source else {}


classes = (IteronFlameSettings,)
