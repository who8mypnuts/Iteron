# SPDX-License-Identifier: MIT
"""Drawing a formula's parameters from its schema — the only place parameters are laid out.

Ungrouped parameters come first; each group folds into its own sub-section, and a group that starts with a
Bool (Julia) puts that checkbox in its header and greys out the rest while it is off.
"""

from __future__ import annotations

from ..core.formula import Formula, slug


REGION_GROUPS = ("Cut",)      # drawn in the Region section instead of Shape


def draw_params(layout, values, entry: Formula, skip: tuple[str, ...] = REGION_GROUPS) -> None:
    groups: dict[str, list] = {}
    for param in entry.params:
        if param.group not in skip:
            groups.setdefault(param.group, []).append(param)
    column = _split(layout.column())
    for param in groups.pop("", []):
        column.prop(values, param.name)
    for name, params in groups.items():
        draw_group(layout, values, entry, name, params)


def draw_group(layout, values, entry: Formula, name: str, params=None) -> None:
    """One folding group; a group whose first parameter is a Bool has it as the header's checkbox."""
    params = list(params if params is not None else [p for p in entry.params if p.group == name])
    if not params:
        return
    header, body = layout.panel(f"iteron_{entry.id}_{slug(name)}", default_closed=True)
    toggle = params.pop(0) if params[0].kind == "bool" else None
    if toggle is not None:
        header.prop(values, toggle.name, text=name)
    else:
        header.label(text=name)
    if body is None:
        return
    column = _split(body.column())
    column.active = getattr(values, toggle.name) if toggle is not None else True
    for param in params:
        column.prop(values, param.name)


def _split(layout):
    layout.use_property_split = True
    layout.use_property_decorate = True       # the keyframe dots
    return layout
