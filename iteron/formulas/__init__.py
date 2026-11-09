# SPDX-License-Identifier: MIT
"""The bundled formulas. Importing this package registers them (`core.formula.REGISTRY`)."""

from . import boxes, bulbs, kifs, quaternion, sponges  # noqa: F401  (registration by import)
