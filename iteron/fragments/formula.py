# SPDX-License-Identifier: MIT
"""A fragment as an Iteron formula: its parameters (from the annotations, plus the shared Cut options), presets and
the GLSL kernel the GPU sampler and the live preview run — the same `KernelSource` a traced formula gives (plus the
2D textures it samples, which the host binds).

The kernel loads the parameters from the uniform block into the fragment's globals, resets the orbit trap, runs
`init()` when the fragment `#define providesInit`, calls `DE(pos)` and applies the cut (traced from the same
`runners._cut` the built-in formulas use). Colour channels: the orbit trap's `w` (√, as FragM colours it), its `x`,
and log(1 + |pos|); a fragment that provides `baseColor(p, n)` can colour the mesh itself (`glsl.COLOR_MAIN`). There
is no CPU path: GLSL can't run in numpy.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..core.formula import GLOBAL, slug, symbolic_values
from ..core.glsl import STRUCT, UNIFORM, KernelSource
from ..core.params import Param, layout, resolve, slot_count
from ..core.runners import _cut
from ..core.trace import S, Tracer, code, tracing
from . import annotations, compat, document
from .preprocess import FragmentError, expand, parse, resolver

RE_PROVIDES_COLOR = re.compile(r"^\s*#\s*define\s+providesColor\b", re.MULTILINE)
RE_BASE_COLOR = re.compile(r"\bvec3\s+baseColor\s*\([^)]*\)\s*\{")
RE_DE = re.compile(r"\bfloat\s+DE\s*\(\s*(?:in\s+)?(?:const\s+)?vec3\s+\w+\s*\)\s*\{")   # defined, not declared
FAMILY = "Fragments"
DEFAULT_BOUNDS = 2.0


@dataclass(frozen=True)
class FragmentFormula:
    id: str
    name: str
    code: str
    params: tuple[Param, ...]
    presets: dict[str, dict[str, Any]] = field(default_factory=dict, hash=False, compare=False)
    camera: document.FragCamera | None = None
    bounds: float = DEFAULT_BOUNDS
    info: str = ""
    version: str = ""                              # a digest of the GLSL: shaders and built meshes follow edits
    textures: tuple[tuple[str, str], ...] = ()     # (sampler uniform, image file named in `file[…]`)
    family = FAMILY
    kind = "fragment"
    surface_offset = 0.6                           # a little over half a voxel: zero-thickness sheets still mesh
    prepare = None
    compose = None
    stored = None
    description = "A Fragmentarium distance estimator"

    @property
    def provides_color(self) -> bool:
        """Whether the fragment `#define providesColor` and defines `vec3 baseColor(vec3, vec3)`."""
        return bool(RE_PROVIDES_COLOR.search(self.code) and RE_BASE_COLOR.search(self.code))

    @property
    def uses_trap(self) -> bool:
        """Whether the fragment writes the orbit trap (the host shim only declares it); without it, colour by radius."""
        return self.code.count("orbitTrap") > 1

    def param(self, name: str) -> Param:
        return next(p for p in self.params if p.name == name)

    def values(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        return resolve(self.params, overrides)

    def static_key(self, _values: dict[str, Any]) -> tuple:
        return ()                                  # every parameter is a uniform: one shader per fragment

    def kernel_source(self, values: dict[str, Any]) -> KernelSource:
        slots = layout(self.params)
        own = [p for p in self.params if p.name not in _CUT_NAMES]
        loads = "\n".join(f"    {p.name} = {_load(p, *slots[p.name])};" for p in own)
        tracer = Tracer()
        with tracing(tracer):
            distance = code(_cut(S("float", "iteron_d"), S("vec3", "pos"), symbolic_values(self, values)))
        kernel = f"""{self.code}

void iteron_load() {{
{loads}
}}

vec4 iteron_kernel(vec3 pos) {{
    iteron_load();
#ifdef ITERON_HOST
    orbitTrap = vec4(10000.0);
#endif
#ifdef providesInit
    init();
#endif
    float iteron_d = DE(pos);
{tracer.source()}
#ifdef ITERON_HOST
    vec4 iteron_trap = orbitTrap;
#else
    vec4 iteron_trap = vec4(0.0);
#endif
    return vec4({distance}, sqrt(abs(iteron_trap.w)), iteron_trap.x, log(1.0 + length(pos)));
}}
"""
        slots_n = slot_count(self.params)
        return KernelSource(f"struct {STRUCT} {{ vec4 v[{slots_n}]; }};", kernel, slots_n,
                            tuple(name for name, _file in self.textures))


_CUT_NAMES = {p.name for p in GLOBAL}


def _load(param: Param, slot: int, lane: int) -> str:
    ref = f"{UNIFORM}.v[{slot}]"
    if param.lanes > 1:
        return f"{ref}.{'xyzw'[:param.lanes]}"
    component = f"{ref}.{'xyzw'[lane]}"
    if param.kind == "bool":
        return f"({component} > 0.5)"
    if param.kind in ("int", "enum"):
        return f"int(round({component}))"
    return component


def build(text: str, path: Path | None = None, folders: tuple[str, ...] = (), name: str = "",
          prefer_shims: bool = False) -> FragmentFormula:
    """The formula for a fragment's source (cached by content). Raises `FragmentError` for what Iteron can't run."""
    return _build(text, str(path) if path else "", tuple(str(f) for f in folders), name, prefer_shims)


@lru_cache(maxsize=16)
def _build(text: str, path: str, folders: tuple[str, ...], name: str, prefer_shims: bool) -> FragmentFormula:
    origin = Path(path) if path else None
    source = document.strip_metadata(text)
    merged = expand(document.remove_presets(source), origin, resolver([Path(f) for f in folders], prefer_shims))
    parsed = parse(merged)
    glsl, problems = compat.convert(parsed.code, parsed.params)
    problems += parsed.problems
    if problems:
        raise FragmentError("not supported here: " + ", ".join(problems))
    if not RE_DE.search(glsl):
        raise FragmentError("no `float DE(vec3)`: only 3D distance-estimated fragments can be meshed")
    params = tuple(parsed.params) + tuple(p for p in GLOBAL if p.name not in {q.name for q in parsed.params})
    presets = {key: _preset_values(params, values) for key, values in document.presets(source).items()}
    first = next(iter(document.presets(source).values()), {})
    camera = document.camera(first)
    bounds = min(max(camera.distance * camera.fov * 1.2, 0.5), 50.0) if camera else DEFAULT_BOUNDS
    digest = hashlib.sha1(glsl.encode()).hexdigest()[:12]
    title = name or (origin.stem if origin else "Fragment")
    return FragmentFormula(f"fragment_{slug(title)}", title, glsl, params, presets, camera, bounds,
                           " ".join(parsed.info), digest, tuple(parsed.textures.items()))


def _preset_values(params: tuple[Param, ...], values: dict[str, str]) -> dict[str, Any]:
    by_name = {p.name: p for p in params}
    return {key: annotations.from_text(by_name[key], text) for key, text in values.items() if key in by_name}




def embeddable(path: Path, folders: tuple[str, ...] = ()) -> str:
    """A fragment file's text as a `.blend` keeps it: the user's own includes inlined, Iteron's shims left by name
    (read back with `prefer_shims`, so the file builds the same anywhere)."""
    from .preprocess import is_shim
    return expand(document.read(path), Path(path), resolver([Path(f) for f in folders]), keep=is_shim)




def texture_paths(entry: FragmentFormula, path: Path | None, folders: tuple[str, ...] = ()) -> dict[str, Path]:
    """Where each texture's file is: beside the fragment, then in the include folders (`FragmentError` names a
    missing one)."""
    bases = ([Path(path).parent] if path else []) + [Path(f) for f in folders]
    found = {}
    for name, file in entry.textures:
        candidate = next((b / file for b in bases if (b / file).is_file()), Path(file) if Path(file).is_file() else None)
        if candidate is None:
            raise FragmentError(f"texture \"{file}\" (for {name}) not found beside the fragment or in the include folders")
        found[name] = candidate
    return found


__all__ = ["FragmentFormula", "FragmentError", "build", "embeddable", "texture_paths"]
