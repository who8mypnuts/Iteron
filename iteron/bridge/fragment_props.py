# SPDX-License-Identifier: MIT
"""What a fragment object stores: its source (a Text datablock), where it came from, and its parameters.

A fragment's uniforms aren't known when the add-on registers, so its values live in a generic typed collection,
`obj.iteron.fragment.params["Power"]`, one item per parameter, synced to the parameter specs whenever the source
changes (existing values are kept). Every item stores its value in the one property its kind uses — `value` for
floats and vectors, `colour` for colours, `integer`, `flag`, `choice` — so it stays keyframeable
(`params["Power"].value[0]`).
"""

from __future__ import annotations

import json

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatVectorProperty, IntProperty,
                       PointerProperty, StringProperty)
from bpy.types import PropertyGroup

_CHOICES: dict[str, list] = {}          # Blender needs dynamic enum items kept alive


def _changed(self, _context):
    from .state import params_changed
    params_changed(self.id_data)


def _choice_items(self, _context):
    key = self.choices
    if key not in _CHOICES:
        _CHOICES[key] = [(i, label, "") for i, label in json.loads(key or "[]")] or [("0", "(none)", "")]
    return _CHOICES[key]


class IteronParamItem(PropertyGroup):
    kind: StringProperty(options={"HIDDEN"})            # the spec's kind: float int bool enum vec2 vec3 vec4
    subtype: StringProperty(options={"HIDDEN"})
    value: FloatVectorProperty(size=4, precision=3, step=1, update=_changed)
    colour: FloatVectorProperty(size=3, subtype="COLOR", min=0.0, soft_max=1.0, update=_changed)
    integer: IntProperty(update=_changed)
    flag: BoolProperty(update=_changed)
    choices: StringProperty(options={"HIDDEN"})          # JSON [(identifier, label), …] for `choice`
    choice: EnumProperty(items=_choice_items, update=_changed)


class IteronFragmentSettings(PropertyGroup):
    name: StringProperty(name="Name", description="The fragment's name (its file's)")
    text: PointerProperty(type=bpy.types.Text, name="Source",
                          description="The fragment's source, kept in the .blend (edit it in the Text Editor, then "
                          "rebuild)")
    path: StringProperty(name="File", subtype="FILE_PATH", description="The file the fragment was opened from")
    params: CollectionProperty(type=IteronParamItem)
    error: StringProperty(options={"HIDDEN"}, description="Why the fragment can't be built")


def is_colour(item) -> bool:
    return item.subtype == "COLOR"


def get(item):
    """An item's value as plain Python, by its kind."""
    kind = item.kind
    if kind == "float":
        return item.value[0]
    if kind == "int":
        return item.integer
    if kind == "bool":
        return item.flag
    if kind == "enum":
        return item.choice
    lanes = {"vec2": 2, "vec3": 3, "vec4": 4}[kind]
    if is_colour(item):
        return tuple(item.colour) + ((item.value[3],) if lanes == 4 else ())
    return tuple(item.value[:lanes])


def put(item, value) -> None:
    kind = item.kind
    if kind == "float":
        item.value[0] = value
    elif kind == "int":
        item.integer = value
    elif kind == "bool":
        item.flag = value
    elif kind == "enum":
        item.choice = value
    elif is_colour(item):
        item.colour = value[:3]
        if len(value) == 4:
            item.value[3] = value[3]
    else:
        item.value[:len(value)] = value


def sync(settings, params) -> None:
    """Make the items match `params` (specs): add new ones at their defaults, drop gone ones, keep the values of
    the rest (when the kind is unchanged)."""
    items = settings.params
    wanted = {p.name: p for p in params}
    for index in reversed(range(len(items))):
        item = items[index]
        spec = wanted.get(item.name)
        if spec is None or spec.kind != item.kind:
            items.remove(index)
    for spec in params:
        item = items.get(spec.name)
        fresh = item is None
        if fresh:
            item = items.add()
            item.name, item.kind = spec.name, spec.kind
        item.subtype = getattr(spec, "subtype", "")
        if spec.kind == "enum":
            item.choices = json.dumps([[i, label] for i, label, _d in spec.items])
        if fresh:
            put(item, spec.coerce(spec.default))


def read(settings, params) -> dict:
    """`{name: value}` for `params` (a missing item reads as the default)."""
    items = settings.params
    return {p.name: (p.coerce(get(items[p.name])) if p.name in items else p.coerce(p.default)) for p in params}


def write(settings, params, values: dict) -> None:
    items = settings.params
    for p in params:
        if p.name in values and p.name in items:
            put(items[p.name], p.coerce(values[p.name]))


classes = (IteronParamItem, IteronFragmentSettings)
