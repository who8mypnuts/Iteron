# SPDX-License-Identifier: MIT
"""The sidebar and menus draw without errors, and every property they show exists (a typo would only surface as
a broken panel in the live UI)."""

import numpy as np
import pytest

import bpy
from iteron.bridge import colors, material
from iteron.core.formula import REGISTRY
from iteron.ui import menus, panel


class FakeLayout:
    """Records what a draw function asks for; `prop` checks the property exists on its data."""

    def __init__(self, log):
        self.log = log
        self.use_property_split = self.use_property_decorate = False
        self.active = self.enabled = True
        self.operator_context = "INVOKE_DEFAULT"

    def _child(self, *_args, **_kwargs):
        return FakeLayout(self.log)

    row = column = box = split = _child

    def prop(self, data, name, **_kwargs):
        assert name in data.bl_rna.properties, f"{data.bl_rna.identifier} has no property {name!r}"
        self.log.append(("prop", name))

    def panel(self, idname, default_closed=False):
        self.log.append(("panel", idname))
        return FakeLayout(self.log), FakeLayout(self.log)

    def operator(self, idname, **_kwargs):
        module, name = idname.split(".")
        assert hasattr(getattr(bpy.ops, module), name), f"no operator {idname}"
        self.log.append(("operator", idname))
        return type("Props", (), {})()

    def operator_menu_enum(self, idname, prop, **_kwargs):
        self.operator(idname)

    def label(self, **kwargs):
        self.log.append(("label", kwargs.get("text", "")))

    def menu(self, idname, **_kwargs):
        self.log.append(("menu", idname))

    def progress(self, **kwargs):
        self.log.append(("progress", kwargs.get("text")))

    def template_color_ramp(self, data, name, **_kwargs):
        assert name in data.bl_rna.properties
        self.log.append(("ramp", data.name))

    def template_icon(self, **_kwargs):
        self.log.append(("icon",))

    def template_icon_view(self, data, name, **_kwargs):
        assert name in data.bl_rna.properties
        self.log.append(("icon_view", name))

    def separator(self, **_kwargs):
        pass


def test_quick_start_draws(addon):
    log = []
    panel.draw_quick_start(FakeLayout(log), bpy.context)
    assert ("operator", "iteron.add_fractal") in log and ("icon_view", "iteron_new_formula") in log


@pytest.mark.parametrize("fid", list(REGISTRY))
def test_fractal_panel_draws_every_parameter(fractal, fid):
    obj = fractal(fid, resolution=24)
    log = []
    panel.draw_fractal(FakeLayout(log), obj)
    shown = {name for kind, name in log if kind == "prop"}
    assert {p.name for p in REGISTRY[fid].params} <= shown
    assert ("ramp", material.RAMP_NODE) in log and ("operator", "iteron.build_final") in log


def test_add_menu_lists_every_formula():
    log = []
    menus.VIEW3D_MT_iteron_add.draw(type("M", (), {"layout": FakeLayout(log)})(), bpy.context)
    assert sum(1 for kind, name in log if kind == "operator") == len(REGISTRY)


def test_ramp_edit_is_rebaked(fractal):
    obj = fractal("mandelbulb", resolution=24)
    before = np.zeros(len(obj.data.vertices) * 4, dtype=np.float32)
    obj.data.color_attributes[colors.COLOR_ATTRIBUTE].data.foreach_get("color", before)
    material.ramp_node(obj).color_ramp.elements[0].color = (1.0, 0.0, 0.0, 1.0)
    bpy.context.view_layer.update()                    # fires depsgraph_update_post
    assert material.find(obj).name in colors._DIRTY
    colors.rebake_dirty()                               # what the debounced timer does
    after = np.zeros_like(before)
    obj.data.color_attributes[colors.COLOR_ATTRIBUTE].data.foreach_get("color", after)
    assert not np.allclose(before, after)
