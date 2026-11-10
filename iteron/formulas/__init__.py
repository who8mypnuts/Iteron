# SPDX-License-Identifier: MIT
"""The bundled formulas. Importing this package registers them (`core.formula.REGISTRY`)."""

from . import boxes, bulbs, kifs, quaternion, sponges  # noqa: F401  (registration by import)
from . import box_variants, bulb_variants, cubes, hypercomplex, inversions, polyhedra  # noqa: F401
from . import hybrid  # noqa: F401  (last: it combines the others)
