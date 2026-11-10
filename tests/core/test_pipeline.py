# SPDX-License-Identifier: MIT
"""The build pipeline end to end on the CPU: closed meshes, blocks that agree, vertices on the surface, calibration,
simplification."""

import numpy as np
import pytest

import iteron.formulas  # noqa: F401
from iteron.core import blocks, cpu_eval
from iteron.core.formula import REGISTRY
from iteron.jobs.cpu_sampler import CpuSampler
from iteron.jobs.pipeline import BuildSpec, build
from iteron.jobs.steps import run_to_end


def _build(fid, **options):
    return run_to_end(build(BuildSpec(fid, {}, **options), CpuSampler()))


def _edge_uses(result):
    faces = [result.quads[:, [i, (i + 1) % 4]] for i in range(4)]
    if result.tris is not None:
        faces += [result.tris[:, [i, (i + 1) % 3]] for i in range(3)]
    edges = np.sort(np.concatenate(faces).astype(np.int64), axis=1)
    _keys, counts = np.unique(edges[:, 0] * len(result.vertices) + edges[:, 1], return_counts=True)
    return counts


@pytest.mark.parametrize("fid", list(REGISTRY))
def test_every_formula_builds_a_closed_manifold_mesh(fid):
    result = _build(fid, resolution=56, refine_steps=1)
    assert result.faces > 100
    assert (_edge_uses(result) == 2).all()


def test_many_blocks_give_the_same_mesh_as_one(monkeypatch):
    one = _build("mandelbulb", resolution=60, refine_steps=0, field_normals=False)
    monkeypatch.setattr(blocks, "BLOCK", 20)
    many = _build("mandelbulb", resolution=60, refine_steps=0, field_normals=False)
    assert len(many.quads) == len(one.quads) and len(many.vertices) == len(one.vertices)
    assert np.allclose(np.sort(many.vertices, axis=0), np.sort(one.vertices, axis=0), atol=1e-5)


def test_refinement_puts_the_vertices_on_the_surface():
    entry = REGISTRY["mandelbulb"]
    plain = _build("mandelbulb", resolution=64, refine_steps=0, field_normals=False)
    refined = _build("mandelbulb", resolution=64, refine_steps=2)
    level = 0.5 * refined.plan.spacing * refined.gain
    error = lambda r: np.abs(cpu_eval.evaluate(entry, entry.values(), r.vertices.astype(float))[:, 0] - level)
    assert np.percentile(error(refined), 95) < 0.2 * np.percentile(error(plain), 95)
    assert np.allclose(np.linalg.norm(refined.normals, axis=1), 1.0, atol=1e-4)


def test_calibration_tells_underestimating_estimators_from_exact_ones():
    assert _build("mandelbox", resolution=64).gain < 0.45
    assert _build("menger_sponge", resolution=64).gain > 0.8


def test_simplification_keeps_the_mesh_closed_and_flat_parts_coarse():
    full = _build("menger_sponge", resolution=96, simplify=0.0)
    reduced = _build("menger_sponge", resolution=96, simplify=0.1)
    assert reduced.faces < 0.8 * full.faces
    assert (_edge_uses(reduced) == 2).all()


def test_the_cut_plane_removes_one_side_and_closes_the_face():
    whole = _build("mandelbulb", resolution=56)
    cut = run_to_end(build(BuildSpec("mandelbulb", {"cut": True, "cut_axis": "Z", "cut_offset": 0.1}, resolution=56),
                           CpuSampler()))
    assert cut.vertices[:, 2].max() <= 0.1 + cut.plan.spacing
    assert whole.vertices[:, 2].max() > 0.5
    assert (_edge_uses(cut) == 2).all()


@pytest.mark.parametrize("fid", ["amazing_surf", "menger_sponge", "mandelbulb"])
def test_simplified_vertices_stay_inside_the_grid(fid):
    """Vertices refined just outside the grid must not throw a merged vertex far away (cell keys were once negative)."""
    result = _build(fid, resolution=64, simplify=0.2, refine_steps=2)
    lo = np.asarray(result.plan.origin) - 2 * result.plan.spacing
    hi = np.asarray(result.plan.origin) + (np.asarray(result.plan.shape) + 1) * result.plan.spacing
    assert (result.vertices >= lo).all() and (result.vertices <= hi).all()
