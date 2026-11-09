# SPDX-License-Identifier: MIT
"""The whole Phase 1 pipeline, numpy-only: fit a box, sample the field, mesh it (PLAN.md §2 end to end)."""

from __future__ import annotations

import numpy as np
import pytest

import iteron.formulas  # noqa: F401
from iteron.core.cpu_eval import evaluate, evaluate_grid
from iteron.core.formula import REGISTRY
from iteron.core.grid import Bounds, fit, plan
from iteron.core.surface_nets import surface_nets

ONE_OF_EACH_KIND = ["mandelbulb", "mandelbox", "menger_sponge", "octahedral_kifs", "quaternion_julia"]


@pytest.mark.parametrize("formula_id", ONE_OF_EACH_KIND)
def test_builds_a_watertight_looking_mesh(formula_id):
    formula_ = REGISTRY[formula_id]
    bounds = fit(formula_, {}, Bounds(size=2.4 * formula_.bounds), coarse=28)
    origin, spacing, shape = plan(bounds, 48)
    field, _trap = evaluate_grid(formula_, {}, origin, spacing, shape)
    mesh = surface_nets(field, spacing * 0.5, origin, spacing)
    assert len(mesh) > 50, f"{formula_id} produced almost no geometry at this resolution"
    assert np.isfinite(mesh.vertices).all()
    assert mesh.normals is not None and np.isfinite(mesh.normals).all()


def test_gradient_normals_point_outward():
    from iteron.core.cpu_eval import gradient_normals

    formula_ = REGISTRY["mandelbulb"]
    points = np.array([[1.1, 0.0, 0.0], [0.0, 1.1, 0.0]])
    normals = gradient_normals(formula_, {}, points)
    assert np.isfinite(normals).all()
    norms = np.linalg.norm(normals, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-4)
    # the distance field increases outward, so its gradient roughly follows the point direction
    assert np.dot(normals[0], [1.0, 0.0, 0.0]) > 0
    assert np.dot(normals[1], [0.0, 1.0, 0.0]) > 0


def test_vertex_colour_pass_matches_the_same_formula():
    """The per-vertex trap pass (what `bridge.mesh_write` bakes into the colour attribute) re-uses `cpu_eval`
    directly on the mesh's own vertices, so it's always in step with the mesh that produced them."""
    formula_ = REGISTRY["mandelbulb"]
    bounds = fit(formula_, {}, Bounds(size=2.6), coarse=24)
    origin, spacing, shape = plan(bounds, 32)
    field, _trap = evaluate_grid(formula_, {}, origin, spacing, shape)
    mesh = surface_nets(field, spacing * 0.5, origin, spacing)
    assert len(mesh) > 0
    _distance, trap = evaluate(formula_, {}, mesh.vertices.astype(np.float64))
    assert trap.shape[0] == mesh.vertices.shape[0]
    assert np.isfinite(trap).all()
