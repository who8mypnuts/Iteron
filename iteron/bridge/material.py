# SPDX-License-Identifier: MIT
"""The material every fractal starts with: a mesh attribute → a colour ramp → Principled BSDF.

The ramp is the palette: the sidebar draws this node's widget, so editing it there or in the Shader Editor is
the same thing. The ramp starts with the Iteron brand sweep (branding/source/palette.py).
"""

from __future__ import annotations

import bpy

from .mesh_write import ATTRIBUTE_PREFIX

RAMP_NODE, ATTRIBUTE_NODE = "Iteron Ramp", "Iteron Attribute"
ATTRIBUTE_FOR_MODE = {"TRAP": "trap", "ITERATIONS": "iterations", "RADIUS": "radius", "SOLID": ""}
SWEEP = ((0.00, "#1FF0FF"), (0.30, "#2F9BFF"), (0.55, "#6A4DFF"), (0.80, "#B23CFF"), (1.00, "#FF3F93"))


def _linear(hex_colour: str) -> tuple[float, float, float, float]:
    """sRGB hex → scene-linear RGBA (ramp colours are linear)."""
    def channel(c):
        c = int(c, 16) / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    h = hex_colour.lstrip("#")
    return (channel(h[0:2]), channel(h[2:4]), channel(h[4:6]), 1.0)


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
        element.position, element.color = position, _linear(colour)
    links.new(attribute.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return material


def set_mode(obj, mode: str) -> None:
    material = find(obj)
    if material is not None:
        material.node_tree.nodes[ATTRIBUTE_NODE].attribute_name = attribute_name(mode)
