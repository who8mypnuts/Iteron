# SPDX-License-Identifier: MIT
"""Reading `.fafrag` / Fragmentarium `.frag` files (PLAN.md \u00a77): the metadata block, the annotated uniforms
as `core.params.Param`, the `#preset` blocks, and `#include` resolution through Iteron's own MIT shims instead of
FragM's GPL/LGPL include files. Turning the result into a compilable shader is `iteron.gpu_eval` (GPU-only, bpy);
this package only reads the text.
"""
