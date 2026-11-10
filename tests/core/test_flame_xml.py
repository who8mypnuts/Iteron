# SPDX-License-Identifier: MIT
"""Apophysis / flam3 `.flame` files: the reader's rules on a small file, and every sample flame read the same as
Fractalchemy's own reader reads it (at test time, from the sample sources — never bundled)."""

import sys
from pathlib import Path

import numpy as np
import pytest

from iteron.flames import chaos
from iteron.flames.flame_xml import read_flame, split_variations
from iteron.flames.formats import FormatError
from iteron.flames.variations import canonical, resolve

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = sorted((ROOT / "sample_source" / "Fractalchemy" / "samples").rglob("*.flame"))
FRACTALCHEMY = ROOT / "sample_source" / "Fractalchemy"
SMALL = """<Flames name="test">
<flame name="two" size="640 480" center="0.5 -0.25" scale="100" angle="0.5" cam_pitch="0.3" cam_dist="4"
       background="1 0 0">
  <xform weight="0.5" color="0" symmetry="0.5" linear="1" julian="0.5" julian_power="3" julian_dist="1"
         mystery="0.2" mystery_amount="3" coefs="0.5 0 0 0.5 0 0" chaos="1 0"/>
  <xform weight="0.5" color="1" color_speed="0.25" spherical="1" coefs="0.5 0 0 0.5 0.5 0" post="1 0 0 1 0.1 0"/>
  <finalxform color="0" symmetry="1" linear="1" coefs="1 0 0 1 0 0"/>
  <palette count="2" format="RGB">ff000000ff00</palette>
</flame>
<flame name="empty"/>
</Flames>"""


def test_a_small_file_reads_as_apophysis_means_it(tmp_path):
    path = tmp_path / "two.flame"
    path.write_text(SMALL)
    [flame] = read_flame(path)                                         # the flame without transforms is skipped
    assert flame.name == "two" and flame.palette == [(255, 0, 0), (0, 255, 0)] and flame.background == (255, 0, 0)
    camera = flame.camera
    assert camera.center == (0.5, -0.25) and camera.rotate == pytest.approx(-0.5 * 180 / np.pi)
    assert camera.pitch == 0.3 and camera.perspective == 0.25 and (camera.width, camera.height) == (640, 480)
    first, second = flame.xforms
    assert first.color_speed == 0.25 and second.color_speed == 0.25     # symmetry 0.5 → speed 0.25
    assert first.variations == {"linear": 1.0, "julian": 0.5, "mystery": 0.2}
    assert first.params["julian_power"] == 3.0 and first.params["mystery_amount"] == 3.0
    assert first.chaos == [1.0, 0.0] and second.post == (1.0, 0.0, 0.0, 1.0, 0.1, 0.0)
    assert flame.final is not None and flame.final.color_speed == 0.0
    orbit = chaos.chaos_game(flame, 2_000)
    assert orbit.unsupported == ("mystery",) and len(orbit.points) == 2_000


def test_pre_and_post_variations_are_variations():
    variations, params = split_variations({"pre_blur": "0.2", "post_rotate_x": "0.1", "coefs": "1 0 0 1 0 0"})
    assert variations == {"pre_blur": 0.2, "post_rotate_x": 0.1} and params == {}


def test_broken_files_raise_format_errors(tmp_path):
    (tmp_path / "bad.flame").write_text("<Flames><flame")
    (tmp_path / "none.flame").write_text("<Flames><flame name='x'/></Flames>")
    for name in ("bad.flame", "none.flame"):
        with pytest.raises(FormatError):
            read_flame(tmp_path / name)


@pytest.fixture(scope="module")
def theirs():
    if not (FRACTALCHEMY / "fractalchemy").is_dir() or not SAMPLES:
        pytest.skip("Fractalchemy's sources and samples are not in the checkout")
    sys.path.insert(0, str(FRACTALCHEMY))
    try:
        from fractalchemy import formulas
        from fractalchemy.fractal.formats import flame_xml
        formulas.load_all()
    except Exception as error:                     # pragma: no cover - depends on the sample checkout
        pytest.skip(f"Fractalchemy does not import here: {error}")
    finally:
        sys.path.remove(str(FRACTALCHEMY))
    return flame_xml


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.name)
def test_sample_flames_read_as_fractalchemy_reads_them(theirs, path):
    ours, reference = read_flame(path), theirs.parse_file(path)
    assert [f.name for f in ours] == [f.name for f in reference]
    for mine, other in zip(ours, reference):
        for key, value in other.camera.__dict__.items():
            assert np.allclose(getattr(mine.camera, key), value), key
        assert mine.palette == other.palette
        assert len(mine.xforms) == len(other.xforms)
        for a, b in zip(mine.xforms + [mine.final] * bool(mine.final), other.xforms + [other.final] * bool(other.final)):
            assert a.coefs == pytest.approx(b.coefs) and a.post == pytest.approx(b.post)
            assert (a.weight, a.color, a.color_speed, a.opacity) == pytest.approx((b.weight, b.color, b.color_speed,
                                                                                   b.opacity))
            assert a.chaos == b.chaos
            assert _known(a.variations) == pytest.approx(_known(b.variations))


def _known(variations: dict) -> dict:
    """Weights by Iteron's canonical name, aliases summed (`linear` + `linear3D`), of the variations Iteron runs."""
    out: dict = {}
    for name, weight in variations.items():
        if resolve(name) is not None:
            out[canonical(name)] = out.get(canonical(name), 0.0) + weight
    return out


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.name)
def test_sample_flames_iterate(path):
    """(One sample flame is degenerate — a polynomial with zero coefficients, whose orbit is all NaN — and yields
    nothing; the rest yield finite points.)"""
    orbits = [chaos.chaos_game(flame, 1_000) for flame in read_flame(path)]
    assert all(np.isfinite(o.points).all() for o in orbits)
    assert sum(len(o.points) == 1_000 for o in orbits) >= len(orbits) - 1
