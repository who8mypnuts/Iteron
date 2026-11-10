# SPDX-License-Identifier: MIT
"""The flames that come with Iteron (`flames/library/*.json`, Fractalchemy's flame dict format): the Shift+A menu."""

from __future__ import annotations

import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent / "library"


def bundled() -> dict[str, dict]:
    """Flame id (the file's stem) → flame dict, in name order."""
    flames = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in FOLDER.glob("*.json")}
    return dict(sorted(flames.items(), key=lambda item: item[1].get("name", item[0])))
