// DE-Raytracer.frag — Iteron's own minimal stand-in for FragM's include of the same name.
// SPDX-License-Identifier: MIT
//
// The real DE-Raytracer.frag (GPL / LGPL, not bundled — see PLAN.md §7 / §8) is a full raymarching camera and
// shader; Iteron only meshes a distance estimator (iteron.gpu_eval), so this shim provides just the global a
// DE() function commonly writes to for orbit-trap colouring, and nothing else. `#preset` blocks that set the
// raytracer's own uniforms (FOV, Eye, Detail, …) are still read for the camera (PLAN.md §7's .fafrag / .frag row)
// even though those uniforms themselves don't exist here.

vec4 orbitTrap = vec4(1e30);
