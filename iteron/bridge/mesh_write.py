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


def fill(mesh, vertices: np.ndarray, quads: np.ndarray, tris: np.ndarray | None = None) -> None:
    """Replace the mesh's geometry (quads first, then triangles; no faces at all for a point cloud)."""
    materials = list(mesh.materials)
    mesh.clear_geometry()
    tris = tris if tris is not None else np.zeros((0, 3), dtype=np.int32)
    corners = np.concatenate([quads.astype(np.int32).ravel(), tris.astype(np.int32).ravel()])
    starts = np.concatenate([np.arange(0, quads.size, 4), quads.size + np.arange(0, tris.size, 3)]).astype(np.int32)
    mesh.vertices.add(len(vertices))
    mesh.vertices.foreach_set("co", np.asarray(vertices, dtype=np.float32).ravel())
    mesh.loops.add(corners.size)
    mesh.loops.foreach_set("vertex_index", corners)
    mesh.polygons.add(len(starts))
    mesh.polygons.foreach_set("loop_start", starts)
    mesh.update(calc_edges=True)
    if list(mesh.materials) != materials:          # clear_geometry keeps them; be certain
        mesh.materials.clear()
        for material in materials:
            mesh.materials.append(material)


def attribute(mesh, name: str, values: np.ndarray, kind: str = "FLOAT", domain: str = "POINT") -> None:
    """Create or refill a mesh attribute (`FLOAT`, `INT`, `FLOAT_VECTOR` or `FLOAT_COLOR` from `(V,)`, `(V, 3)` or
    `(V, 4)` values)."""
    existing = mesh.attributes.get(name)
    if existing is not None and existing.data_type != kind:
        mesh.attributes.remove(existing)
        existing = None
    layer = existing or mesh.attributes.new(name, kind, domain)
    field = {"FLOAT": "value", "INT": "value", "FLOAT_COLOR": "color", "FLOAT_VECTOR": "vector"}[kind]
    dtype = np.int32 if kind == "INT" else np.float32
    layer.data.foreach_set(field, np.ascontiguousarray(values, dtype=dtype).ravel())


def write(obj, result: BuildResult) -> None:
    mesh = obj.data
    fill(mesh, result.vertices, result.quads, result.tris)
    for index, name in enumerate(CHANNELS):
        attribute(mesh, ATTRIBUTE_PREFIX + name, result.channels[:, index])
    base = getattr(result, "base_colours", None)
    if base is not None:                     # a fragment's own colour (scene-linear, as Blender stores colours)
        linear = np.power(np.clip(base, 0.0, 1.0), 2.2)
        attribute(mesh, ATTRIBUTE_PREFIX + "base", np.hstack([linear, np.ones((len(base), 1))]), "FLOAT_COLOR")
    elif ATTRIBUTE_PREFIX + "base" in mesh.attributes:
        mesh.attributes.remove(mesh.attributes[ATTRIBUTE_PREFIX + "base"])
    apply_shading(obj)
    if result.normals is not None and len(result.vertices):
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
