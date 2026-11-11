# SPDX-License-Identifier: MIT
"""The material every fractal starts with: a mesh attribute → a colour ramp → Principled BSDF.

The ramp is the palette: the sidebar draws this node's widget, so editing it there or in the Shader Editor is
the same thing. The ramp starts with the Iteron brand sweep (core/palette.py, from branding/source/palette.py).
"""

from __future__ import annotations

import bpy

from ..core.palette import SWEEP, linear
from .mesh_write import ATTRIBUTE_PREFIX

RAMP_NODE, ATTRIBUTE_NODE = "Iteron Ramp", "Iteron Attribute"
ATTRIBUTE_FOR_MODE = {"TRAP": "trap", "ITERATIONS": "iterations", "RADIUS": "radius", "SOLID": "", "BASE": "base"}


def attribute_name(mode: str) -> str:
    return ATTRIBUTE_PREFIX + ATTRIBUTE_FOR_MODE[mode] if ATTRIBUTE_FOR_MODE[mode] else ""


def find(obj):
    """The object's Iteron material (the first slot whose tree has the ramp node), or None."""
    for slot in obj.material_slots:
        material = slot.material
        if material and material.node_tree and RAMP_NODE in material.node_tree.nodes:
            return material
    return None


def ramp_node(obj):
    material = find(obj)
    return material.node_tree.nodes[RAMP_NODE] if material else None


def ensure(obj):
    """The object's Iteron material, created and assigned if it has none."""
    material = find(obj)
    if material is None:
        material = create(obj.name)
        obj.data.materials.append(material)
    return material


def create(name: str):
    material = bpy.data.materials.new(f"Iteron {name}")
    if material.node_tree is None:            # before Blender 5 a new material has no node tree until asked
        material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.4
    attribute = nodes.new("ShaderNodeAttribute")
    attribute.name = attribute.label = ATTRIBUTE_NODE
    attribute.attribute_type = "GEOMETRY"
    attribute.attribute_name = attribute_name("TRAP")
    attribute.location = (bsdf.location.x - 520, bsdf.location.y)
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.name = ramp.label = RAMP_NODE
    ramp.location = (bsdf.location.x - 300, bsdf.location.y)
    elements = ramp.color_ramp.elements
    while len(elements) < len(SWEEP):
        elements.new(0.5)
    for element, (position, colour) in zip(elements, SWEEP):
        element.position, element.color = position, linear(colour)
    links.new(attribute.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return material


FLAME_TAG = "iteron_flame"          # marks the material a flame object made


def ensure_flame(obj):
    """A flame's material: its palette colours (the `Col` attribute) into a Principled BSDF (the base the
    per-transform materials are copied from)."""
    f = obj.iteron.flame
    if f.base_material is not None:
        return f.base_material
    for slot in obj.material_slots:
        if slot.material is not None and slot.material.get(FLAME_TAG):
            f.base_material = slot.material
            return slot.material
    flame = bpy.data.materials.new(f"Iteron {obj.name}")
    flame[FLAME_TAG] = True
    if flame.node_tree is None:
        flame.use_nodes = True
    nodes, links = flame.node_tree.nodes, flame.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.45
    colour = nodes.new("ShaderNodeAttribute")
    colour.attribute_type = "GEOMETRY"
    colour.attribute_name = "Col"
    colour.location = (bsdf.location.x - 300, bsdf.location.y)
    links.new(colour.outputs["Color"], bsdf.inputs["Base Color"])
    obj.data.materials.append(flame)
    f.base_material = flame
    return flame


def set_surface(material, roughness: float, specular: float) -> None:
    bsdf = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Specular IOR Level"].default_value = specular


def set_mode(obj, mode: str) -> None:
    """Point the material's attribute node at the mode's channel; the fragment's own colour (`BASE`) bypasses the
    ramp."""
    material = find(obj)
    if material is None:
        return
    nodes, links = material.node_tree.nodes, material.node_tree.links
    attribute = nodes[ATTRIBUTE_NODE]
    attribute.attribute_name = attribute_name(mode)
    bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        own = mode == "BASE" and ATTRIBUTE_PREFIX + "base" in obj.data.attributes
        source = attribute.outputs["Color"] if own else nodes[RAMP_NODE].outputs["Color"]
        links.new(source, bsdf.inputs["Base Color"])
