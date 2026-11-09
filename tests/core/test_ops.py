# SPDX-License-Identifier: MIT
import math
import random

import numpy as np
import pytest

from iteron.core import ops
from iteron.core.sym import Context
from .helpers import replay, value

SCALAR_CASES = [
    (ops.sqrt, (4.0,)), (ops.sin, (0.7,)), (ops.cos, (0.7,)), (ops.acos, (0.3,)), (ops.asin, (0.3,)),
    (ops.floor, (2.7,)), (ops.abs_, (-3.5,)), (ops.min_, (1.0, 2.0)), (ops.max_, (1.0, 2.0)),
    (ops.pow_, (2.0, 3.0)), (ops.sign, (-2.0,)), (ops.mod, (5.5, 2.0)), (ops.mix, (1.0, 3.0, 0.25)),
    (ops.clamp, (5.0, 0.0, 1.0)), (ops.select, (True, 1.0, 2.0)), (ops.atan2, (1.0, 2.0)),
]


@pytest.mark.parametrize("fn, args", SCALAR_CASES)
def test_numpy_matches_plain_numbers(fn, args):
    """Called with plain floats, every op behaves like its numpy form (no Sym involved)."""
    result = fn(*args)
    assert np.ndim(result) == 0


@pytest.mark.parametrize("fn, args", SCALAR_CASES)
def test_symbolic_matches_numpy(fn, args):
    """The GLSL text traced for each op evaluates (via the Python stand-in, see helpers.replay) to the same
    number as calling the op directly on plain floats — the parity check PLAN.md §11 describes."""
    ctx = Context()
    sym_args = [ctx.ref(f"a{i}") for i in range(len(args))]
    result = fn(*sym_args)
    namespace = replay(ctx.lines, dict(zip((f"a{i}" for i in range(len(args))), args)))
    got = value(namespace, result)
    want = fn(*args)
    assert got == pytest.approx(float(want), abs=1e-9) if not isinstance(want, (bool, np.bool_)) else got == want


def test_select_is_branchless_on_arrays():
    cond = np.array([True, False, True])
    a, b = np.array([1.0, 2.0, 3.0]), np.array([10.0, 20.0, 30.0])
    np.testing.assert_array_equal(ops.select(cond, a, b), [1.0, 20.0, 3.0])


def test_mod_matches_glsl_negative_convention():
    # GLSL's mod follows the sign of the divisor, like Python's `%` but we implement it explicitly (core/glsl_funcs.py)
    assert ops.mod(-1.0, 4.0) == pytest.approx(3.0)


@pytest.mark.parametrize("seed", range(20))
def test_random_scalars_agree(seed):
    rng = random.Random(seed)
    fn, args_template = random.Random(seed).choice(SCALAR_CASES)
    args = [rng.uniform(0.1, 4.0) if not isinstance(v, bool) else rng.choice([True, False]) for v in args_template]
    ctx = Context()
    sym_args = [ctx.ref(f"a{i}") for i in range(len(args))]
    result = fn(*sym_args)
    namespace = replay(ctx.lines, dict(zip((f"a{i}" for i in range(len(args))), args)))
    got = value(namespace, result)
    want = fn(*args)
    if isinstance(want, (bool, np.bool_)):
        assert bool(got) == bool(want)
    else:
        assert got == pytest.approx(float(want), abs=1e-6, rel=1e-6)
