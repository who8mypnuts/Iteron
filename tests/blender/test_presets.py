# SPDX-License-Identifier: MIT
"""User presets: save, list beside the built-in ones, apply, delete — in a temporary folder."""

import json

import pytest

import bpy
from iteron.bridge import presets
from iteron.bridge.props import group, read_values
from iteron.core.formula import REGISTRY


@pytest.fixture(autouse=True)
def preset_folder(tmp_path, monkeypatch):
    def folder(formula_id, create=False):
        path = tmp_path / formula_id
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path
    monkeypatch.setattr(presets, "folder", folder)
    return tmp_path


def test_save_list_apply_and_delete(fractal, preset_folder):
    obj = fractal("mandelbulb", resolution=24)
    group(obj.iteron).power = 5.5
    group(obj.iteron).julia_c = (0.1, 0.2, 0.3)
    bpy.ops.iteron.save_preset(name="Mine / 1")
    assert presets.user_presets("mandelbulb") == ["Mine _ 1"]
    saved = json.loads((preset_folder / "mandelbulb" / "Mine _ 1.json").read_text())
    assert saved["values"]["power"] == 5.5 and saved["values"]["julia_c"] == pytest.approx([0.1, 0.2, 0.3])
    bpy.ops.iteron.reset_formula()
    assert group(obj.iteron).power == 8.0
    bpy.ops.iteron.apply_preset(preset=presets.USER_PREFIX + "Mine _ 1")
    assert read_values(obj.iteron)["power"] == 5.5
    bpy.ops.iteron.delete_preset(preset="Mine _ 1")
    assert presets.user_presets("mandelbulb") == []


def test_a_preset_for_another_formula_is_refused(preset_folder):
    presets.save("mandelbulb", "Bulb", {"power": 3.0})
    (preset_folder / "menger_sponge").mkdir()
    (preset_folder / "menger_sponge" / "Bulb.json").write_text((preset_folder / "mandelbulb" / "Bulb.json").read_text())
    with pytest.raises(ValueError):
        presets.load(REGISTRY["menger_sponge"], "Bulb")


def test_a_hybrid_preset_brings_back_its_parts(fractal):
    obj = fractal("hybrid", resolution=24)
    bpy.ops.iteron.apply_preset(preset="Bulb + Menger")
    group(obj.iteron, "menger_sponge").offset = (1.0, 0.6, 1.0)
    bpy.ops.iteron.save_preset(name="Towers")
    bpy.ops.iteron.apply_preset(preset="Bulb + Box")
    group(obj.iteron, "menger_sponge").offset = (1.0, 1.0, 1.0)
    bpy.ops.iteron.apply_preset(preset=presets.USER_PREFIX + "Towers")
    assert group(obj.iteron).second == "menger_sponge"
    assert tuple(group(obj.iteron, "menger_sponge").offset) == pytest.approx((1.0, 0.6, 1.0))
