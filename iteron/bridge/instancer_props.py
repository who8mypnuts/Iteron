# SPDX-License-Identifier: MIT
"""A flame's holons: which mesh is instanced along the flame, and how the instances are placed and sized
(flames/holon.py). Placement settings rebuild; the shape, the object and the colouring only restyle."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import PropertyGroup

MODES = (("CHAOS", "Chaos Game", "Instances at orbit samples, each framed by its last transforms"),
         ("TREE", "Tree", "An instance at every composition of the transforms, level by level"))
FRAMES = (("JACOBIAN", "Turned", "Turned and scaled as the transforms turn and squash space"),
          ("TRANSLATION", "Upright", "Scaled only, never turned"))
SHAPES = (("SPHERE", "Sphere", ""), ("CUBE", "Cube", ""), ("ICOSAHEDRON", "Icosahedron", ""),
          ("TETRAHEDRON", "Tetrahedron", ""), ("TORUS", "Torus", ""), ("CYLINDER", "Cylinder", ""),
          ("OBJECT", "Object", "Any object of the scene"))


def _changed(self, _context):
    from .state import params_changed
    params_changed(self.id_data)


def _restyled(self, _context):
    from .holons import restyle
    restyle(self.id_data)


class IteronInstancer(PropertyGroup):
    enabled: BoolProperty(name="Instances", default=False, update=_changed,
                          description="Instance a mesh along the flame, turned and scaled by the transforms (holons)")
    mode: EnumProperty(name="Placement", items=MODES, default="CHAOS", update=_changed)
    count: IntProperty(name="Count", default=2000, min=1, soft_max=50_000, update=_changed,
                       description="Instances from the chaos game")
    depth: IntProperty(name="Depth", default=6, min=1, max=14, update=_changed,
                       description="Transforms composed per instance (chaos) or the tree's depth")
    leaves_only: BoolProperty(name="Deepest Level Only", default=False, update=_changed,
                              description="Tree: only the last level's instances")
    frames: EnumProperty(name="Frames", items=FRAMES, default="JACOBIAN", update=_changed)
    size: FloatProperty(name="Size", default=0.1, min=0.0, soft_max=2.0, subtype="DISTANCE", update=_changed,
                        description="An instance's size before the transforms scale it")
    falloff: FloatProperty(name="Size Falloff", default=1.0, min=0.0, max=2.0, update=_changed,
                           description="Exponent on the accumulated scale (below 1 evens the sizes out)")
    min_size: FloatProperty(name="Min Size", default=0.002, min=0.0, soft_max=0.1, precision=4, subtype="DISTANCE",
                            update=_changed, description="Smaller instances are dropped")
    cap: IntProperty(name="Max Instances", default=20_000, min=1, soft_max=200_000, update=_changed,
                     description="At most this many (the largest are kept)")
    seed: IntProperty(name="Seed", default=1, min=0, update=_changed)
    shape: EnumProperty(name="Shape", items=SHAPES, default="SPHERE", update=_restyled,
                        description="What is instanced")
    object: PointerProperty(name="Object", type=bpy.types.Object, update=_restyled,
                            description="The object instanced (Shape: Object)")
    palette: BoolProperty(name="Palette Colours", default=True, update=_restyled,
                          description="Colour each instance from the flame's palette (else the shape's own material)")
    source: StringProperty(options={"HIDDEN"}, description="An IFS of the instances' own (JSON; empty: the flame)")
    holder: PointerProperty(type=bpy.types.Object, options={"HIDDEN"}, description="The object the instances live on")

    def spec(self):
        import json
        from ..jobs.flame_pipeline import InstanceSpec
        return InstanceSpec(self.mode, self.count, self.depth, self.leaves_only, self.frames, self.size, self.falloff,
                            self.min_size, self.cap, self.seed, json.loads(self.source) if self.source else None)


classes = (IteronInstancer,)
