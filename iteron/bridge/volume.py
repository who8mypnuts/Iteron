# SPDX-License-Identifier: MIT
"""Volume output: the fractal's mesh filled as a volume by a Geometry Nodes modifier (Mesh to Volume → a Principled
Volume material), for fog-like renders in Cycles and EEVEE. Blender's Python has no OpenVDB writer, so the volume is
made where Blender makes volumes; the mesh stays the source and every rebuild updates it."""

from __future__ import annotations

import bpy

GROUP = "Iteron Volume"
MODIFIER = "Iteron Volume"
MATERIAL_TAG = "iteron_volume"


def apply(obj) -> None:
    """Add, update or remove the volume modifier to match `obj.iteron.output`."""
    modifier = obj.modifiers.get(MODIFIER)
    if obj.iteron.output != "VOLUME":
        if modifier is not None:
            obj.modifiers.remove(modifier)
        return
    if modifier is None:
        modifier = obj.modifiers.new(MODIFIER, "NODES")
        modifier.node_group = node_group()
    set_input(modifier, "Density", obj.iteron.volume_density)
    set_input(modifier, "Voxel Size", obj.iteron.volume_voxel)
    set_input(modifier, "Material", material(obj))
    obj.update_tag()


def set_input(modifier, name: str, value) -> None:
    for item in modifier.node_group.interface.items_tree:
        if getattr(item, "in_out", None) == "INPUT" and item.name == name:
            modifier[item.identifier] = value
            return


def node_group():
    group = bpy.data.node_groups.get(GROUP)
    if group is not None:
        return group
    group = bpy.data.node_groups.new(GROUP, "GeometryNodeTree")
    interface = group.interface
    interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    for name, default in (("Density", 1.0), ("Voxel Size", 0.02)):
        socket = interface.new_socket(name, in_out="INPUT", socket_type="NodeSocketFloat")
        socket.default_value, socket.min_value = default, 0.0
    interface.new_socket("Material", in_out="INPUT", socket_type="NodeSocketMaterial")
    interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes, links = group.nodes, group.links
    inputs, outputs = nodes.new("NodeGroupInput"), nodes.new("NodeGroupOutput")
    to_volume, set_material = nodes.new("GeometryNodeMeshToVolume"), nodes.new("GeometryNodeSetMaterial")
    if "Resolution Mode" in to_volume.inputs:                 # Blender 5: a menu socket
        to_volume.inputs["Resolution Mode"].default_value = "Size"
    else:
        to_volume.resolution_mode = "VOXEL_SIZE"
    inputs.location, to_volume.location, set_material.location, outputs.location = (-420, 0), (-160, 0), (80, 0), (300, 0)
    links.new(inputs.outputs["Geometry"], to_volume.inputs["Mesh"])
    links.new(inputs.outputs["Density"], to_volume.inputs["Density"])
    links.new(inputs.outputs["Voxel Size"], to_volume.inputs["Voxel Size"])
    links.new(to_volume.outputs["Volume"], set_material.inputs["Geometry"])
    links.new(inputs.outputs["Material"], set_material.inputs["Material"])
    links.new(set_material.outputs["Geometry"], outputs.inputs["Geometry"])
    return group


def material(obj):
    """The object's volume material: a Principled Volume tinted with the start of its colour ramp."""
    from .material import ramp_node
    name = f"Iteron Volume {obj.name}"
    found = bpy.data.materials.get(name)
    if found is not None and found.get(MATERIAL_TAG):
        return found
    shader = bpy.data.materials.new(name)
    shader[MATERIAL_TAG] = True
    if shader.node_tree is None:
        shader.use_nodes = True
    nodes, links = shader.node_tree.nodes, shader.node_tree.links
    for node in list(nodes):
        if node.type != "OUTPUT_MATERIAL":
            nodes.remove(node)
    output = next(n for n in nodes if n.type == "OUTPUT_MATERIAL")
    volume = nodes.new("ShaderNodeVolumePrincipled")
    volume.location = (output.location.x - 300, output.location.y)
    ramp = ramp_node(obj)
    if ramp is not None:
        volume.inputs["Color"].default_value = ramp.color_ramp.evaluate(0.5)
    links.new(volume.outputs["Volume"], output.inputs["Volume"])
    return shader
