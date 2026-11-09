# SPDX-License-Identifier: MIT
from pathlib import Path

import pytest

from iteron.interop.fa3d import Fa3dFormatError, parse_file, parse_text

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "fractalchemy"


def test_parses_the_sample_fa3d_scene():
    scene = parse_file(FIXTURES / "musk_sphere.fa3d")
    assert scene.name
    assert len(scene.fractal.xforms) == 10
    assert scene.fractal.final is not None
    assert "julia3D" in scene.fractal.variation_names or "curl3D" in scene.fractal.variation_names


def test_lights_and_materials_round_trip_enough_to_place_in_blender():
    scene = parse_file(FIXTURES / "musk_sphere.fa3d")
    assert len(scene.lights) == 2
    kinds = {light.kind for light in scene.lights}
    assert kinds == {"point", "distant"}
    # one material per transform, plus one for the final transform
    assert len(scene.materials) == len(scene.fractal.xforms) + 1
    material = scene.material_for(0)
    assert 0.0 <= material.diffuse <= 1.0


def test_environment_and_mesh_settings():
    scene = parse_file(FIXTURES / "musk_sphere.fa3d")
    assert scene.environment.visible is True
    assert scene.mesh.resolution == 128
    assert scene.mesh.target_faces == 200_000


def test_material_for_beyond_the_list_clamps_to_the_last():
    scene = parse_file(FIXTURES / "musk_sphere.fa3d")
    assert scene.material_for(999) is scene.material_for(len(scene.materials) - 1)


def test_rejects_non_fa3d_text():
    with pytest.raises(Fa3dFormatError):
        parse_text('{"format": "fractalchemy", "flames": []}')
