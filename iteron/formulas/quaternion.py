# SPDX-License-Identifier: MIT
"""Quaternion Julia sets: z² + c in four dimensions, seen through a 3D slice."""

from __future__ import annotations

from ..core import ops
from ..core.formula import DIRECT, formula
from ..core.params import Float, Int, Vec3


def _square(q):
    """q² for the quaternion (x; y, z, w) with x the real part."""
    return ops.vec4(q.x * q.x - q.y * q.y - q.z * q.z - q.w * q.w, 2.0 * q.x * q.y, 2.0 * q.x * q.z, 2.0 * q.x * q.w)


@formula("Quaternion Julia", family="Hypercomplex", kind=DIRECT, bounds=1.6,
         description="A quaternion Julia set, sliced at a chosen fourth coordinate",
         params=(Int("iterations", 12, min=1, max=64, description="Iterations per point"),
                 Vec3("c", (-0.2, 0.6, 0.2), min=-1.5, max=1.5, label="C", description="The first three components of C"),
                 Float("c_w", 0.0, min=-1.5, max=1.5, label="C w", description="The fourth component of C"),
                 Float("slice", 0.0, min=-1.5, max=1.5, description="The fourth coordinate of the 3D slice"),
                 Float("bailout", 4.0, min=2.0, max=64.0, hard_min=1.0, description="Radius beyond which a point has escaped")),
         presets={"Default": {}, "Coral": {"c": (-0.291, -0.399, 0.339), "c_w": 0.437},
                  "Dendrite": {"c": (-0.125, -0.256, 0.847), "c_w": 0.0}})
def quaternion_julia(pos, p):
    c = ops.vec4(p.c.x, p.c.y, p.c.z, p.c_w)
    bail2 = p.bailout * p.bailout

    def body(_i, state):
        q, dq, trap = state
        dq = 2.0 * ops.length(q) * dq
        q = _square(q) + c
        return q, dq, ops.min(trap, ops.dot(q, q))

    start = ops.vec4(pos.x, pos.y, pos.z, p.slice)
    (q, dq, trap), _n = ops.loop(p.iterations, 64, (start, 1.0, ops.dot(start, start)), body,
                                 until=lambda s: ops.dot(s[0], s[0]) > bail2)
    r = ops.max(ops.length(q), 1e-10)
    return 0.5 * r * ops.log(r) / dq, ops.sqrt(trap)
