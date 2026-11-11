# SPDX-License-Identifier: MIT
"""Open every example fragment of Fractalchemy's library (when the sample sources are in the checkout) the way the
add-on does — Iteron's shims, optionally an include folder, textures loaded — and sample each on the GPU through
moderngl. Prints a tally; fails unless every 3D fragment of the *Fractalchemy Collection* builds and samples.

    python tools/check_fragments.py [--include-folder]      (needs moderngl, an OpenGL 3.3 context and Pillow)
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
LIBRARY = ROOT / "sample_source" / "Fractalchemy" / "fractalchemy" / "fragments" / "library"


def check(include_folder: bool) -> tuple[collections.Counter, list[str], list[str]]:
    """`(tally, the Collection's failures, other failures' reasons)`."""
    from iteron.cli.commands import load_image
    from iteron.cli.gl_sampler import GlSampler, context
    from iteron.core.grid import cube_plan
    from iteron.fragments.formula import build, embeddable, texture_paths
    from iteron.fragments.preprocess import FragmentError
    from iteron.jobs.steps import run_to_end
    ctx = context()
    folders = (str(LIBRARY / "Include"),) if include_folder else ()
    tally, collection_failures, reasons = collections.Counter(), [], []
    for path in sorted((LIBRARY / "Examples").rglob("*.frag")):
        try:
            entry = build(embeddable(path, folders), path.stem, prefer_shims=True)
            textures = {name: load_image(p) for name, p in texture_paths(entry, path, folders).items()}
            values = entry.values(next(iter(entry.presets.values()), {}))
            run_to_end(GlSampler(ctx, textures).sample(entry, values, cube_plan((0.0, 0.0, 0.0), entry.bounds, 12)))
            tally["built" + (" (textured)" if textures else "")] += 1
            continue
        except FragmentError as error:
            kind = "not a 3D distance estimator" if "2D" in str(error) or "DE(vec3)" in str(error) else "unsupported"
            tally[kind] += 1
        except Exception as error:                 # noqa: BLE001 - a GLSL compile error from the driver
            tally["GLSL errors"] += 1
            reasons.append(f"{path.relative_to(LIBRARY)}: {str(error).strip().splitlines()[0][:100]}")
        if path.parent.name == "Fractalchemy Collection" and path.name.startswith("3D"):
            collection_failures.append(path.name)
    return tally, collection_failures, reasons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--include-folder", action="store_true", help="also search Fractalchemy's Include folder")
    args = parser.parse_args()
    from iteron.cli.gl_sampler import context
    if not LIBRARY.is_dir() or context() is None:
        print("skipped: no Fractalchemy library in the checkout, or no OpenGL 3.3 context")
        return 0
    tally, failures, reasons = check(args.include_folder)
    print("\n".join(reasons))
    print(", ".join(f"{count} {name}" for name, count in sorted(tally.items())))
    if failures:
        print("Fractalchemy Collection fragments that failed: " + ", ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
