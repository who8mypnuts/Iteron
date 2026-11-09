# SPDX-License-Identifier: MIT
import pytest

import iteron.formulas  # noqa: F401
from iteron.core.formula import DIRECT, ESCAPE, REGISTRY
from iteron.core.glsl import build_function


@pytest.mark.parametrize("formula_", sorted(REGISTRY.values(), key=lambda f: f.id), ids=lambda f: f.id)
def test_build_function_shape(formula_):
    source, uniforms = build_function(formula_, {})
    assert "float iteron_de(vec3 p, out float trap)" in source
    body = source.split("float iteron_de(vec3 p, out float trap)", 1)[1]
    assert body.count("return") == 1
    non_static_names = {p.name for p in formula_.all_params() if not p.static}
    assert {name for _type, name in uniforms} == non_static_names
    if formula_.kind == ESCAPE:
        assert "for (int _i = 0;" in source
        assert "break;" in source
    if formula_.kind != DIRECT:
        assert "trap" in source


@pytest.mark.parametrize("formula_", sorted(REGISTRY.values(), key=lambda f: f.id), ids=lambda f: f.id)
def test_never_redeclares_the_trap_out_parameter(formula_):
    """`trap` is already `iteron_de`'s `out` parameter; declaring a local of the same name (`float trap = …;`)
    would shadow it and silently drop the result \u2014 GLSL also just rejects it as a redefinition."""
    source, _uniforms = build_function(formula_, {})
    body = source.split("out float trap)", 1)[1]
    assert "float trap" not in body


def test_static_change_alters_the_source_but_not_the_uniform_list():
    formula_ = REGISTRY["mandelbulb"]
    default_source, default_uniforms = build_function(formula_, {})
    rotated_source, rotated_uniforms = build_function(formula_, {"rotation_axis": (1.0, 0.0, 0.0)})
    assert default_source != rotated_source
    assert default_uniforms == rotated_uniforms


def test_uniform_types_are_known_glsl_types():
    from iteron.core.glsl import glsl_type_name

    for formula_ in REGISTRY.values():
        _source, uniforms = build_function(formula_, {})
        for glsl_type, _name in uniforms:
            assert glsl_type_name(glsl_type)
