# SPDX-License-Identifier: MIT
# Iteron — 3D fractals as Blender meshes. Copyright (c) 2026 Stan Ragets. MIT licence (see LICENSE).
"""Registration only. Each module lists its Blender classes in `classes` and may add `register_extra()` /
`unregister_extra()` (or plain `register()` / `unregister()`) for anything that is not a class."""

from __future__ import annotations

import importlib

MODULES = ("prefs", "ui.icons", "bridge.animation", "bridge.instancer_props", "bridge.flame_props",
           "bridge.fragment_props", "bridge.props", "bridge.state", "bridge.colors", "bridge.display", "ops.add", "ops.build", "ops.presets", "ops.apply",
           "ops.region", "ops.importer", "ops.fragments", "ops.bake", "ui.quick_start", "ui.panel", "ui.menus",
           "ui.overlay", "jobs.scheduler")


def _modules():
    return [importlib.import_module(f".{name}", __package__) for name in MODULES]


def register() -> None:
    import bpy
    for module in _modules():
        if hasattr(module, "register"):
            module.register()
        for cls in getattr(module, "classes", ()):
            bpy.utils.register_class(cls)
        if hasattr(module, "register_extra"):
            module.register_extra()


def unregister() -> None:
    import bpy
    for module in reversed(_modules()):
        if hasattr(module, "unregister_extra"):
            module.unregister_extra()
        for cls in reversed(getattr(module, "classes", ())):
            bpy.utils.unregister_class(cls)
        if hasattr(module, "unregister"):
            module.unregister()
