# SPDX-License-Identifier: MIT
from pathlib import Path

import pytest

from iteron.interop.fa import FaFormatError, parse_file, parse_text

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "fractalchemy"


def test_parses_the_sample_fa_file():
    flames = parse_file(FIXTURES / "anew.fa")
    assert len(flames) == 1
    flame = flames[0]
    assert flame.name
    assert len(flame.xforms) > 0
    assert len(flame.palette) == 256
    assert all(len(c) == 3 for c in flame.palette)


def test_xform_has_usable_affine_and_variations():
    flame = parse_file(FIXTURES / "anew.fa")[0]
    first = flame.xforms[0]
    assert len(first.coefs) == 6
    assert isinstance(first.variations, dict)
    assert len(first.variations) > 0


def test_rejects_non_fa_text():
    with pytest.raises(FaFormatError):
        parse_text("{}")
    with pytest.raises(FaFormatError):
        parse_text("not json at all")


def test_missing_keys_take_defaults():
    flames = parse_text('{"format": "fractalchemy", "version": 1, "flames": [{}]}')
    assert len(flames) == 1
    assert flames[0].name == "flame"
    assert flames[0].xforms == []
    assert flames[0].final is None
