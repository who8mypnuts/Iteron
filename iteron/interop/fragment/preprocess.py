# SPDX-License-Identifier: MIT
"""Resolving a fragment's `#include`s (PLAN.md \u00a77).

FragM's own include files (`MathUtils.frag`, `DE-Raytracer.frag`, …) are GPL / LGPL and can't ship with an MIT
add-on, so Iteron ships small MIT **shims** of its own under `fragment/shims/` \u2014 just the globals and helper
functions a distance estimator typically needs (`orbitTrap`, `rotationMatrix3`, …), not a raytracer. Anything a
shim doesn't cover is looked for beside the fragment, then in the *include folders* from Preferences (a user's own
Fractalchemy or FragM installation); a name found nowhere is reported, not silently dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

SHIMS_DIR = Path(__file__).resolve().parent / "shims"
_INCLUDE = re.compile(r'^\s*#include\s+"([^"]+)"\s*$', re.MULTILINE)


class MissingIncludeError(FileNotFoundError):
    def __init__(self, name: str, searched: list[Path]):
        self.name, self.searched = name, searched
        super().__init__(f'#include "{name}" was not found (looked in {", ".join(str(p) for p in searched)})')


@dataclass
class Preprocessed:
    source: str                            # every #include expanded, in order
    resolved: list[Path] = field(default_factory=list)       # the files used, for a "what this pulled in" report


def _search_paths(name: str, beside: Path | None, include_dirs: list[Path]) -> list[Path]:
    paths = []
    if beside is not None:
        paths.append(beside.parent / name)
    paths.append(SHIMS_DIR / name)
    paths.extend(folder / name for folder in include_dirs)
    return paths


def resolve(text: str, beside: Path | None = None, include_dirs: list[Path] | None = None,
            _seen: frozenset[str] = frozenset()) -> Preprocessed:
    """`text` with every `#include "name"` replaced by that file's own (recursively resolved) text."""
    include_dirs = include_dirs or []
    resolved_files: list[Path] = []

    def expand(match: re.Match) -> str:
        name = match.group(1)
        if name in _seen:
            return f"// (already included: {name})\n"
        for candidate in _search_paths(name, beside, include_dirs):
            if candidate.is_file():
                nested = resolve(candidate.read_text(encoding="utf-8"), candidate, include_dirs, _seen | {name})
                resolved_files.append(candidate)
                resolved_files.extend(nested.resolved)
                return nested.source
        raise MissingIncludeError(name, _search_paths(name, beside, include_dirs))

    return Preprocessed(_INCLUDE.sub(expand, text), resolved_files)
