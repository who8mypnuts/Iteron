# SPDX-License-Identifier: MIT
"""Run the test suites inside Blender.

With a Blender executable (pytest must be importable by Blender's Python: `<blender-python> -m pip install pytest`):

    blender -b --factory-startup --python tools/run_blender_tests.py -- [pytest options]

With the `bpy` module from PyPI (needs the Python version that Blender uses, 3.11 for Blender 4.2 – 5.0):

    python -m pip install bpy pytest && python -m pytest tests

`tests/core` needs no Blender at all (numpy + pytest; moderngl adds the GLSL parity tests).
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    extra = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    sys.exit(pytest.main([str(ROOT / "tests"), "-p", "no:cacheprovider", *extra]))
