# SPDX-License-Identifier: MIT
"""A flame's geometry in Blender: a point cloud (with a Geometry Nodes modifier that turns the vertices into render
points) or a density mesh, coloured from the flame's palette (`Col`), with the transform of each point
(`iteron_xform`) kept as an attribute — on a solid, the transform densest around each vertex. Materials: one, or one
per transform (flame_materials.py)."""

from __future__ import annotations

import bpy
import numpy as np

from . import flame_materials
from .mesh_write import attribute, fill

POINTS_GROUP = "Iteron Points"
MODIFIER = "Iteron Points"


def write(obj, result) -> None:
    mesh = obj.data
    fill(mesh, result.vertices, result.quads, result.tris)
    colours = np.concatenate([result.colours, np.ones((len(result.colours), 1), dtype=np.float32)], axis=1)
    attribute(mesh, "Col", colours, "FLOAT_COLOR")
    mesh.color_attributes.active_color = mesh.color_attributes["Col"]
    if result.xform is not None:
        attribute(mesh, "iteron_xform", result.xform.astype(np.int32), "INT")
    elif "iteron_xform" in mesh.attributes:
        mesh.attributes.remove(mesh.attributes["iteron_xform"])
    apply_look(obj)
    mesh.update()


def apply_look(obj) -> None:
    """Materials (one, or one per transform) and, for a point cloud, the points modifier; from the mesh as built,
    so toggling per-transform materials needs no rebuild."""
    mesh = obj.data
    wanted = flame_materials.assign(obj)
    points = len(mesh.polygons) == 0
    modifier = obj.modifiers.get(MODIFIER)
    if points:
        modifier = modifier or obj.modifiers.new(MODIFIER, "NODES")
        if len(wanted) > 1:
            modifier.node_group = flame_materials.points_group(obj, wanted)
        else:
            modifier.node_group = points_group()
            _set_input(modifier, "Material", wanted[0])
        update_point_radius(obj)
        modifier.show_viewport = modifier.show_render = True
    else:
        if modifier is not None:
            obj.modifiers.remove(modifier)
        mesh.shade_smooth()


def update_point_radius(obj) -> None:
    modifier = obj.modifiers.get(MODIFIER)
    if modifier is not None:
        _set_input(modifier, "Radius", obj.iteron.flame.point_radius)
        obj.update_tag()


def _set_input(modifier, name: str, value) -> None:
    for item in modifier.node_group.interface.items_tree:
        if getattr(item, "in_out", None) == "INPUT" and item.name == name:
            modifier[item.identifier] = value
            return


def points_group():
    """The shared node group: mesh vertices → points of a given radius, with a material."""
    group = bpy.data.node_groups.get(POINTS_GROUP)
    if group is not None:
        return group
    group = bpy.data.node_groups.new(POINTS_GROUP, "GeometryNodeTree")
    interface = group.interface
    interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    radius = interface.new_socket("Radius", in_out="INPUT", socket_type="NodeSocketFloat")
    radius.default_value, radius.min_value = 0.005, 0.0
    interface.new_socket("Material", in_out="INPUT", socket_type="NodeSocketMaterial")
    interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes, links = group.nodes, group.links
    inputs, outputs = nodes.new("NodeGroupInput"), nodes.new("NodeGroupOutput")
    to_points, set_material = nodes.new("GeometryNodeMeshToPoints"), nodes.new("GeometryNodeSetMaterial")
    inputs.location, to_points.location, set_material.location, outputs.location = (-400, 0), (-150, 0), (80, 0), (300, 0)
    links.new(inputs.outputs["Geometry"], to_points.inputs["Mesh"])
    links.new(inputs.outputs["Radius"], to_points.inputs["Radius"])
    links.new(to_points.outputs["Points"], set_material.inputs["Geometry"])
    links.new(inputs.outputs["Material"], set_material.inputs["Material"])
    links.new(set_material.outputs["Geometry"], outputs.inputs["Geometry"])
    return group
