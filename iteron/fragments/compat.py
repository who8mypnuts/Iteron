# SPDX-License-Identifier: MIT
"""Fragment GLSL made to compile inside Iteron's probe and preview shaders (any Blender GPU backend).

Fragmentarium code is GLSL 1.20 written for a full-screen renderer; Iteron only calls its `DE`. So:

* uniforms become plain globals — the annotated ones are loaded from Iteron's uniform block at the start of every
  evaluation, the others (the host's `time`, `pixelSize` …) keep zero values; a uniform declared twice is kept once;
* textures can't be supplied, so a sampler uniform is reported by name;
* `double` / `dvec` / `dmat` become their float forms (the GPU path is float32), `1.0LF` literals lose the suffix;
* a `main`, `gl_FragColor`, `fragColor` and `varying` declarations are renamed out of the way (a fragment's own
  `main` is never called);
* `precision` statements go. `#version` / `#extension` lines were already commented out by the preprocessor;
* `PI` is defined when the code uses it and doesn't define it (FragM's 3D setup does).
"""

from __future__ import annotations

import re

from ..core.params import Param

RE_UNIFORM = re.compile(r"^(\s*)uniform\s+(?:(?:lowp|mediump|highp)\s+)?(\w+)\s+(\w+)\s*(\[[^\]]*\])?\s*;(.*)$")
RE_VARYING = re.compile(r"^(\s*)(?:varying|flat\s+in|in|out)\s+(?:(?:lowp|mediump|highp)\s+)?(\w+\s+\w+\s*(?:\[[^\]]*\])?\s*;.*)$")
RE_PRECISION = re.compile(r"^\s*precision\s+\w+\s+\w+\s*;")
RE_MAIN = re.compile(r"\bvoid\s+main\s*\(")
RENAMES = ((re.compile(r"\bgl_FragData\s*\[\s*\d+\s*\]"), "iteron_frag_color"),
           (re.compile(r"\bgl_FragColor\b"), "iteron_frag_color"),
           (re.compile(r"\bfragColor\b"), "iteron_frag_color"),
           (re.compile(r"\bdouble\b"), "float"), (re.compile(r"\bdvec([234])\b"), r"vec\1"),
           (re.compile(r"\bdmat([234](?:x[234])?)\b"), r"mat\1"),
           (re.compile(r"(\d\.?\d*(?:[eE][-+]?\d+)?)(?:lf|LF)\b"), r"\1"),
           (re.compile(r"#\s*include\b"), "(include)"))      # left in comments: no host include resolver may see it
PRELUDE = "vec4 iteron_frag_color;\n"
PI_DEFINE = "#define PI 3.14159265358979323846\n"
RE_USES_PI, RE_DEFINES_PI = re.compile(r"\bPI\b"), re.compile(r"^\s*#\s*define\s+PI\b", re.MULTILINE)
# the host's settings a DE occasionally reads (declared by the ray tracer shim), at Fragmentarium's usual defaults
HOST_DEFAULTS = {"FOV": "0.4", "Eye": "vec3(0.0, 0.0, -10.0)", "Up": "vec3(0.0, 1.0, 0.0)", "Detail": "-2.3",
                 "DetailAO": "-0.5", "FudgeFactor": "1.0", "MaxDistance": "1000.0", "MaxRaySteps": "56",
                 "NormalBackStep": "1.0", "Specular": "0.4", "SpecularExp": "16.0", "ShadowSoft": "2.0",
                 "BaseColor": "vec3(1.0)", "BackgroundColor": "vec3(0.6, 0.6, 0.45)", "GradientBackground": "0.3",
                 "Cycles": "1.1", "FloorNormal": "vec3(0.0, 0.0, 1.0)", "FloorColor": "vec3(1.0)",
                 "pixelSize": "vec2(0.001)"}


def zero(glsl_type: str) -> str:
    """A neutral initial value for a global of `glsl_type`."""
    if glsl_type == "bool":
        return "false"
    if glsl_type in ("int", "uint"):
        return "0" if glsl_type == "int" else "0u"
    if glsl_type.startswith("mat"):
        return f"{glsl_type}(1.0)"
    return f"{glsl_type}(0.0)" if glsl_type != "float" else "0.0"


def convert(code: str, params: list[Param]) -> tuple[str, list[str]]:
    """`(GLSL for the probe, unsupported features by name)`."""
    loaded = {p.name for p in params}
    declared: set[str] = set()
    problems: list[str] = []
    out = []
    for line in code.splitlines():
        for pattern, replacement in RENAMES:
            line = pattern.sub(replacement, line)
        if RE_PRECISION.match(line):
            line = "// " + line.strip()
        elif match := RE_UNIFORM.match(line):
            indent, glsl_type, name, array, rest = match.groups()
            if "sampler" in glsl_type or "image" in glsl_type:
                problems.append(f"textures ({name})")
                line = "// " + line.strip()
            elif name in declared:
                line = "// " + line.strip() + "  (declared before)"
            else:
                declared.add(name)
                init = "" if array or name in loaded else f" = {HOST_DEFAULTS.get(name, zero(glsl_type))}"
                line = f"{indent}{glsl_type} {name}{array or ''}{init};{rest}"
        elif match := RE_VARYING.match(line):
            line = match.group(1) + match.group(2)
        line = RE_MAIN.sub("void iteron_fragment_main(", line)
        out.append(line)
    code = "\n".join(out)
    pi = PI_DEFINE if RE_USES_PI.search(code) and not RE_DEFINES_PI.search(code) else ""
    return PRELUDE + pi + code, problems
