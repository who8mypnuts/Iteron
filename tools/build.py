# SPDX-License-Identifier: MIT
"""Build the installable extension zip: copy the branding icons into the package, then zip it.

    python tools/build.py                      # dist/iteron-<version>.zip, zipped here
    python tools/build.py --blender blender    # the same through `blender --command extension build` (validates)

`branding/addon/*.png` is the single source of the add-on's icons; `iteron/icons/` is build output (git-ignored).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE, DIST = ROOT / "iteron", ROOT / "dist"
SKIP_PARTS, SKIP_SUFFIXES = {"__pycache__", ".pytest_cache"}, {".pyc", ".pyo", ".zip"}


def copy_icons() -> None:
    target = PACKAGE / "icons"
    target.mkdir(exist_ok=True)
    for png in sorted((ROOT / "branding" / "addon").glob("*.png")):
        shutil.copy2(png, target / png.name)


def manifest() -> dict:
    with open(PACKAGE / "blender_manifest.toml", "rb") as handle:
        return tomllib.load(handle)


def build_zip() -> Path:
    DIST.mkdir(exist_ok=True)
    path = DIST / f"{manifest()['id']}-{manifest()['version']}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(PACKAGE.rglob("*")):
            relative = file.relative_to(PACKAGE)
            if file.is_file() and not (set(relative.parts) & SKIP_PARTS) and file.suffix not in SKIP_SUFFIXES:
                archive.write(file, relative.as_posix())
    return path


def build_with_blender(blender: str) -> None:
    DIST.mkdir(exist_ok=True)
    subprocess.run([blender, "--command", "extension", "build", "--source-dir", str(PACKAGE),
                    "--output-dir", str(DIST)], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--blender", help="a Blender executable: build (and validate) with Blender's own tool")
    args = parser.parse_args()
    copy_icons()
    if args.blender:
        build_with_blender(args.blender)
    else:
        print(build_zip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
