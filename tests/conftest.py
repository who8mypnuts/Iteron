# SPDX-License-Identifier: MIT
"""Make the add-on package importable as `iteron` from the repository root."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
