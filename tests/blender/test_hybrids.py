# SPDX-License-Identifier: MIT
"""Hybrids in Blender: the object stores only its choices, the parts' values are their own groups', the panel
draws them, presets switch the parts, and editing a part makes the hybrid stale."""

import pytest

import bpy
from iteron.bridge import state
from iteron.bridge.kinds import FormulaKind
from iteron.bridge.props import group, read_values
from iteron.ui import panel

from .test_ui import FakeLayout


@pytest.fixture
def hybrid(fractal):
    return fractal("hybrid", resolution=40)


def test_the_hybrid_group_keeps_only_its_own_choices(hybrid):
    own = group(hybrid.iteron)
    assert "first" in own.bl_rna.properties and "a_power" not in own.bl_rna.properties
    values = read_values(hybrid.iteron)
    assert values["a_power"] == group(hybrid.iteron, "mandelbulb").power
    assert values["b_scale"] == group(hybrid.iteron, "mandelbox").scale
    assert len(hybrid.data.polygons) > 100, hybrid.iteron.message


def test_editing_a_part_makes_the_hybrid_stale(hybrid):
    assert not state.is_stale(hybrid)
    group(hybrid.iteron, "mandelbulb").power = 5.0
    assert state.is_stale(hybrid)


def test_a_preset_switches_the_parts_and_their_values(hybrid):
    bpy.ops.iteron.apply_preset(preset="Bulb + Menger")
    own = group(hybrid.iteron)
    assert (own.first, own.second) == ("mandelbulb", "menger_sponge")
    entry = FormulaKind.entry(hybrid)
    assert "b_offset" in {p.name for p in entry.params}
    FormulaKind.write(hybrid, {"b_scale": 2.5})
    assert group(hybrid.iteron, "menger_sponge").scale == pytest.approx(2.5)


def test_the_panel_draws_the_parts_parameters_from_their_groups(hybrid):
    log = []
    panel.draw_fractal(FakeLayout(log), hybrid)
    shown = {name for kind, name in log if kind == "prop"}
    assert {"first", "second", "power", "scale", "fold_limit"} <= shown
