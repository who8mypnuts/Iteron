# SPDX-License-Identifier: MIT
"""Drawing a formula's parameters from its schema — the only place parameters are laid out, for built-in formulas
(a PropertyGroup per formula), hybrids (their parts' groups) and fragments (a collection of typed items) alike:
`Source` hides the difference.

Ungrouped parameters come first; each group folds into its own sub-section, and a group that starts with a
Bool (Julia) puts that checkbox in its header and greys out the rest while it is off.
"""

from __future__ import annotations

from ..core.formula import slug

REGION_GROUPS = ("Cut",)      # drawn in the Region section instead of Shape


class Source:
    """Where a formula's values live: `lookup(name)` → `(data, attribute)` — a PropertyGroup and the property's
    name (built-in formulas; a hybrid's part parameters are its parts' own), or `(item, None)` for a fragment's
    typed item (None when the item doesn't exist yet)."""

    def __init__(self, lookup):
        self.lookup = lookup

    def prop(self, layout, param, text: str | None = None) -> None:
        label = param.title if text is None else text
        data, attr = self.lookup(param.name)
        if attr is not None:
            layout.prop(data, attr, text=label)
        elif data is None:
            layout.label(text=f"{label}: rebuild to show", icon="INFO")
        else:
            _draw_item(layout, data, param, label)

    def get(self, name: str):
        data, attr = self.lookup(name)
        if attr is not None:
            return getattr(data, attr)
        from ..bridge.fragment_props import get
        return get(data) if data is not None else True


def _draw_item(layout, item, param, label: str) -> None:
    prop, size = _item_prop(item, param)
    if prop == "colour":
        column = layout.column(align=True)
        column.prop(item, "colour", text=label)
        if param.lanes == 4:                      # FragM's colour-and-value: (r, g, b, value)
            column.prop(item, "value", index=3, text="Value")
    elif size == 1:
        layout.prop(item, prop, index=0 if prop == "value" else -1, text=label)
    else:
        column = layout.column(align=True)
        for index in range(size):
            column.prop(item, prop, index=index, text=label if index == 0 else "")


def _item_prop(item, param) -> tuple[str, int]:
    if param.kind in ("int", "bool", "enum"):
        return {"int": "integer", "bool": "flag", "enum": "choice"}[param.kind], 1
    if getattr(param, "subtype", "") == "COLOR" and param.lanes > 1:
        return "colour", 1
    return "value", param.lanes


def draw_params(layout, source: Source, entry, skip: tuple[str, ...] = REGION_GROUPS) -> None:
    groups: dict[str, list] = {}
    for param in entry.params:
        if param.group not in skip:
            groups.setdefault(param.group, []).append(param)
    column = _split(layout.column())
    for param in groups.pop("", []):
        source.prop(column, param)
    for name, params in groups.items():
        draw_group(layout, source, entry, name, params)


def draw_group(layout, source: Source, entry, name: str, params=None) -> None:
    """One folding group; a group whose first parameter is a Bool has it as the header's checkbox."""
    params = list(params if params is not None else [p for p in entry.params if p.group == name])
    if not params:
        return
    header, body = layout.panel(f"iteron_{entry.id}_{slug(name)}", default_closed=True)
    toggle = params.pop(0) if params[0].kind == "bool" else None
    if toggle is not None:
        source.prop(header, toggle, text=name)
    else:
        header.label(text=name)
    if body is None:
        return
    column = _split(body.column())
    column.active = bool(source.get(toggle.name)) if toggle is not None else True
    for param in params:
        source.prop(column, param)


def _split(layout):
    layout.use_property_split = True
    layout.use_property_decorate = True       # the keyframe dots
    return layout
