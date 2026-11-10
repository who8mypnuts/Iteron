# SPDX-License-Identifier: MIT
"""A build result written into the object's mesh datablock, in place.

`foreach_set` on whole arrays (never `from_pydata`, far too slow for millions of faces). Refilling the existing
datablock keeps its materials, the object's modifiers and any linked duplicates. Quads come first, then any
triangles simplification left. Field normals become Blender custom normals.
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
    tris = result.tris if result.tris is not None else np.zeros((0, 3), dtype=np.int32)
    corners = np.concatenate([quads.astype(np.int32).ravel(), tris.astype(np.int32).ravel()])
    starts = np.concatenate([np.arange(0, quads.size, 4), quads.size + np.arange(0, tris.size, 3)]).astype(np.int32)
    mesh.vertices.add(len(vertices))
    mesh.vertices.foreach_set("co", vertices.astype(np.float32).ravel())
    mesh.loops.add(corners.size)
    mesh.loops.foreach_set("vertex_index", corners)
    mesh.polygons.add(len(starts))
    mesh.polygons.foreach_set("loop_start", starts)
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
    if result.normals is not None and len(vertices):
        normals = np.nan_to_num(result.normals, nan=0.0)   # a zero custom normal means "keep Blender's own"
        mesh.normals_split_custom_set_from_vertices(normals)


def apply_shading(obj) -> None:
    """Smooth or flat faces; switching away from field normals drops the custom normals."""
    mesh = obj.data
    if not len(mesh.polygons):
        return
    mode = obj.iteron.shading
    if mode == "FLAT":
        mesh.shade_flat()           # (Blender 4.1+: instant, unlike setting every face's flag)
    else:
        mesh.shade_smooth()
    if mode != "FIELD" and mesh.has_custom_normals:
        mesh.normals_split_custom_set_from_vertices(np.zeros((len(mesh.vertices), 3), dtype=np.float32))
    mesh.update()
