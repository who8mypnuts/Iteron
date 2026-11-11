# SPDX-License-Identifier: MIT
"""The `Col` colour attribute: the ramp baked onto the vertices, so exporters (glTF, PLY, USD) carry the colours.

Re-baked after every build, when the colour mode changes, and (debounced) when the ramp is edited.
"""

from __future__ import annotations

import bpy
import numpy as np
from bpy.app.handlers import persistent

from . import material
from .mesh_write import ATTRIBUTE_PREFIX

COLOR_ATTRIBUTE = "Col"
LUT_SIZE = 256
REBAKE_DELAY = 0.3          # seconds after the last ramp edit
_DIRTY: set[str] = set()    # names of Iteron materials edited since the last re-bake


def ramp_lut(obj) -> np.ndarray:
    """The object's colour ramp sampled at 256 points, `(256, 4)` float32 (a grey ramp without the material)."""
    ramp = material.ramp_node(obj)
    if ramp is None:
        return np.repeat(np.linspace(0.2, 0.9, LUT_SIZE, dtype=np.float32)[:, None], 4, axis=1)
    return np.array([ramp.color_ramp.evaluate(i / (LUT_SIZE - 1)) for i in range(LUT_SIZE)], dtype=np.float32)


def bake(obj) -> None:
    mesh, ramp = obj.data, material.ramp_node(obj)
    count = len(mesh.vertices)
    if ramp is None or count == 0:
        return
    lut = ramp_lut(obj)
    base = mesh.attributes.get(ATTRIBUTE_PREFIX + "base")
    if obj.iteron.color_mode == "BASE" and base is not None:         # a fragment's own colours, as they are
        colours = np.zeros(count * 4, dtype=np.float32)
        base.data.foreach_get("color", colours)
        _store(mesh, colours)
        return
    name = material.ATTRIBUTE_FOR_MODE[obj.iteron.color_mode]
    source = mesh.attributes.get(ATTRIBUTE_PREFIX + name) if name else None
    values = np.zeros(count, dtype=np.float32)
    if source is not None:
        source.data.foreach_get("value", values)
    _store(mesh, lut[np.clip((values * (LUT_SIZE - 1)).round().astype(np.int64), 0, LUT_SIZE - 1)].ravel())


def _store(mesh, colours: np.ndarray) -> None:
    attribute = mesh.color_attributes.get(COLOR_ATTRIBUTE) or mesh.color_attributes.new(COLOR_ATTRIBUTE, "FLOAT_COLOR",
                                                                                         "POINT")
    attribute.data.foreach_set("color", np.ascontiguousarray(colours, dtype=np.float32))
    mesh.color_attributes.active_color = attribute
    mesh.update()


def color_mode_changed(obj) -> None:
    material.set_mode(obj, obj.iteron.color_mode)
    bake(obj)


@persistent
def _on_depsgraph(_scene, depsgraph) -> None:
    """Note Iteron materials whose node tree changed (a ramp edit) and re-bake a moment after the edits stop."""
    for update in depsgraph.updates:
        owner = update.id.original
        if isinstance(owner, bpy.types.ShaderNodeTree):
            owner = next((m for m in bpy.data.materials if m.node_tree == owner), None)
        if isinstance(owner, bpy.types.Material) and owner.node_tree and material.RAMP_NODE in owner.node_tree.nodes:
            _DIRTY.add(owner.name)
    if _DIRTY and not bpy.app.background and not bpy.app.timers.is_registered(rebake_dirty):
        bpy.app.timers.register(rebake_dirty, first_interval=REBAKE_DELAY)


def rebake_dirty() -> None:
    names = set(_DIRTY)
    _DIRTY.clear()
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj.iteron.is_fractal:
            found = material.find(obj)
            if found is not None and found.name in names:
                bake(obj)


def register() -> None:
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)


def unregister() -> None:
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)
