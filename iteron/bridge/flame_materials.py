# SPDX-License-Identifier: MIT
"""A material per transform for flames: each transform's surface (from a `.fa3d` scene's materials, or the flame's
own look to edit), assigned by the transform that made each point — the `iteron_xform` attribute on a point cloud,
the densest transform around each face on a solid.

Point clouds can't carry a material index, so their Geometry Nodes group is made per object: the points are split
by transform, each part gets its material and becomes an instance of its own, and the parts are joined again."""

from __future__ import annotations

import json

import bpy
import numpy as np

from . import material
from ..core.palette import linear

TRANSFORM_TAG = "iteron_transform"      # the transform index a material is for


def surface(settings: dict) -> tuple[float, float, tuple | None]:
    """`(roughness, specular, fixed colour or None)` for a Principled BSDF from Fractalchemy's Blinn–Phong
    material (as its own Blender export maps it)."""
    roughness = min(1.0, max(0.05, 1.0 - float(settings.get("shininess", 24.0)) / 200.0))
    fixed = None
    if settings.get("color_mode") == "fixed":
        fixed = linear("#%02x%02x%02x" % tuple(int(c) for c in settings.get("color", (200, 200, 200))))
    return roughness, min(1.0, float(settings.get("specular", 0.35))), fixed


def transform_count(obj) -> int:
    return len([x for x in obj.iteron.flame.flame_dict().get("xforms", []) if float(x.get("weight", 0.5)) > 0])


def materials(obj) -> list:
    """The materials the flame's geometry uses, in slot order (one, or one per transform)."""
    flame = material.ensure_flame(obj)
    f = obj.iteron.flame
    if not f.per_transform:
        return [flame]
    found = {m.get(TRANSFORM_TAG): m for m in obj.data.materials if m is not None and m.get(TRANSFORM_TAG) is not None}
    looks = json.loads(f.materials or "[]")
    out = []
    for index in range(transform_count(obj)):
        made = found.get(index)
        if made is None:
            made = flame.copy()
            made.name = f"{obj.name} · Transform {index + 1}"
            made[TRANSFORM_TAG] = index
            if made.get(material.FLAME_TAG):
                del made[material.FLAME_TAG]
            if looks:
                _look(made, looks[min(index, len(looks) - 1)])
        out.append(made)
    return out


def _look(made, settings: dict) -> None:
    roughness, specular, fixed = surface(settings)
    material.set_surface(made, roughness, specular)
    if fixed is not None:
        bsdf = next(n for n in made.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        for link in list(bsdf.inputs["Base Color"].links):
            made.node_tree.links.remove(link)
        bsdf.inputs["Base Color"].default_value = fixed


def assign(obj) -> list:
    """Put the materials on the mesh and, for a solid, each face's index (the transform of its first corner, from
    the `iteron_xform` attribute); returns the materials."""
    mesh, wanted = obj.data, materials(obj)
    if list(mesh.materials) != wanted:
        mesh.materials.clear()
        for made in wanted:
            mesh.materials.append(made)
    faces, which = len(mesh.polygons), mesh.attributes.get("iteron_xform")
    if faces:
        index = np.zeros(faces, dtype=np.int32)
        if len(wanted) > 1 and which is not None:
            per_vertex = np.zeros(len(mesh.vertices), dtype=np.int32)
            which.data.foreach_get("value", per_vertex)
            starts, corners = np.zeros(faces, dtype=np.int32), np.zeros(len(mesh.loops), dtype=np.int32)
            mesh.polygons.foreach_get("loop_start", starts)
            mesh.loops.foreach_get("vertex_index", corners)
            index = np.clip(per_vertex[corners[starts]], 0, len(wanted) - 1).astype(np.int32)
        mesh.polygons.foreach_set("material_index", index)
    return wanted


def points_group(obj, wanted: list):
    """The object's own points group: Mesh to Points, split by `iteron_xform`, a material per part, joined."""
    name = f"Iteron Points · {obj.name}"
    group = bpy.data.node_groups.get(name) or bpy.data.node_groups.new(name, "GeometryNodeTree")
    group.nodes.clear()
    interface = group.interface
    if not interface.items_tree:
        interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        radius = interface.new_socket("Radius", in_out="INPUT", socket_type="NodeSocketFloat")
        radius.default_value, radius.min_value = 0.005, 0.0
        interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes, links = group.nodes, group.links
    inputs, outputs = nodes.new("NodeGroupInput"), nodes.new("NodeGroupOutput")
    to_points, join = nodes.new("GeometryNodeMeshToPoints"), nodes.new("GeometryNodeJoinGeometry")
    which = nodes.new("GeometryNodeInputNamedAttribute")
    which.data_type = "INT"
    which.inputs["Name"].default_value = "iteron_xform"
    links.new(inputs.outputs["Geometry"], to_points.inputs["Mesh"])
    links.new(inputs.outputs["Radius"], to_points.inputs["Radius"])
    for index, made in enumerate(wanted):
        equal = nodes.new("FunctionNodeCompare")
        equal.data_type, equal.operation = "INT", "EQUAL"
        links.new(which.outputs["Attribute"], equal.inputs[2])
        equal.inputs[3].default_value = index
        part = nodes.new("GeometryNodeSeparateGeometry")
        part.domain = "POINT"
        links.new(to_points.outputs["Points"], part.inputs["Geometry"])
        links.new(equal.outputs["Result"], part.inputs["Selection"])
        paint = nodes.new("GeometryNodeSetMaterial")
        paint.inputs["Material"].default_value = made
        links.new(part.outputs["Selection"], paint.inputs["Geometry"])
        wrap = nodes.new("GeometryNodeGeometryToInstance")      # a point cloud holds one material: keep the parts
        links.new(paint.outputs["Geometry"], wrap.inputs["Geometry"])   # apart, as instances
        links.new(wrap.outputs["Instances"], join.inputs["Geometry"])
    links.new(join.outputs["Geometry"], outputs.inputs["Geometry"])
    return group
