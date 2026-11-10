# SPDX-License-Identifier: MIT
"""User presets: a formula's parameters saved as small JSON files, listed beside the built-in presets.

    <user presets>/<formula id>/<name>.json   {"format": "iteron-preset", "version": 1, "formula": …, "values": {…}}

Stored in the extension's own user folder (Blender 4.2+), or Blender's config folder when the add-on runs from a
checkout. Values are checked against the formula's parameters when loaded (unknown names are ignored), so a preset
survives a formula gaining parameters.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import bpy

from ..core.formula import concrete

FORMAT = "iteron-preset"
VERSION = 1
USER_PREFIX = "user:"


def folder(formula_id: str, create: bool = False) -> Path:
    base = None
    try:
        base = Path(bpy.utils.extension_path_user(__package__.rsplit(".", 1)[0], path="presets", create=create))
    except (ValueError, AttributeError, RuntimeError):      # not installed as an extension (a checkout, tests)
        base = Path(bpy.utils.user_resource("CONFIG", path="iteron_presets", create=create))
    path = base / formula_id
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def file_name(name: str) -> str:
    return re.sub(r"[^\w\- ]+", "_", name).strip() or "Preset"


def user_presets(formula_id: str) -> list[str]:
    path = folder(formula_id)
    return sorted(p.stem for p in path.glob("*.json")) if path.is_dir() else []


def save(formula_id: str, name: str, values: dict) -> Path:
    path = folder(formula_id, create=True) / f"{file_name(name)}.json"
    payload = {"format": FORMAT, "version": VERSION, "formula": formula_id,
               "values": {k: list(v) if isinstance(v, tuple) else v for k, v in values.items()}}
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return path


def load(entry, name: str) -> dict:
    """A saved preset of `entry` (a formula or a fragment), checked against its parameters."""
    path = folder(entry.id) / f"{file_name(name)}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != FORMAT or data.get("formula") != entry.id:
        raise ValueError(f"{path.name} is not an Iteron preset for {entry.id}")
    entry = concrete(entry, {k: v for k, v in data.get("values", {}).items() if k in (entry.stored or ())})
    params = {p.name: p for p in entry.params}                  # (a hybrid: the parts the preset was saved with)
    return {k: params[k].coerce(v) for k, v in data.get("values", {}).items() if k in params}


def delete(formula_id: str, name: str) -> None:
    path = folder(formula_id) / f"{file_name(name)}.json"
    if path.is_file():
        path.unlink()
