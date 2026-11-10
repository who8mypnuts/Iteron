# SPDX-License-Identifier: MIT
"""The `.frag` preprocessor: includes, FragM's host directives, `#group`s and annotated uniforms.

Two passes, as in FragM (ported from Fractalchemy's `fragments/preprocessor.py`, Stan Ragets, MIT):

1. `expand` pulls in `#include "file"` lines (column 0), textually. Iteron's own shims stand in for FragM's ray
   tracers always, and for its library includes when no file of that name is found beside the fragment or in the
   include folders; each shim is included once. `keep` leaves chosen includes as they are — how a fragment is
   stored in a `.blend` with the user's own includes inlined but the shims still by name.
2. `parse` walks the merged lines: `#vertex … #endvertex` blocks and the host directives (`#camera`, `#group`,
   `#info`, `#buffer`, `#donotrun` …) become comments, `#replace "a" "b"` applies to later lines, and annotated
   uniforms become parameters (their line a bare `uniform` declaration).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import annotations
from ..core.params import Param

SHIMS = Path(__file__).resolve().parent / "shims"
RE_INCLUDE = re.compile(r'^#include(?:.*)\s"([^"]+)"\s*$')
RE_REPLACE = re.compile(r'^#replace\s+"([^"]+)"\s+"([^"]+)"\s*$')
RE_HOST = re.compile(r"^(?:raytracer|pathtracer|[\w-]*-raytracer[\w.-]*|[\w-]*raytracer[\w.-]*|de-kn\w*|3d|3dkn[\w.-]*"
                     r"|brute3d|sky-pathtracer|ibl-pathtracer)\.frag$", re.IGNORECASE)
RE_2D = re.compile(r"^(?:2d[\w.-]*|progressive2d[\w.-]*)\.frag$", re.IGNORECASE)
HOST_SHIM = "DE-Raytracer.frag"
DIRECTIVES = ("#camera", "#group", "#info", "#buffer", "#donotrun", "#texparameter", "#vertex", "#endvertex",
              "#buffershader", "#version", "#extension")
MAX_DEPTH = 32


class FragmentError(ValueError):
    """A fragment Iteron cannot use (a missing include, no distance estimator, textures …)."""
    user_facing = True          # reported on the object as it is, without a traceback


@dataclass
class Parsed:
    code: str
    params: list[Param] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)      # unsupported features, by name


def shim(name: str) -> Path | None:
    """Iteron's stand-in for an include, if it has one (every FragM ray tracer maps to the one host shim)."""
    if RE_HOST.match(Path(name).name):
        return SHIMS / HOST_SHIM
    path = SHIMS / Path(name).name
    return path if path.is_file() else None


def resolver(folders: list[Path], prefer_shims: bool = False) -> Callable[[str, Path | None], Path]:
    """`resolve(name, including_file)`: a ray tracer → the host shim; otherwise beside the including file, then the
    include folders, then a shim (`prefer_shims`: a shim first — how a fragment stored in a `.blend` is read, the
    same on every machine). `FragmentError` names an include that is found nowhere."""
    def resolve(name: str, origin: Path | None) -> Path:
        if RE_2D.match(Path(name).name):
            raise FragmentError(f"a 2D fragment (it includes {name}): only 3D distance estimators can be meshed")
        own = shim(name)
        if own is not None and (prefer_shims or RE_HOST.match(Path(name).name)):
            return own
        bases = ([origin.parent] if origin is not None else []) + [Path(f) for f in folders if str(f).strip()]
        for base in bases:
            candidate = base / name
            if candidate.is_file() and not is_shim(candidate):
                return candidate
        if own is None:
            raise FragmentError(f"missing include \"{name}\" (add its folder in Iteron's preferences)")
        return own
    return resolve


def is_shim(path: Path) -> bool:
    return SHIMS in Path(path).resolve().parents


def expand(text: str, path: Path | None, resolve, keep: Callable[[Path], bool] = lambda _p: False,
           _depth: int = 0, _seen: set | None = None) -> str:
    """`text` with its includes pulled in (see the module docstring)."""
    if _depth > MAX_DEPTH:
        raise FragmentError("includes nested too deeply (an include loop?)")
    seen = set() if _seen is None else _seen
    out = []
    for line in text.splitlines():
        match = RE_INCLUDE.match(line)
        if not match:
            out.append(line)
            continue
        target = resolve(match.group(1), path)
        if keep(target):
            out.append(line)
        elif is_shim(target) and target.name in seen:
            out.append(f"// (included already: {match.group(1)})")
        else:
            if is_shim(target):
                seen.add(target.name)
            body = target.read_text(encoding="utf-8", errors="replace")
            out.append(f"// (included: {match.group(1)})")      # no "#include" text left for a host to trip over
            out.append(expand(body, target, resolve, keep, _depth + 1, seen))
    return "\n".join(out)


def parse(text: str) -> Parsed:
    """The merged source (after `expand`) turned into code and parameters."""
    parsed = Parsed("")
    lines, replacements, group, comment, in_vertex = [], {}, "", "", False
    for line in text.splitlines():
        for old, new in replacements.items():
            line = line.replace(old, new)
        stripped = line.strip()
        lowered = stripped.lower()
        if in_vertex or lowered.startswith("#vertex"):
            in_vertex = not lowered.startswith("#endvertex")
            lines.append("// " + stripped)
            continue
        if match := RE_REPLACE.match(stripped):
            replacements[match.group(1)] = match.group(2)
            lines.append("// " + stripped)
            continue
        if lowered.startswith(DIRECTIVES):
            _directive(parsed, stripped, lowered)
            group = _group(stripped) if lowered.startswith("#group") else group
            lines.append("// " + stripped)
            continue
        param = annotations.parse(line, group, comment) if "uniform" in line else None
        if param is not None:
            parsed.params.append(param)
            line = f"uniform {_glsl_type(line)} {param.name};"
        comment = stripped[2:].strip() if stripped.startswith("//") else ""
        lines.append(line)
    parsed.code = "\n".join(lines)
    return parsed


def _directive(parsed: Parsed, stripped: str, lowered: str) -> None:
    if lowered.startswith("#info"):
        parsed.info.append(stripped[5:].strip())
    elif lowered.startswith("#buffershader"):
        parsed.problems.append("a buffer shader (#buffershader)")


def _group(stripped: str) -> str:
    name = stripped[len("#group"):].strip()
    return "" if name.lower() == "default" else name


def _glsl_type(line: str) -> str:
    return line.split("uniform", 1)[1].split()[0]
