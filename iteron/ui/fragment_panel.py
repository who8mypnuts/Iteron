# SPDX-License-Identifier: MIT
"""The sidebar for a fragment object: its name and description, the shared formula sections (parameters from the
fragment's annotations), and where its source lives."""

from __future__ import annotations

import textwrap

from ..bridge.kinds import FragmentKind
from .draw import Source
from .panel import draw_body

INFO_WIDTH, INFO_LINES = 48, 4


def draw_fragment(layout, obj) -> None:
    f = obj.iteron.fragment
    layout.label(text=f"{obj.name}  ·  {f.name}", icon="FILE_SCRIPT")
    try:
        entry = FragmentKind.entry(obj)
    except ValueError as error:
        for line in textwrap.wrap(str(error), INFO_WIDTH)[:INFO_LINES]:
            layout.label(text=line, icon="ERROR")
        _draw_source(layout, obj)
        return
    column = layout.column(align=True)
    for line in textwrap.wrap(entry.info, INFO_WIDTH)[:INFO_LINES]:
        column.label(text=line)
    draw_body(layout, obj, entry, Source(lambda name: (f.params.get(name), None)))
    _draw_source(layout, obj)


def _draw_source(layout, obj) -> None:
    f = obj.iteron.fragment
    header, body = layout.panel("iteron_fragment_source", default_closed=True)
    header.label(text="Source")
    if body is None:
        return
    column = body.column()
    column.prop(f, "text", text="Text")
    column.prop(f, "path", text="File")
    column.operator("iteron.reload_fragment", icon="FILE_REFRESH")
    column.label(text="Edit the text in the Text Editor, then rebuild", icon="INFO")
