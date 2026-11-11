# SPDX-License-Identifier: MIT
"""Holons in Blender: the instances a flame build placed (flames/holon.py) live on a child object — one vertex per
instance, with its rotation, scale and palette colour as attributes — whose Geometry Nodes modifier instances the
chosen shape there (*Instance on Points*). The instances stay instances (light, and they render in Cycles and EEVEE);
their palette colour reaches the shader through an *Instancer* attribute."""

from __future__ import annotations

import bmesh
import bpy
import numpy as np

from ..flames.holon import euler_xyz
from .mesh_write import attribute, fill

MODIFIER = "Iteron Instances"
ASSETS = "Iteron Assets"
ROTATION, SCALE, COLOUR = "iteron_rotation", "iteron_scale", "Col"


def write(obj, result) -> None:
    """Fill (or remove) the flame's instance object from a build result."""
    settings = obj.iteron.flame.instancer
    found = getattr(result, "instances", None)
    if found is None or not settings.enabled:
        remove(obj)
        return
    holder = _holder(obj)
    mesh = holder.data
    fill(mesh, found.positions.astype(np.float32), np.zeros((0, 4), dtype=np.int32))
    attribute(mesh, ROTATION, euler_xyz(found.rotations).astype(np.float32), "FLOAT_VECTOR")
    attribute(mesh, SCALE, found.scales.astype(np.float32))
    colours = np.hstack([result.instance_colours, np.ones((len(found), 1))]) if len(found) else np.zeros((0, 4))
    attribute(mesh, COLOUR, colours, "FLOAT_COLOR")
    mesh.update()
    restyle(obj)


def remove(obj) -> None:
    holder = obj.iteron.flame.instancer.holder
    if holder is not None:
        mesh = holder.data
        bpy.data.objects.remove(holder)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        obj.iteron.flame.instancer.holder = None


def restyle(obj) -> None:
    """The modifier's instanced shape and colouring, from the settings (no rebuild)."""
    settings = obj.iteron.flame.instancer
    holder = settings.holder
    if holder is None:
        return
    source = settings.object if settings.shape == "OBJECT" and settings.object is not None else shape(settings.shape)
    modifier = holder.modifiers.get(MODIFIER) or holder.modifiers.new(MODIFIER, "NODES")
    modifier.node_group = _group(holder, source, palette_material(obj) if settings.palette else None)


def _holder(obj):
    settings = obj.iteron.flame.instancer
    if settings.holder is None or settings.holder.name not in bpy.data.objects:
        mesh = bpy.data.meshes.new(f"{obj.name} Instances")
        holder = bpy.data.objects.new(mesh.name, mesh)
        for collection in obj.users_collection:
            collection.objects.link(holder)
        holder.parent = obj
        settings.holder = holder
    return settings.holder


def _group(holder, source, paint):
    name = f"Iteron Instances · {holder.name}"
    group = bpy.data.node_groups.get(name) or bpy.data.node_groups.new(name, "GeometryNodeTree")
    group.nodes.clear()
    if not group.interface.items_tree:
        group.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes, links = group.nodes, group.links
    inputs, outputs = nodes.new("NodeGroupInput"), nodes.new("NodeGroupOutput")
    info, place = nodes.new("GeometryNodeObjectInfo"), nodes.new("GeometryNodeInstanceOnPoints")
    info.inputs["Object"].default_value = source
    geometry = info.outputs["Geometry"]
    if paint is not None:
        material = nodes.new("GeometryNodeSetMaterial")
        material.inputs["Material"].default_value = paint
        links.new(geometry, material.inputs["Geometry"])
        geometry = material.outputs["Geometry"]
    rotation, scale = nodes.new("GeometryNodeInputNamedAttribute"), nodes.new("GeometryNodeInputNamedAttribute")
    rotation.data_type, scale.data_type = "FLOAT_VECTOR", "FLOAT"
    rotation.inputs["Name"].default_value, scale.inputs["Name"].default_value = ROTATION, SCALE
    links.new(inputs.outputs["Geometry"], place.inputs["Points"])
    links.new(geometry, place.inputs["Instance"])
    links.new(rotation.outputs["Attribute"], place.inputs["Rotation"])
    links.new(scale.outputs["Attribute"], place.inputs["Scale"])
    links.new(place.outputs["Instances"], outputs.inputs["Geometry"])
    return group


def palette_material(obj):
    """Each instance's palette colour (the instance attribute `Col`) into a Principled BSDF."""
    name = f"Iteron Instances · {obj.name}"
    made = bpy.data.materials.get(name)
    if made is not None:
        return made
    made = bpy.data.materials.new(name)
    if made.node_tree is None:
        made.use_nodes = True
    nodes, links = made.node_tree.nodes, made.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    colour = nodes.new("ShaderNodeAttribute")
    colour.attribute_type, colour.attribute_name = "INSTANCER", COLOUR
    colour.location = (bsdf.location.x - 300, bsdf.location.y)
    links.new(colour.outputs["Color"], bsdf.inputs["Base Color"])
    return made


# --- the built-in shapes: unit-sized, centred, in a hidden collection ---------------------------------------------------
def shape(kind: str):
    name = f"Iteron {kind.title()}"
    found = bpy.data.objects.get(name)
    if found is not None:
        return found
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    if kind in ("SPHERE", "ICOSAHEDRON"):
        bmesh.ops.create_icosphere(bm, subdivisions=2 if kind == "SPHERE" else 1, radius=0.5)
    elif kind == "CUBE":
        bmesh.ops.create_cube(bm, size=1.0)
    elif kind == "CYLINDER":
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.5, radius2=0.5, depth=1.0)
    elif kind == "TORUS":
        _torus(bm, 0.35, 0.15, 32, 12)
    else:
        corners = [bm.verts.new(v) for v in np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]]) * 0.2887]
        for a, b, c in ((0, 1, 2), (0, 3, 1), (0, 2, 3), (1, 3, 2)):
            bm.faces.new((corners[a], corners[b], corners[c]))
    bm.to_mesh(mesh)
    bm.free()
    if kind in ("SPHERE", "TORUS", "CYLINDER"):
        mesh.shade_smooth()
    found = bpy.data.objects.new(name, mesh)
    _assets().objects.link(found)
    return found


def _torus(bm, major: float, minor: float, segments: int, rings: int) -> None:
    rows = []
    for i in range(segments):
        a = 2 * np.pi * i / segments
        rows.append([bm.verts.new(((major + minor * np.cos(b)) * np.cos(a), (major + minor * np.cos(b)) * np.sin(a),
                                   minor * np.sin(b))) for b in 2 * np.pi * np.arange(rings) / rings])
    for i in range(segments):
        for j in range(rings):
            a, b = rows[i], rows[(i + 1) % segments]
            bm.faces.new((a[j], b[j], b[(j + 1) % rings], a[(j + 1) % rings]))


def _assets():
    collection = bpy.data.collections.get(ASSETS)
    if collection is None:
        collection = bpy.data.collections.new(ASSETS)
        bpy.context.scene.collection.children.link(collection)
        collection.hide_viewport = collection.hide_render = True
    return collection
