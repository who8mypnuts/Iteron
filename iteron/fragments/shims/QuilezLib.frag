#donotrun
// SPDX-License-Identifier: MIT
// Iteron's stand-in for QuilezLib.frag: Inigo Quilez's distance functions (https://iquilezles.org/articles/
// distfunctions/, MIT — Copyright (c) Inigo Quilez), under the names Fragmentarium's library uses.

float maxcomp(vec3 a) { return max(a.x, max(a.y, a.z)); }
float sdSphere(vec3 p, float s) { return length(p) - s; }
float udBox(vec3 p, vec3 b) { return length(max(abs(p) - b, 0.0)); }
float udRoundBox(vec3 p, vec3 b, float r) { return length(max(abs(p) - b, 0.0)) - r; }
float sdToBox(vec3 p, vec3 b) { vec3 d = abs(p) - b; return min(maxcomp(d), length(max(d, 0.0))); }
float sdTorus(vec3 p, vec2 t) { return length(vec2(length(p.xz) - t.x, p.y)) - t.y; }
float sdCylinder(vec3 p, vec3 c) { return length(p.xz - c.xy) - c.z; }            // endless, along y
float sdCone(vec3 p, vec2 c) { return dot(c, vec2(length(p.xy), p.z)); }         // c normalised
float sdPlane(vec3 p, vec4 n) { return dot(p, n.xyz) + n.w; }                      // n.xyz normalised
float udHexPrism(vec3 p, vec2 h) { vec3 q = abs(p); return max(q.z - h.y, max(q.x + q.y * 0.57735, q.y) - h.x); }
float opU(float d1, float d2) { return min(d1, d2); }
float opS(float d1, float d2) { return max(-d1, d2); }                             // d2 minus d1
float opI(float d1, float d2) { return max(d1, d2); }
float length8(vec2 p) { vec2 r = p * p; r = r * r; return pow(dot(r, r), 0.125); }
float length4(vec2 p) { vec2 r = p * p; return pow(dot(r, r), 0.25); }
float sdTorus88(vec3 p, vec2 t) { return length8(vec2(length8(p.xz) - t.x, p.y)) - t.y; }
