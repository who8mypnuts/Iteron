# SPDX-License-Identifier: MIT
"""The live preview's shader source: ray-march a formula's traced kernel inside its box, in the object's space.

The box is drawn with its back faces (so the camera may be inside it). Each fragment un-projects its pixel into a
ray in object space (perspective, orthographic and any object transform alike), marches the distance estimate until
it drops below the pixel's footprint at that depth (measured from the neighbouring pixel's ray, so detail follows the
zoom), takes the normal from a tetrahedral stencil, colours the hit from the object's ramp (a 256 × 1 texture) by the
chosen channel, and writes the hit's depth so the fractal sorts correctly among other objects.

Shared by Blender (`gpu_eval/raymarch.py`) and the development harness, like the probe sources in `glsl.py`.
"""

from __future__ import annotations

import numpy as np

STRUCT = "IteronView"
UNIFORM = "iteron_view"
RAMP = "iteron_ramp"
TYPEDEF = f"""struct {STRUCT} {{
    mat4 mvp;           /* object space → clip space */
    mat4 inverse_mvp;
    vec4 viewport;      /* x, y, width, height of the region, in framebuffer pixels */
    vec4 box_lo;        /* the box the fractal lives in (object space) */
    vec4 box_hi;
    vec4 options;       /* detail (pixels), max steps, channel (0 trap 1 iterations 2 radius 3 solid), unused */
    vec4 range_lo;      /* per channel: the values the ramp's ends stand for */
    vec4 range_hi;
}};"""

VERTEX = f"""
void main() {{
    vec3 p = {UNIFORM}.box_lo.xyz + pos * ({UNIFORM}.box_hi.xyz - {UNIFORM}.box_lo.xyz);
    gl_Position = {UNIFORM}.mvp * vec4(p, 1.0);
}}
"""

FRAGMENT = f"""
vec3 iteron_unproject(vec2 ndc, float z) {{
    vec4 p = {UNIFORM}.inverse_mvp * vec4(ndc, z, 1.0);
    return p.xyz / p.w;
}}

float iteron_de(vec3 p) {{ return iteron_kernel(p).x; }}

void main() {{
    vec2 ndc = (gl_FragCoord.xy - {UNIFORM}.viewport.xy) / {UNIFORM}.viewport.zw * 2.0 - 1.0;
    vec3 origin = iteron_unproject(ndc, -1.0);
    vec3 dir = normalize(iteron_unproject(ndc, 1.0) - origin);
    vec2 side = ndc + vec2(2.0 / {UNIFORM}.viewport.z, 0.0);          /* the next pixel's ray: the footprint */
    vec3 origin2 = iteron_unproject(side, -1.0);
    vec3 dir2 = normalize(iteron_unproject(side, 1.0) - origin2);
    vec3 inv = 1.0 / dir;
    vec3 ta = ({UNIFORM}.box_lo.xyz - origin) * inv, tb = ({UNIFORM}.box_hi.xyz - origin) * inv;
    vec3 tmin = min(ta, tb), tmax = max(ta, tb);
    float t = max(max(max(tmin.x, tmin.y), tmin.z), 0.0);
    float t_exit = min(min(tmax.x, tmax.y), tmax.z);
    if (t_exit <= t) discard;
    float detail = {UNIFORM}.options.x;
    int steps = int({UNIFORM}.options.y);
    float footprint = 0.0;
    bool hit = false;
    for (int i = 0; i < 1024; i++) {{
        if (i >= steps) break;
        vec3 p = origin + dir * t;
        footprint = length(origin2 + dir2 * t - p) * detail;
        float d = iteron_de(p);
        if (d < footprint) {{ hit = true; break; }}
        t += max(d * 0.9, footprint * 0.25);
        if (t > t_exit) break;
    }}
    if (!hit) discard;
    vec3 p = origin + dir * t;
    float e = max(footprint * 0.5, 1e-7);
    vec3 n = normalize(vec3(1.0, -1.0, -1.0) * iteron_de(p + vec3(e, -e, -e))
                     + vec3(-1.0, -1.0, 1.0) * iteron_de(p + vec3(-e, -e, e))
                     + vec3(-1.0, 1.0, -1.0) * iteron_de(p + vec3(-e, e, -e))
                     + vec3(1.0, 1.0, 1.0) * iteron_de(p + vec3(e, e, e)));
    vec4 k = iteron_kernel(p);
    int channel = int({UNIFORM}.options.z);
    float value = channel == 0 ? k.y : (channel == 1 ? k.z : k.w);
    float lo = channel == 0 ? {UNIFORM}.range_lo.x : (channel == 1 ? {UNIFORM}.range_lo.y : {UNIFORM}.range_lo.z);
    float hi = channel == 0 ? {UNIFORM}.range_hi.x : (channel == 1 ? {UNIFORM}.range_hi.y : {UNIFORM}.range_hi.z);
    float at = channel == 3 ? 0.0 : clamp((value - lo) / max(hi - lo, 1e-9), 0.0, 1.0);
    vec3 albedo = texture({RAMP}, vec2(at, 0.5)).rgb;
    vec3 key = normalize(-dir + vec3(0.0, 0.0, 0.6));
    float light = 0.22 + 0.58 * max(dot(n, -dir), 0.0) + 0.32 * max(dot(n, key), 0.0);
    vec3 linear = albedo * light;
    fragColor = vec4(pow(max(linear, vec3(0.0)), vec3(1.0 / 2.2)), 1.0);  /* the overlay is display-referred */
    vec4 clip = {UNIFORM}.mvp * vec4(p, 1.0);
    gl_FragDepth = clip.z / clip.w * 0.5 + 0.5;
}}
"""

_FACES = (((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)), ((0, 0, 1), (0, 1, 1), (1, 1, 1), (1, 0, 1)),
          ((0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 0, 0)), ((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)),
          ((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)), ((1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)))
# the unit cube as triangles wound counter-clockwise seen from outside (the draw culls front faces: only the far
# side is drawn, so the preview also works with the camera inside the box)
CUBE = [corner for a, b, c, d in _FACES for corner in (a, c, b, a, d, c)]
CHANNELS = {"TRAP": 0, "ITERATIONS": 1, "RADIUS": 2, "SOLID": 3}
DETAIL, MAX_STEPS = 1.0, 256


def view_block(mvp: np.ndarray, viewport, box_lo, box_hi, channel: str, range_lo, range_hi,
               detail: float = DETAIL, steps: int = MAX_STEPS) -> np.ndarray:
    """The view uniform block's contents (std140: column-major mat4s, then vec4s), float32."""
    mvp = np.asarray(mvp, dtype=np.float64)
    rows = [mvp.T.ravel(), np.linalg.inv(mvp).T.ravel(), np.asarray(viewport, dtype=np.float64),
            [*box_lo, 0.0], [*box_hi, 0.0], [detail, steps, CHANNELS[channel], 0.0],
            [*range_lo, 0.0], [*range_hi, 0.0]]
    return np.concatenate([np.asarray(r, dtype=np.float64).ravel() for r in rows]).astype(np.float32)
