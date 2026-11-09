# SPDX-License-Identifier: MIT
from pathlib import Path

import pytest

from iteron.interop.fragment import document, presets
from iteron.interop.fragment.annotations import parse as parse_params
from iteron.interop.fragment.preprocess import MissingIncludeError, resolve
from iteron.interop.fragment.reader import read_file

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "fractalchemy"
FRAG = FIXTURES / "pseudo_kleinian.fafrag"


def test_splits_the_fractalchemy_metadata_block():
    text = FRAG.read_text(encoding="utf-8")
    body, metadata = document.split(text)
    assert "[fractalchemy]" not in body
    assert metadata == {"tabs": {"origin": "Examples/Knighty Collection/PseudoKleinian.frag"}, "version": 1}


def test_plain_frag_without_a_metadata_block_is_untouched():
    body, metadata = document.split("#info nothing here\nfloat DE(vec3 p) { return length(p) - 1.0; }\n")
    assert metadata is None
    assert "DE(vec3 p)" in body


def test_parses_the_annotated_uniforms():
    params = parse_params(FRAG.read_text(encoding="utf-8"))
    by_name = {p.name: p for p in params}
    assert by_name["MI"].kind == "int" and by_name["MI"].default == 5
    assert by_name["Size"].default == pytest.approx(1.0)
    assert by_name["CSize"].kind == "vec3" and by_name["CSize"].default == pytest.approx((1.0, 1.0, 1.0))
    assert "Maximum iterations" in by_name["MI"].description


def test_parses_every_preset():
    found = presets.parse(FRAG.read_text(encoding="utf-8"))
    assert set(found) == {"Default", "P3", "Kleinian Forest"}
    assert found["Default"]["MI"] == 5.0
    assert found["Default"]["CycleColors"] is True
    assert found["Default"]["Eye"] == pytest.approx((1.44674, 0.992411, -0.508827))


def test_includes_resolve_through_the_bundled_shims_not_fragm():
    text = FRAG.read_text(encoding="utf-8")
    body, _metadata = document.split(text)
    expanded = resolve(body, beside=FRAG)
    assert "rotationMatrix3" in expanded.source          # from our MathUtils.frag shim
    assert "orbitTrap" in expanded.source                 # from our DE-Raytracer.frag shim
    assert all(p.parent.name == "shims" for p in expanded.resolved)


def test_missing_include_is_reported_by_name():
    with pytest.raises(MissingIncludeError, match="NoSuchFile.frag"):
        resolve('#include "NoSuchFile.frag"\n')


def test_read_file_end_to_end():
    fragment = read_file(FRAG)
    assert fragment.metadata is not None
    assert len(fragment.params) >= 7
    assert "Default" in fragment.presets
    assert "float DE(vec3 p)" in fragment.glsl
    assert len(fragment.includes) == 2
