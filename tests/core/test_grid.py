# SPDX-License-Identifier: MIT
import numpy as np
import pytest

import iteron.formulas  # noqa: F401
from iteron.core.formula import REGISTRY
from iteron.core.grid import Bounds, check, estimated_bytes, fit, plan


def test_bounds_origin_and_spacing():
    b = Bounds(center=(1.0, 2.0, 3.0), size=4.0)
    np.testing.assert_allclose(b.origin(), [-1.0, 0.0, 1.0])
    assert b.spacing(5) == pytest.approx(1.0)


def test_plan_shape():
    origin, spacing, shape = plan(Bounds(size=2.0), 16)
    assert shape == (16, 16, 16)
    assert spacing == pytest.approx(2.0 / 15)


def test_check_flags_too_large_or_too_small():
    assert check(2, memory_limit_bytes=10**12)          # too small
    assert not check(64, memory_limit_bytes=10**12)      # fine
    assert check(64, memory_limit_bytes=1)               # too much memory


def test_estimated_bytes_grows_with_the_cube():
    assert estimated_bytes(128) > estimated_bytes(64)


def test_fit_shrinks_to_the_mandelbulb():
    formula_ = REGISTRY["mandelbulb"]
    big = Bounds(size=10.0)
    fitted = fit(formula_, {}, big, coarse=24)
    assert fitted.size < big.size


def test_fit_keeps_empty_bounds_unchanged():
    formula_ = REGISTRY["mandelbulb"]
    far_away = Bounds(center=(1000.0, 1000.0, 1000.0), size=1.0)
    fitted = fit(formula_, {}, far_away, coarse=8)
    assert fitted == far_away
