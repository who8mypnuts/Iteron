# SPDX-License-Identifier: MIT
"""Reading one `.fafrag` / `.frag` file into its parts (PLAN.md \u00a77): the metadata, the parameters, the
presets, and the GLSL with every `#include` resolved through Iteron's shims. Compiling it is `iteron.gpu_eval`'s
job (bpy, GPU-only); this stays Qt- and bpy-free.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...core.params import Param
from . import annotations, document, presets
from .preprocess import Preprocessed, resolve


@dataclass
class FragmentFile:
    source: str                                    # original text, metadata block included
    glsl: str                                       # with every #include expanded
    params: list[Param]
    presets: dict[str, dict[str, object]]
    metadata: dict | None
    includes: list[Path]


def read_text(text: str, path: Path | None = None, include_dirs: list[Path] | None = None) -> FragmentFile:
    body, metadata = document.split(text)
    expanded: Preprocessed = resolve(body, beside=path, include_dirs=include_dirs)
    return FragmentFile(source=text, glsl=expanded.source, params=annotations.parse(body),
                         presets=presets.parse(body), metadata=metadata, includes=expanded.resolved)


def read_file(path: str | Path, include_dirs: list[Path] | None = None) -> FragmentFile:
    path = Path(path)
    return read_text(path.read_text(encoding="utf-8"), path, include_dirs)
