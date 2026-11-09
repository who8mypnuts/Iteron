# SPDX-License-Identifier: MIT
"""A build result written into the object's mesh datablock, in place.

`foreach_set` on whole arrays (never `from_pydata`, far too slow for millions of faces). Refilling the existing
datablock keeps its materials, the object's modifiers and any linked duplicates.
"""

from __future__ import annotations

import numpy as np

from ..jobs.pipeline import CHANNELS, BuildResult

ATTRIBUTE_PREFIX = "iteron_"


def write(obj, result: BuildResult) -> None:
    mesh = obj.data
    materials = list(mesh.materials)
    mesh.clear_geometry()
    vertices, quads = result.vertices, result.quads
    mesh.vertices.add(len(vertices))
    mesh.vertices.foreach_set("co", vertices.astype(np.float32).ravel())
    mesh.loops.add(quads.size)
    mesh.loops.foreach_set("vertex_index", quads.astype(np.int32).ravel())
    mesh.polygons.add(len(quads))
    mesh.polygons.foreach_set("loop_start", np.arange(0, quads.size, 4, dtype=np.int32))
    mesh.update(calc_edges=True)
    for index, name in enumerate(CHANNELS):
        attribute = mesh.attributes.get(ATTRIBUTE_PREFIX + name) or mesh.attributes.new(ATTRIBUTE_PREFIX + name,
                                                                                         "FLOAT", "POINT")
        attribute.data.foreach_set("value", np.ascontiguousarray(result.channels[:, index], dtype=np.float32))
    if list(mesh.materials) != materials:          # clear_geometry keeps them; be certain
        mesh.materials.clear()
        for material in materials:
            mesh.materials.append(material)
    apply_shading(obj)


def apply_shading(obj) -> None:
    mesh = obj.data
    if len(mesh.polygons):
        mesh.polygons.foreach_set("use_smooth", np.full(len(mesh.polygons), obj.iteron.smooth, dtype=bool))
        mesh.update()
