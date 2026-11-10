# SPDX-License-Identifier: MIT
"""Iteron without Blender: `python -m iteron.cli` meshes formulas, fragments and flames to PLY / OBJ files with the
same pipeline the add-on uses (`core`, `jobs`, `fragments`, `flames` never import bpy). Formulas run on the CPU
(numpy) or, with `--gpu`, through moderngl; fragments need moderngl (they are GLSL)."""
