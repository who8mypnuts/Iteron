# SPDX-License-Identifier: MIT
"""Blender properties generated from the formula schemas, and `Object.iteron` — everything a fractal object stores.

Each formula gets its own PropertyGroup (built with `type()` from its `Param`s), so its values survive switching
formulas and back, and every parameter is a real typed property: keyframes, drivers, *Reset to Default* and
`obj.iteron.f_mandelbulb.power` all work. Nothing here is written per formula.
"""

from __future__ import annotations

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty,
                       PointerProperty, StringProperty)
from bpy.types import PropertyGroup

from .. import formulas  # noqa: F401  (registers the formulas)
from .animation import IteronBakedFrame
from .flame_props import IteronFlameSettings
from .fragment_props import IteronFragmentSettings
from ..core.formula import REGISTRY, by_family
from ..core.params import Param

GROUP_PREFIX = "f_"
SHADING_MODES = (("FIELD", "Field Normals", "Normals from the fractal's own field: detail finer than the faces shows"),
                 ("SMOOTH", "Smooth", "Normals averaged from the faces"),
                 ("FLAT", "Flat", "One normal per face"))
PREVIEW_MODES = (("AUTO", "Auto", "Show the fractal ray-marched while its mesh is being rebuilt, the mesh otherwise"),
                 ("RAYMARCH", "Ray-march", "Always show the ray-marched fractal; the mesh is only built by Build "
                  "Final (fastest exploring)"),
                 ("MESH", "Mesh", "Show only the mesh"))
KINDS = (("FORMULA", "Formula", "A distance-estimated fractal"), ("FLAME", "Flame", "A fractal flame (an IFS)"),
         ("FRAGMENT", "Fragment", "A Fragmentarium distance estimator"))
OUTPUTS = (("MESH", "Mesh", "A surface mesh"),
           ("VOLUME", "Volume", "The mesh filled as a volume (Geometry Nodes Mesh to Volume), for fog-like renders"))
COLOR_MODES = (("TRAP", "Orbit Trap", "Colour by how close the orbit came to the origin"),
               ("ITERATIONS", "Iterations", "Colour by how many iterations the point took"),
               ("RADIUS", "Radius", "Colour by the orbit's final distance from the origin"),
               ("SOLID", "Solid", "One colour: the start of the ramp"))


def _changed(self, _context):
    from .state import params_changed     # late: state imports the scheduler, which imports this module's users
    params_changed(self.id_data)


def _color_mode_changed(self, _context):
    from .colors import color_mode_changed
    color_mode_changed(self.id_data)


def _shading_changed(self, _context):
    from .mesh_write import apply_shading
    apply_shading(self.id_data)
    if self.shading == "FIELD":                       # field normals come from the field: rebuild
        _changed(self, _context)


def blender_property(param: Param):
    """The bpy property for one parameter spec."""
    common = {"name": param.title, "description": param.description, "update": _changed}
    if param.kind == "float":
        extra = {k: v for k, v in (("min", param.hard_min), ("max", param.hard_max)) if v is not None}
        return FloatProperty(default=param.default, soft_min=param.min, soft_max=param.max, subtype=param.subtype,
                             precision=3, step=1, **extra, **common)
    if param.kind == "int":
        return IntProperty(default=param.default, min=param.min, max=param.max, **common)
    if param.kind == "bool":
        return BoolProperty(default=param.default, **common)
    if param.kind == "vec3":
        return FloatVectorProperty(size=3, default=param.default, soft_min=param.min, soft_max=param.max,
                                   subtype=param.subtype, precision=3, step=1, **common)
    if param.kind == "enum":
        return EnumProperty(items=list(param.items), default=param.default, **common)
    raise TypeError(f"no Blender property for {param.kind!r}")


def _formula_items():
    items, number = [], 0
    for family, entries in by_family():
        items.append(("", family, ""))                 # a heading in the menu
        for entry in entries:
            items.append((entry.id, entry.name, entry.description, "NONE", number))
            number += 1
    return items


FORMULA_ITEMS = _formula_items()


def _output_changed(self, _context):
    from .volume import apply
    apply(self.id_data)


def _preview_changed(self, _context):
    from .display import sync
    sync(self.id_data)
    _changed(self, _context)


def _formula_changed(self, context):
    from .state import formula_changed
    formula_changed(self.id_data)


def _settings_annotations(groups: dict[str, type]) -> dict:
    refresh = {"update": _changed}
    annotations = {
        "is_fractal": BoolProperty(default=False, options={"HIDDEN"}),
        "kind": EnumProperty(items=KINDS, default="FORMULA", options={"HIDDEN"}),
        "flame": PointerProperty(type=IteronFlameSettings),
        "fragment": PointerProperty(type=IteronFragmentSettings),
        "baked": CollectionProperty(type=IteronBakedFrame, description="Baked frames: a mesh per frame"),
        "live_mesh": PointerProperty(type=bpy.types.Mesh, description="The mesh rebuilds write to (while baked, "
                                     "the object shows a baked one)"),
        "formula": EnumProperty(name="Formula", items=FORMULA_ITEMS, update=_formula_changed,
                                description="The fractal this object is built from"),
        "live": BoolProperty(name="Live", default=True,
                             description="Rebuild the preview mesh whenever a parameter changes"),
        "preview": EnumProperty(name="Preview", items=PREVIEW_MODES, default="AUTO", update=_preview_changed,
                                description="How the viewport shows the fractal while you work"),
        "saved_display": StringProperty(options={"HIDDEN"}, description="The display type the ray-marched preview "
                                        "replaced"),
        "channel_lo": FloatVectorProperty(size=3, options={"HIDDEN"}, default=(0.0, 0.0, 0.0)),
        "channel_hi": FloatVectorProperty(size=3, options={"HIDDEN"}, default=(1.0, 1.0, 1.0)),
        "auto_fit": BoolProperty(name="Auto-Fit", default=True, description="Shrink the box to where the fractal is "
                                 "(a coarse pass first), so every voxel counts", **refresh),
        "center": FloatVectorProperty(name="Center", size=3, subtype="TRANSLATION", description="Center of the sampling box",
                                      **refresh),
        "size": FloatProperty(name="Size", default=0.0, min=0.0, soft_max=10.0, subtype="DISTANCE",
                              description="Half-size of the sampling box (0 uses the formula's own)", **refresh),
        "preview_resolution": IntProperty(name="Preview", default=96, min=16, max=256,
                                          description="Voxels along the longest side for the live preview", **refresh),
        "final_resolution": IntProperty(name="Final", default=256, min=32, max=4096,
                                        description="Voxels along the longest side for Build Final"),
        "simplify": FloatProperty(name="Simplify", default=0.1, min=0.0, max=2.0, soft_max=0.5, precision=2,
                                  description="Build Final merges flat areas whose faces stay within this many voxels "
                                  "of the surface; detail keeps every face (0 = off)"),
        "surface_offset": FloatProperty(name="Surface Offset", default=0.5, soft_min=0.0, soft_max=2.0, min=-4.0, max=8.0,
                                        description="How far out the surface sits, in voxels of true distance (the "
                                        "estimator is calibrated per build). Lower is crisper; too low breaks thin "
                                        "parts into dust", **refresh),
        "refine_steps": IntProperty(name="Refine", default=2, min=0, max=6,
                                    description="Newton steps moving every vertex onto the fractal's true surface: "
                                    "crisp ridges and grooves (0 = off, faster)", **refresh),
        "output": EnumProperty(name="Output", items=OUTPUTS, default="MESH", update=_output_changed,
                               description="What the fractal renders as"),
        "volume_density": FloatProperty(name="Density", default=1.0, min=0.0, soft_max=20.0, update=_output_changed,
                                        description="Density inside the fractal"),
        "volume_voxel": FloatProperty(name="Voxel Size", default=0.02, min=0.0005, soft_max=0.2, precision=4,
                                      subtype="DISTANCE", update=_output_changed,
                                      description="The volume's voxel size (smaller is finer and heavier)"),
        "color_mode": EnumProperty(name="Color", items=COLOR_MODES, default="TRAP", update=_color_mode_changed,
                                   description="What drives the colour ramp"),
        "shading": EnumProperty(name="Shading", items=SHADING_MODES, default="FIELD", update=_shading_changed,
                                description="How the surface's normals are made"),
        # the last build, written by the scheduler
        "built_hash": StringProperty(options={"HIDDEN"}),
        "built_resolution": IntProperty(options={"HIDDEN"}),
        "built_final": BoolProperty(options={"HIDDEN"}),
        "built_faces": IntProperty(options={"HIDDEN"}),
        "built_seconds": FloatProperty(options={"HIDDEN"}),
        "built_device": StringProperty(options={"HIDDEN"}),
        "message": StringProperty(options={"HIDDEN"}, description="The last warning or error"),
    }
    for fid, cls in groups.items():
        annotations[GROUP_PREFIX + fid] = PointerProperty(type=cls)
    return annotations


_CLASSES: list[type] = []


def register() -> None:
    groups = {}
    for fid, entry in REGISTRY.items():
        cls = type(f"ITERON_PG_{fid}", (PropertyGroup,), {"__annotations__": {p.name: blender_property(p)
                                                                                for p in stored(entry)}})
        bpy.utils.register_class(cls)
        groups[fid] = cls
        _CLASSES.append(cls)
    settings = type("ITERON_PG_settings", (PropertyGroup,), {"__annotations__": _settings_annotations(groups)})
    bpy.utils.register_class(settings)
    _CLASSES.append(settings)
    bpy.types.Object.iteron = PointerProperty(type=settings)


def unregister() -> None:
    del bpy.types.Object.iteron
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
    _CLASSES.clear()


# --- reading and writing values ------------------------------------------------------------------------------------
def stored(entry) -> list:
    """The parameters an object keeps for `entry` (a hybrid keeps only its own; its parts' live in their groups)."""
    return [p for p in entry.params if entry.stored is None or p.name in entry.stored]


def group(settings, formula_id: str | None = None):
    """A formula's PropertyGroup (the active formula's by default)."""
    return getattr(settings, GROUP_PREFIX + (formula_id or settings.formula))


def locate(settings, name: str):
    """`(PropertyGroup, attribute)` holding parameter `name` of the active formula — a hybrid's `a_power` is the
    first part's own `power`."""
    entry = REGISTRY[settings.formula]
    if entry.compose is not None and name[:2] in ("a_", "b_"):
        own = group(settings)
        return group(settings, own.first if name[0] == "a" else own.second), name[2:]
    return group(settings), name


def read_values(settings) -> dict:
    """The active formula's parameter values as plain Python (vectors as tuples), a hybrid's parts included."""
    entry, values = REGISTRY[settings.formula], {}
    for p in stored(entry):
        values[p.name] = _plain(getattr(group(settings), p.name))
    if entry.compose is not None:
        for p in entry.compose(values).params:
            if p.name not in values:
                data, attr = locate(settings, p.name)
                values[p.name] = _plain(getattr(data, attr))
    return values


def write_values(settings, values: dict) -> None:
    """Set the active formula's parameters (unknown names are ignored); a hybrid's choices are set first."""
    entry = REGISTRY[settings.formula]
    for p in stored(entry):
        if p.name in values:
            setattr(group(settings), p.name, p.coerce(values[p.name]))
    if entry.compose is not None:
        for p in entry.compose(read_values(settings)).params:
            if p.name in values and p.name not in entry.stored:
                data, attr = locate(settings, p.name)
                setattr(data, attr, p.coerce(values[p.name]))


def reset_values(settings) -> None:
    write_values(settings, REGISTRY[settings.formula].values())


def _plain(value):
    return tuple(value) if hasattr(value, "__len__") and not isinstance(value, str) else value
