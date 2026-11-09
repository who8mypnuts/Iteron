# SPDX-License-Identifier: MIT
"""The `.fafrag` wrapper: a `.frag` (so FragM still opens it unchanged) plus, at most once, a JSON metadata block
Fractalchemy keeps inside a comment \u2014 Fractalchemy's own format (`fragments/document_format.py`), unchanged.

    /*[fractalchemy]
    {"version": 1, "tabs": {"origin": "Examples/Knighty Collection/PseudoKleinian.frag"}}
    [/fractalchemy]*/
"""

from __future__ import annotations

import json
import re

BLOCK = re.compile(r"\n?/\*\[fractalchemy\]\s*\n(.*?)\n\[/fractalchemy\]\*/\s*", re.DOTALL)


class FragmentMetadataError(ValueError):
    """The metadata block is there but is not valid JSON."""


def split(text: str) -> tuple[str, dict | None]:
    """`(glsl_source, metadata)` \u2014 `metadata` is `None` for a plain `.frag` with no Fractalchemy block."""
    match = BLOCK.search(text)
    if not match:
        return text, None
    try:
        metadata = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise FragmentMetadataError(f"the [fractalchemy] metadata block is not valid JSON: {exc}") from exc
    return text[:match.start()] + text[match.end():], metadata
