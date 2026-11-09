# SPDX-License-Identifier: MIT
import math

import numpy as np
import pytest

from iteron.core.sym import Context
from iteron.core.vec import Vec3, Vec4
from .helpers import replay, value


def test_vec3_numpy_arithmetic():
    a = Vec3(np.array([1.0, 2.0]), np.array([3.0, 4.0]), np.array([5.0, 6.0]))
    b = Vec3(np.array([1.0, 1.0]), np.array([1.0, 1.0]), np.array([1.0, 1.0]))
    c = a + b * 2.0
    np.testing.assert_allclose(c.x, [3.0, 4.0])
    np.testing.assert_allclose(c.dot(c), c.x ** 2 + c.y ** 2 + c.z ** 2)


def test_vec3_length_and_normalize():
    v = Vec3(3.0, 4.0, 0.0)
    assert v.length() == pytest.approx(5.0)
    n = v.normalized()
    assert n.length() == pytest.approx(1.0)


def test_vec3_cross_is_perpendicular():
    a, b = Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0)
    c = a.cross(b)
    assert (c.x, c.y, c.z) == pytest.approx((0.0, 0.0, 1.0))


def test_vec3_symbolic_matches_numeric():
    ctx = Context()
    sym = Vec3(ctx.ref("ax"), ctx.ref("ay"), ctx.ref("az"))
    other = Vec3(2.0, 3.0, 4.0)
    result = (sym + other).dot(sym)
    namespace = replay(ctx.lines, {"ax": 1.0, "ay": 2.0, "az": 3.0})
    numeric = (Vec3(1.0, 2.0, 3.0) + other).dot(Vec3(1.0, 2.0, 3.0))
    assert value(namespace, result) == pytest.approx(numeric)


def test_vec3_select_picks_whole_points():
    # cond has one entry per point; select chooses a's or b's matching point, all three components together
    a = Vec3(np.array([1.0, 2.0]), np.array([1.0, 2.0]), np.array([1.0, 2.0]))
    b = Vec3(np.array([10.0, 20.0]), np.array([10.0, 20.0]), np.array([10.0, 20.0]))
    picked = a.select(np.array([True, False]), b)
    np.testing.assert_allclose(picked.x, [1.0, 20.0])
    np.testing.assert_allclose(picked.z, [1.0, 20.0])


def test_vec4_length():
    v = Vec4(1.0, 2.0, 2.0, 0.0)
    assert v.length() == pytest.approx(3.0)
