# SPDX-License-Identifier: MIT
"""Fragments: opening a `.frag` / `.fafrag` as an Iteron object, reloading it from disk, and the include folders.

The source goes into a Text datablock (with the user's own includes inlined, so the `.blend` opens anywhere), and its
textures into images packed in the `.blend`; the first preset's values are applied; its camera can become a Blender
camera. Fragments are y-up, so a y-up one is
turned upright with the object's rotation — its own space stays the fragment's.
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
import numpy as np
from bpy.props import StringProperty
from mathutils import Matrix

from ..bridge import fragment_props, material
from ..bridge.kinds import FragmentKind
from ..bridge.state import is_fractal
from ..fragments.formula import build, embeddable, texture_paths
from ..prefs import include_folders, preferences
from .add import build_first, new_object


def import_fragment(context, path: Path, camera: bool = True):
    path = Path(path)
    source = embeddable(path, include_folders())
    entry = build(source, None, include_folders(), path.stem, prefer_shims=True)     # FragmentError if unusable
    obj = new_object(context, entry.name)
    s, f = obj.iteron, obj.iteron.fragment
    s.kind = "FRAGMENT"
    f.name, f.path = path.stem, str(path)
    f.text = bpy.data.texts.new(path.name)
    f.text.write(source)
    fragment_props.sync(f, entry.params)
    fragment_props.write(f, entry.params, next(iter(entry.presets.values()), {}))
    fragment_props.set_textures(f, texture_paths(entry, path, include_folders()))
    s.surface_offset = entry.surface_offset
    if entry.camera is not None:
        s.center = entry.camera.target
        if abs(np.dot(_unit(entry.camera.up), (0.0, 1.0, 0.0))) > 0.9:
            obj.rotation_euler.x = math.pi / 2.0                    # y-up fragment → Blender's z-up
        if camera:
            add_camera(context, obj, entry.camera)
    material.ensure(obj)
    # its own colour if it has one; else the orbit trap, or the distance when it writes no trap
    s.color_mode = "BASE" if entry.provides_color else "TRAP" if entry.uses_trap else "RADIUS"
    build_first(obj)
    return obj


def _unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float64)
    return v / max(np.linalg.norm(v), 1e-12)


def look_at(eye, target, up) -> np.ndarray:
    """Camera-to-space 4 × 4 (Blender cameras look down −z, +y up)."""
    back = _unit(np.subtract(eye, target))
    right = _unit(np.cross(up, back))
    m = np.eye(4)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = right, np.cross(back, right), back, eye
    return m


def add_camera(context, obj, frag_camera):
    data = bpy.data.cameras.new(f"{obj.name} Camera")
    camera = bpy.data.objects.new(data.name, data)
    context.collection.objects.link(camera)
    context.view_layer.update()
    view = look_at(frag_camera.eye, frag_camera.target, frag_camera.up)
    camera.matrix_world = obj.matrix_world @ Matrix(view.tolist())
    data.sensor_fit = "VERTICAL"
    data.angle_y = frag_camera.vertical_angle
    data.clip_start, data.clip_end = max(1e-4, frag_camera.distance * 1e-3), frag_camera.distance * 100.0
    context.scene.camera = camera
    return camera


class ITERON_OT_reload_fragment(bpy.types.Operator):
    """Read the fragment's file again (its includes too); parameter values with the same names are kept"""
    bl_idname = "iteron.reload_fragment"
    bl_label = "Reload from Disk"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not is_fractal(obj) or obj.iteron.kind != "FRAGMENT":
            return False
        return Path(bpy.path.abspath(obj.iteron.fragment.path)).is_file()

    def execute(self, context):
        obj = context.active_object
        f = obj.iteron.fragment
        try:
            source = embeddable(Path(bpy.path.abspath(f.path)), include_folders())
        except (OSError, ValueError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        if f.text is None:
            f.text = bpy.data.texts.new(Path(f.path).name)
        f.text.clear()
        f.text.write(source)
        entry = FragmentKind.entry(obj)
        fragment_props.sync(f, entry.params)
        try:
            fragment_props.set_textures(f, texture_paths(entry, Path(bpy.path.abspath(f.path)), include_folders()))
        except ValueError as error:
            self.report({"WARNING"}, str(error))
        from ..bridge.state import params_changed
        params_changed(obj)
        return {"FINISHED"}


class ITERON_OT_add_include_folder(bpy.types.Operator):
    """Add a folder to the ones searched for the files fragments #include"""
    bl_idname = "iteron.add_include_folder"
    bl_label = "Add Include Folder"

    directory: StringProperty(subtype="DIR_PATH")

    def invoke(self, context, _event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, _context):
        prefs = preferences()
        folders = [f for f in include_folders() if f != self.directory.rstrip("/\\")]
        prefs.include_folders = ";".join(folders + [self.directory.rstrip("/\\")])
        return {"FINISHED"}


classes = (ITERON_OT_reload_fragment, ITERON_OT_add_include_folder)

__all__ = ["import_fragment", "add_camera", "look_at"]
