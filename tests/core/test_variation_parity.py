# SPDX-License-Identifier: MIT
"""Iteron's flame variations against Fractalchemy's own (read from the sample sources at test time, never bundled):
the same points, parameters, affine and random stream must give the same result."""

import sys

from pathlib import Path

import numpy as np
import pytest

from iteron.flames import variations as iteron_variations


ROOT = Path(__file__).resolve().parents[2]
FRACTALCHEMY = ROOT / "sample_source" / "Fractalchemy"
WRITTEN_HERE = {"julia3D", "spherical3D"}       # written from the published maths, not ported


@pytest.fixture(scope="module")
def theirs():
    if not (FRACTALCHEMY / "fractalchemy").is_dir():
        pytest.skip("Fractalchemy's sources are not in the checkout")
    sys.path.insert(0, str(FRACTALCHEMY))
    try:
        from fractalchemy import formulas
        from fractalchemy.fractal import variations
        formulas.load_all()
    except Exception as error:                     # pragma: no cover - depends on the sample checkout
        pytest.skip(f"Fractalchemy does not import here: {error}")
    finally:
        sys.path.remove(str(FRACTALCHEMY))
    return variations


def _names():
    iteron_variations._load()
    return sorted(set(iteron_variations.REGISTRY) - WRITTEN_HERE)


@pytest.mark.parametrize("name", _names())
def test_variation_matches_fractalchemy(theirs, name):
    other = theirs.resolve(name)
    if other is None:
        pytest.skip(f"Fractalchemy has no {name}")
    ours = iteron_variations.REGISTRY[name]
    rng = np.random.default_rng(3)
    x, y, z, px, py, pz = (rng.uniform(-1.5, 1.5, 64) for _ in range(6))
    coefs = (0.9, 0.2, -0.3, 0.8, 0.1, -0.2)
    params = {key: (value if value else 0.7) for key, value in ours.params.items()}
    their_params = dict(params)
    if other.prepare:
        their_params.update(other.prepare(their_params, 0.8, coefs, np.random.default_rng(1)))
    mine = iteron_variations.Point(x, y, z, px, py, pz, 0.8, coefs, params, np.random.default_rng(5))
    fc = theirs.Point(x, y, 0.8, coefs, their_params, np.random.default_rng(5), z=z, px=px, py=py, pz=pz)
    with np.errstate(all="ignore"):
        a, b = ours.apply(mine), other.apply(fc)[:6]
    for u, v in zip(a, b):
        assert np.allclose(np.broadcast_to(u, x.shape), np.broadcast_to(v, x.shape), rtol=1e-6, atol=1e-9,
                           equal_nan=True)
