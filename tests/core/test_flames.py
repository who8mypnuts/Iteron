# SPDX-License-Identifier: MIT
"""Flames without Blender: the model round trip, the chaos game, density meshing, the bundled library and the
Fractalchemy file readers."""

import json

from pathlib import Path

import numpy as np
import pytest

from iteron.flames import chaos, density, formats, library, variations
from iteron.flames.model import Flame, XForm
from iteron.jobs.flame_pipeline import MESH, POINTS, FlameSpec, build
from iteron.jobs.steps import run_to_end


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "fractalchemy"
SAMPLES = ROOT / "sample_source" / "Fractalchemy" / "samples"


def sierpinski_triangle() -> Flame:
    corners = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    return Flame("triangle", [XForm(weight=1.0, color=i / 2, coefs=(0.5, 0.0, 0.0, 0.5, cx / 2, cy / 2))
                              for i, (cx, cy) in enumerate(corners)])


def test_a_flame_survives_the_dict_round_trip():
    flame = Flame.from_dict(library.bundled()["spiral_tower"])
    again = Flame.from_dict(json.loads(json.dumps(flame.to_dict())))
    assert again == flame


def test_the_chaos_game_lands_on_the_attractor():
    orbit = chaos.chaos_game(sierpinski_triangle(), 20_000, seed=3)
    x, y = orbit.points[:, 0], orbit.points[:, 1]
    assert len(orbit.points) == 20_000
    assert (x >= -1e-6).all() and (y >= -1e-6).all() and (x + y <= 1 + 1e-6).all()
    # the middle triangle (x, y < ½, x + y > ½) is the first hole of the gasket
    hole = (x < 0.49) & (y < 0.49) & (x + y > 0.51)
    assert hole.sum() == 0


def test_the_chaos_game_is_repeatable_and_seeded():
    a, b = (chaos.chaos_game(sierpinski_triangle(), 5_000, seed=7) for _ in range(2))
    c = chaos.chaos_game(sierpinski_triangle(), 5_000, seed=8)
    assert np.array_equal(a.points, b.points) and not np.array_equal(a.points, c.points)


def test_unknown_variations_are_reported_and_skipped():
    flame = sierpinski_triangle()
    flame.xforms[0].variations = {"linear": 1.0, "no_such_variation": 0.5}
    flame.final = XForm(variations={"also_missing": 1.0})
    orbit = chaos.chaos_game(flame, 2_000)
    assert orbit.unsupported == ("also_missing", "no_such_variation")
    assert np.ptp(orbit.points[:, 0]) > 0.5          # the unrunnable final transform did not collapse everything


def test_xaos_rows_steer_the_choice_of_transform():
    flame = sierpinski_triangle()
    for xform in flame.xforms:
        xform.chaos = [1.0, 0.0, 0.0]                 # only ever the first transform
    orbit = chaos.chaos_game(flame, 2_000)
    assert np.abs(orbit.points[:, :2]).max() < 1e-3


def test_the_registry_has_the_3d_variations_and_their_aliases():
    variations._load()
    assert len(variations.REGISTRY) >= 70
    for name in ("julia3D", "spherical3D", "curl3D", "linear3D", "zscale", "pre_blur"):
        assert variations.resolve(name) is not None, name
    assert variations.canonical("Spherical3D") == "spherical3D"


def test_blur_keeps_the_mass_and_trilinear_is_exact_on_linear_fields():
    volume = np.zeros((21, 21, 21), np.float32)
    volume[10, 10, 10] = 1.0
    assert abs(density.blur(volume, 1.5).sum() - 1.0) < 1e-4
    grid = np.indices((5, 6, 7)).astype(np.float64)
    field = 2 * grid[0] - grid[1] + 0.5 * grid[2]
    coords = np.random.default_rng(1).uniform(0, 4, (50, 3))
    assert np.allclose(density.trilinear(field, coords), 2 * coords[:, 0] - coords[:, 1] + 0.5 * coords[:, 2])


def test_a_dense_ball_of_points_meshes_to_a_closed_sphere():
    rng = np.random.default_rng(2)
    direction = rng.normal(size=(200_000, 3))
    points = direction / np.linalg.norm(direction, axis=1)[:, None] * rng.random(200_000)[:, None] ** (1 / 3)
    orbit = chaos.Orbit(points.astype(np.float32), np.full(len(points), 0.5, np.float32),
                        np.zeros(len(points), np.int16), chaos.palette_array([(255, 0, 0), (255, 0, 0)]), ())
    vertices, quads, colours, _plan = density.density_mesh(orbit, 48, 0.15, 1.0)
    radius = np.linalg.norm(vertices, axis=1)
    assert len(quads) > 500 and 0.85 < np.median(radius) < 1.1
    assert np.allclose(colours, [1.0, 0.0, 0.0], atol=1e-3)
    edges = np.sort(np.concatenate([quads[:, [i, (i + 1) % 4]] for i in range(4)]).astype(np.int64), axis=1)
    _keys, uses = np.unique(edges[:, 0] * len(vertices) + edges[:, 1], return_counts=True)
    assert (uses == 2).all()


@pytest.mark.parametrize("key", list(library.bundled()))
def test_every_bundled_flame_builds_as_points_and_as_a_solid(key):
    flame = library.bundled()[key]
    points = run_to_end(build(FlameSpec(flame, 30_000, output=POINTS)))
    assert len(points.vertices) > 25_000 and points.faces == 0 and not points.unsupported
    assert points.xform is not None and points.colours.shape == (len(points.vertices), 3)
    solid = run_to_end(build(FlameSpec(flame, 200_000, output=MESH, resolution=48)))
    assert solid.faces > 100 and solid.xform is None


def test_fa_samples_parse_and_iterate():
    files = sorted(SAMPLES.rglob("*.fa"))
    if not files:
        pytest.skip("Fractalchemy's samples are not in the checkout")
    for path in files:
        for flame in formats.read_fa(path):
            orbit = chaos.chaos_game(flame, 2_000)
            assert len(orbit.points) == 2_000 and np.isfinite(orbit.points).all()


def test_fa3d_fixture_reads_scene_lights_and_mesh_settings():
    scene = formats.read_fa3d(FIXTURES / "3d musk sphere.fa3d")
    assert scene.flame.xforms and scene.solid and scene.mesh["resolution"] == 128
    kinds = sorted(light.kind for light in scene.lights)
    assert kinds == ["distant", "point"]
    sun = next(light for light in scene.lights if light.kind == "distant")
    assert abs(np.linalg.norm(sun.direction) - 1.0) < 1e-9
    assert all(0.0 <= c <= 1.0 for c in scene.background)


def test_the_camera_frame_is_orthonormal_and_looks_at_the_target():
    scene = formats.read_fa3d(FIXTURES / "3d musk sphere.fa3d")
    frame = formats.camera_frame(scene.flame.camera)
    m = frame.matrix()[:3, :3]
    assert np.allclose(m.T @ m, np.eye(3), atol=1e-9) and np.linalg.det(m) > 0
    assert np.allclose(frame.location - frame.back * frame.distance, frame.target)


def test_the_camera_sees_what_fractalchemy_shows():
    """Fractal space has y down the screen: a point right of and below the centre there is so in Blender too."""
    from iteron.flames.model import Camera
    frame = formats.camera_frame(Camera(pitch=0.4, yaw=0.3, perspective=0.2))
    m = np.array(Camera(pitch=0.4, yaw=0.3).matrix())
    point = formats.TO_BLENDER @ (1.0 * m[:, 0] + 0.5 * m[:, 1])          # one right, half down in view terms
    seen = point - frame.location
    assert seen @ frame.right > 0.5 and seen @ frame.up < -0.25 and seen @ frame.back < 0


def test_wrong_files_raise_format_errors(tmp_path):
    (tmp_path / "x.fa").write_text('{"format": "other"}')
    (tmp_path / "y.fa3d").write_text("not json")
    with pytest.raises(formats.FormatError):
        formats.read_fa(tmp_path / "x.fa")
    with pytest.raises(formats.FormatError):
        formats.read_fa3d(tmp_path / "y.fa3d")
