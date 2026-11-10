# SPDX-License-Identifier: MIT
"""Hybrids: composition, what they store, their presets, and the Mandelbulb3D rule that a hybrid of a formula
with itself is that formula iterated twice as often."""

import numpy as np
import pytest

import iteron.formulas  # noqa: F401
from iteron.core import cpu_eval
from iteron.core.formula import REGISTRY, concrete
from iteron.formulas import hybrid


def test_a_hybrid_stores_its_choices_and_takes_its_parts_parameters():
    entry = hybrid.compose({"first": "mandelbulb", "second": "menger_sponge"})
    names = {p.name for p in entry.params}
    assert {"a_power", "b_scale", "b_offset", "first", "second_steps", "iterations", "cut"} <= names
    assert "a_iterations" not in names and "a_power" not in entry.stored and "first" in entry.stored
    assert entry.shape is None and entry.distance == REGISTRY["mandelbulb"].distance
    assert hybrid.compose({"first": "menger_sponge", "second": "mandelbulb"}).shape is not None


def test_the_parts_are_the_step_formulas():
    ids = {f.id for f in hybrid.parts()}
    assert {"mandelbulb", "mandelbox", "menger_sponge"} <= ids
    assert not ids & {"hybrid", "quaternion_julia", "mosely_snowflake"}


@pytest.mark.parametrize("name", list(hybrid.PRESETS))
def test_presets_only_set_parameters_their_hybrid_has(name):
    values = hybrid.PRESETS[name]
    entry = concrete(REGISTRY["hybrid"], values)
    assert set(values) <= {p.name for p in entry.params}


def test_a_formula_hybridised_with_itself_is_iterated_twice_as_often():
    rng = np.random.default_rng(4)
    points = rng.uniform(-0.6, 0.6, (4000, 3))
    twin = hybrid.compose({"first": "mandelbulb", "second": "mandelbulb"})
    doubled = twin.values({"first": "mandelbulb", "second": "mandelbulb", "iterations": 4, "a_power": 8.0,
                           "b_power": 8.0})
    bulb = REGISTRY["mandelbulb"]
    a = cpu_eval.evaluate(twin, doubled, points)
    b = cpu_eval.evaluate(bulb, bulb.values({"iterations": 8}), points)
    kept = (np.abs(a[:, 0]) < 0.5) & (np.abs(b[:, 0]) < 0.5)          # orbits that never escaped
    assert kept.sum() > 100
    assert np.allclose(a[kept, 0], b[kept, 0], rtol=1e-5, atol=1e-7)   # the same orbit: the same estimate


def test_steps_repeat_a_part_within_an_iteration():
    rng = np.random.default_rng(5)
    points = rng.uniform(-1.0, 1.0, (2000, 3))
    entry = hybrid.compose({"first": "mandelbulb", "second": "mandelbox"})
    one = cpu_eval.evaluate(entry, entry.values({"first_steps": 1}), points)
    two = cpu_eval.evaluate(entry, entry.values({"first_steps": 2}), points)
    assert not np.allclose(one[:, 0], two[:, 0])
