#donotrun
// SPDX-License-Identifier: MIT
// Iteron's Primitives.frag: signed distance primitives, operators and fractal folds, from Fractalchemy's library
// (Copyright (c) Stan Ragets, MIT). Sources: Inigo Quilez's distance functions (https://iquilezles.org/articles/
// distfunctions/, MIT), the hg_sdf library by Mercury (http://mercury.sexy/hg_sdf/, MIT) and Akleman & Chen's
// generalized distance functions (via hg_sdf). The Distance Estimator Compendium functions of Fractalchemy's copy
// (CC BY-NC-SA) are left out; point Iteron's include folders at Fractalchemy's library to use its full file.
//
// Every primitive is `float sdXxx(vec3 p, ...)`: negative inside, positive outside, centred at the origin.
#include "QuilezLib.frag"

#define PHI 1.61803398875
#define PRIM_PI 3.14159265358979

// --- small helpers ------------------------------------------------------------------------------------------------
float dot2(vec2 v) { return dot(v, v); }
float dot2(vec3 v) { return dot(v, v); }
float ndot(vec2 a, vec2 b) { return a.x * b.x - a.y * b.y; }
float length6(vec2 p) { p = p * p * p; p = p * p; return pow(p.x + p.y, 1.0 / 6.0); }
float lengthN(vec2 p, float n) { p = pow(abs(p), vec2(n)); return pow(p.x + p.y, 1.0 / n); }
float lpNorm(vec3 p, float n) { p = pow(abs(p), vec3(n)); return pow(p.x + p.y + p.z, 1.0 / n); }
mat2 rot2(float a) { float c = cos(a), s = sin(a); return mat2(c, s, -s, c); }
mat3 rot3(vec3 axis, float angle) {
	axis = normalize(axis);
	float s = sin(angle), c = cos(angle), oc = 1.0 - c;
	return mat3(oc * axis.x * axis.x + c, oc * axis.x * axis.y - axis.z * s, oc * axis.z * axis.x + axis.y * s,
	            oc * axis.x * axis.y + axis.z * s, oc * axis.y * axis.y + c, oc * axis.y * axis.z - axis.x * s,
	            oc * axis.z * axis.x - axis.y * s, oc * axis.y * axis.z + axis.x * s, oc * axis.z * axis.z + c);
}

// --- boxes and planes ----------------------------------------------------------------------------------------------
float sdBox(vec3 p, vec3 b) { vec3 q = abs(p) - b; return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0); }
float sdBoxCheap(vec3 p, vec3 b) { vec3 q = abs(p) - b; return max(max(q.x, q.y), q.z); }
float sdRoundBox(vec3 p, vec3 b, float r) { return sdBox(p, b) - r; }
float sdBoxFrame(vec3 p, vec3 b, float e) {
	p = abs(p) - b;
	vec3 q = abs(p + e) - e;
	return min(min(length(max(vec3(p.x, q.y, q.z), 0.0)) + min(max(p.x, max(q.y, q.z)), 0.0),
	               length(max(vec3(q.x, p.y, q.z), 0.0)) + min(max(q.x, max(p.y, q.z)), 0.0)),
	           length(max(vec3(q.x, q.y, p.z), 0.0)) + min(max(q.x, max(q.y, p.z)), 0.0));
}
float sdBox2D(vec2 p, vec2 b) { vec2 d = abs(p) - b; return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0); }
float sdPlane(vec3 p, vec3 n, float h) { return dot(p, normalize(n)) + h; }
float sdCorner(vec2 p) { return length(max(p, 0.0)) + min(max(p.x, p.y), 0.0); }        // an endless shelf (hg_sdf)

// --- round things --------------------------------------------------------------------------------------------------
float sdEllipsoid(vec3 p, vec3 r) { float k0 = length(p / r), k1 = length(p / (r * r)); return k0 * (k0 - 1.0) / k1; }
float sdCylinder(vec3 p, float r, float h) { vec2 d = abs(vec2(length(p.xz), p.y)) - vec2(r, h); return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)); }
float sdCylinderInfinite(vec3 p, float r) { return length(p.xz) - r; }
float sdRoundedCylinder(vec3 p, float ra, float rb, float h) {
	vec2 d = vec2(length(p.xz) - 2.0 * ra + rb, abs(p.y) - h);
	return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - rb;
}
float sdCylinder6(vec3 p, float r, float h) { return max(length6(p.xz) - r, abs(p.y) - h); }
float sdCylinder8(vec3 p, float r, float h) { return max(length8(p.xz) - r, abs(p.y) - h); }
float sdCapsule(vec3 p, float h, float r) { p.y -= clamp(p.y, -h, h); return length(p) - r; }
float sdCapsuleLine(vec3 p, vec3 a, vec3 b, float r) {
	vec3 pa = p - a, ba = b - a;
	float t = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
	return length(pa - ba * t) - r;
}
float sdTorus(vec3 p, float R, float r) { return length(vec2(length(p.xz) - R, p.y)) - r; }
float sdTorus82(vec3 p, vec2 t) { vec2 q = vec2(length(p.xz) - t.x, p.y); return length8(q) - t.y; }
float sdCappedTorus(vec3 p, float angle, float ra, float rb) {
	vec2 sc = vec2(sin(angle), cos(angle));
	p.x = abs(p.x);
	float k = (sc.y * p.x > sc.x * p.y) ? dot(p.xy, sc) : length(p.xy);
	return sqrt(dot(p, p) + ra * ra - 2.0 * ra * k) - rb;
}
float sdLink(vec3 p, float le, float r1, float r2) {
	vec3 q = vec3(p.x, max(abs(p.y) - le, 0.0), p.z);
	return length(vec2(length(q.xy) - r1, q.z)) - r2;
}
float sdDisc(vec3 p, float r) { float l = length(p.xz) - r; return length(vec2(p.y, max(l, 0.0))); }
float sdSolidAngle(vec3 p, float angle, float ra) {
	vec2 c = vec2(sin(angle), cos(angle));
	vec2 q = vec2(length(p.xz), p.y);
	float l = length(q) - ra;
	float m = length(q - c * clamp(dot(q, c), 0.0, ra));
	return max(l, m * sign(c.y * q.x - c.x * q.y));
}

// --- cones ----------------------------------------------------------------------------------------------------------
float sdCone(vec3 p, float radius, float height) {                                        // tip up the y axis (hg_sdf)
	vec2 q = vec2(length(p.xz), p.y);
	vec2 tip = q - vec2(0.0, height);
	vec2 mantleDir = normalize(vec2(height, radius));
	float mantle = dot(tip, mantleDir);
	float d = max(mantle, -q.y);
	float projected = dot(tip, vec2(mantleDir.y, -mantleDir.x));
	if (q.y > height && projected < 0.0) d = max(d, length(tip));
	if (q.x > radius && projected > length(vec2(height, radius))) d = max(d, length(q - vec2(radius, 0.0)));
	return d;
}
float sdCappedCone(vec3 p, float h, float r1, float r2) {
	vec2 q = vec2(length(p.xz), p.y);
	vec2 k1 = vec2(r2, h), k2 = vec2(r2 - r1, 2.0 * h);
	vec2 ca = vec2(q.x - min(q.x, (q.y < 0.0) ? r1 : r2), abs(q.y) - h);
	vec2 cb = q - k1 + k2 * clamp(dot(k1 - q, k2) / dot(k2, k2), 0.0, 1.0);
	float s = (cb.x < 0.0 && ca.y < 0.0) ? -1.0 : 1.0;
	return s * sqrt(min(dot(ca, ca), dot(cb, cb)));
}
float sdRoundCone(vec3 p, float r1, float r2, float h) {
	vec2 q = vec2(length(p.xz), p.y);
	float b = (r1 - r2) / h, a = sqrt(1.0 - b * b), k = dot(q, vec2(-b, a));
	if (k < 0.0) return length(q) - r1;
	if (k > a * h) return length(q - vec2(0.0, h)) - r2;
	return dot(q, vec2(a, b)) - r1;
}
float sdPyramid(vec3 p, float h) {
	float m2 = h * h + 0.25;
	p.xz = abs(p.xz);
	p.xz = (p.z > p.x) ? p.zx : p.xz;
	p.xz -= 0.5;
	vec3 q = vec3(p.z, h * p.y - 0.5 * p.x, h * p.x + 0.5 * p.y);
	float s = max(-q.x, 0.0);
	float t = clamp((q.y - 0.5 * p.z) / (m2 + 0.25), 0.0, 1.0);
	float a = m2 * (q.x + s) * (q.x + s) + q.y * q.y;
	float b = m2 * (q.x + 0.5 * t) * (q.x + 0.5 * t) + (q.y - m2 * t) * (q.y - m2 * t);
	float d2 = min(q.y, -q.x * m2 - q.y * 0.5) > 0.0 ? 0.0 : min(a, b);
	return sqrt((d2 + q.z * q.z) / m2) * sign(max(q.z, -p.y));
}

// --- prisms -------------------------------------------------------------------------------------------------------------
float sdHexPrism(vec3 p, float width, float height) {                                     // incircle radius `width`
	vec3 q = abs(p);
	return max(q.y - height, max(q.x * 0.866025404 + q.z * 0.5, q.z) - width);
}
float sdTriPrism(vec3 p, vec2 h) {                                                         // h = (side, half depth)
	const float k = 1.7320508;
	h.x *= 0.5 * k;
	p.xy /= h.x;
	p.x = abs(p.x) - 1.0;
	p.y = p.y + 1.0 / k;
	if (p.x + k * p.y > 0.0) p.xy = vec2(p.x - k * p.y, -k * p.x - p.y) / 2.0;
	p.x -= clamp(p.x, -2.0, 0.0);
	float d1 = length(p.xy) * sign(-p.y) * h.x;
	float d2 = abs(p.z) - h.y;
	return length(max(vec2(d1, d2), 0.0)) + min(max(d1, d2), 0.0);
}
float sdOctPrism(vec3 p, float r, float h) {
	const vec3 k = vec3(-0.9238795325, 0.3826834323, 0.4142135623);
	p = abs(p);
	p.xy -= 2.0 * min(dot(vec2(k.x, k.y), p.xy), 0.0) * vec2(k.x, k.y);
	p.xy -= 2.0 * min(dot(vec2(-k.x, k.y), p.xy), 0.0) * vec2(-k.x, k.y);
	p.xy -= vec2(clamp(p.x, -k.z * r, k.z * r), r);
	vec2 d = vec2(length(p.xy) * sign(p.y), p.z - h);
	return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
}
float sdRhombus(vec3 p, float la, float lb, float h, float ra) {
	p = abs(p);
	vec2 b = vec2(la, lb);
	float f = clamp((ndot(b, b - 2.0 * p.xz)) / dot(b, b), -1.0, 1.0);
	vec2 q = vec2(length(p.xz - 0.5 * b * vec2(1.0 - f, 1.0 + f)) * sign(p.x * b.y + p.z * b.x - b.x * b.y) - ra, p.y - h);
	return min(max(q.x, q.y), 0.0) + length(max(q, 0.0));
}

// --- polyhedra --------------------------------------------------------------------------------------------------------
float sdOctahedron(vec3 p, float s) {
	p = abs(p);
	float m = p.x + p.y + p.z - s;
	vec3 q;
	if (3.0 * p.x < m) q = p.xyz;
	else if (3.0 * p.y < m) q = p.yzx;
	else if (3.0 * p.z < m) q = p.zxy;
	else return m * 0.57735027;
	float k = clamp(0.5 * (q.z - q.y + s), 0.0, s);
	return length(vec3(q.x, q.y - s + k, q.z - k));
}
float sdOctahedronCheap(vec3 p, float s) { p = abs(p); return (p.x + p.y + p.z - s) * 0.57735027; }
// Akleman & Chen's generalized distance functions (via hg_sdf): sharp polyhedra, or bulging ones with an exponent.
const vec3 GDFVectors[19] = vec3[19](             // unit vectors as literals (Math.frag may redefine normalize)
	vec3(1.0, 0.0, 0.0), vec3(0.0, 1.0, 0.0), vec3(0.0, 0.0, 1.0),
	vec3(0.577350269, 0.577350269, 0.577350269), vec3(-0.577350269, 0.577350269, 0.577350269),
	vec3(0.577350269, -0.577350269, 0.577350269), vec3(0.577350269, 0.577350269, -0.577350269),
	vec3(0.0, 0.35682209, 0.934172359), vec3(0.0, -0.35682209, 0.934172359), vec3(0.934172359, 0.0, 0.35682209),
	vec3(-0.934172359, 0.0, 0.35682209), vec3(0.35682209, 0.934172359, 0.0), vec3(-0.35682209, 0.934172359, 0.0),
	vec3(0.0, 0.850650808, 0.525731112), vec3(0.0, -0.850650808, 0.525731112), vec3(0.525731112, 0.0, 0.850650808),
	vec3(-0.525731112, 0.0, 0.850650808), vec3(0.850650808, 0.525731112, 0.0), vec3(-0.850650808, 0.525731112, 0.0));
float fGDF(vec3 p, float r, float e, int begin, int end) {
	float d = 0.0;
	for (int i = begin; i <= end; ++i) d += pow(abs(dot(p, GDFVectors[i])), e);
	return pow(d, 1.0 / e) - r;
}
float fGDF(vec3 p, float r, int begin, int end) {
	float d = 0.0;
	for (int i = begin; i <= end; ++i) d = max(d, abs(dot(p, GDFVectors[i])));
	return d - r;
}
float sdGDFOctahedron(vec3 p, float r) { return fGDF(p, r, 3, 6); }
float sdGDFDodecahedron(vec3 p, float r) { return fGDF(p, r, 13, 18); }
float sdGDFIcosahedron(vec3 p, float r) { return fGDF(p, r, 3, 12); }
float sdGDFTruncatedOctahedron(vec3 p, float r) { return fGDF(p, r, 0, 6); }
float sdGDFTruncatedIcosahedron(vec3 p, float r) { return fGDF(p, r, 3, 18); }
float sdGDFCube(vec3 p, float r) { return fGDF(p, r, 0, 2); }

// --- surfaces -----------------------------------------------------------------------------------------------------------
float sdSchwarzP(vec3 p, float scale, float thickness) {
	p *= scale;
	return (abs(cos(p.x) + cos(p.y) + cos(p.z)) / scale - thickness) * 0.5;
}
float udTriangle(vec3 p, vec3 v1, vec3 v2, vec3 v3) {
	vec3 v21 = v2 - v1, p1 = p - v1, v32 = v3 - v2, p2 = p - v2, v13 = v1 - v3, p3 = p - v3;
	vec3 nor = cross(v21, v13);
	return sqrt((sign(dot(cross(v21, nor), p1)) + sign(dot(cross(v32, nor), p2)) + sign(dot(cross(v13, nor), p3)) < 2.0)
	            ? min(min(dot2(v21 * clamp(dot(v21, p1) / dot2(v21), 0.0, 1.0) - p1), dot2(v32 * clamp(dot(v32, p2) / dot2(v32), 0.0, 1.0) - p2)),
	                  dot2(v13 * clamp(dot(v13, p3) / dot2(v13), 0.0, 1.0) - p3))
	            : dot(nor, p1) * dot(nor, p1) / dot2(nor));
}
float udQuad(vec3 p, vec3 v1, vec3 v2, vec3 v3, vec3 v4) {
	if (dot(cross(v2 - v1, v4 - v1), cross(v4 - v3, v2 - v3)) < 0.0) { vec3 tmp = v3; v3 = v4; v4 = tmp; }
	vec3 v21 = v2 - v1, p1 = p - v1, v32 = v3 - v2, p2 = p - v2, v43 = v4 - v3, p3 = p - v3, v14 = v1 - v4, p4 = p - v4;
	vec3 nor = cross(v21, v14);
	return sqrt((sign(dot(cross(v21, nor), p1)) + sign(dot(cross(v32, nor), p2)) + sign(dot(cross(v43, nor), p3)) + sign(dot(cross(v14, nor), p4)) < 3.0)
	            ? min(min(dot2(v21 * clamp(dot(v21, p1) / dot2(v21), 0.0, 1.0) - p1), dot2(v32 * clamp(dot(v32, p2) / dot2(v32), 0.0, 1.0) - p2)),
	                  min(dot2(v43 * clamp(dot(v43, p3) / dot2(v43), 0.0, 1.0) - p3), dot2(v14 * clamp(dot(v14, p4) / dot2(v14), 0.0, 1.0) - p4)))
	            : dot(nor, p1) * dot(nor, p1) / dot2(nor));
}

// --- operators ------------------------------------------------------------------------------------------------------------
float opUnion(float a, float b) { return min(a, b); }
float opSubtract(float a, float b) { return max(a, -b); }                                  // a minus b
float opIntersect(float a, float b) { return max(a, b); }
float opSmoothUnion(float a, float b, float k) { float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0); return mix(b, a, h) - k * h * (1.0 - h); }
float opSmoothSubtract(float a, float b, float k) { float h = clamp(0.5 - 0.5 * (a + b) / k, 0.0, 1.0); return mix(a, -b, h) + k * h * (1.0 - h); }
float opSmoothIntersect(float a, float b, float k) { float h = clamp(0.5 - 0.5 * (b - a) / k, 0.0, 1.0); return mix(b, a, h) + k * h * (1.0 - h); }
float opRound(float d, float r) { return d - r; }
float opOnion(float d, float thickness) { return abs(d) - thickness; }
vec3 opElongate(vec3 p, vec3 h) { return p - clamp(p, -h, h); }                            // stretch a primitive's middle
vec3 opRepeat(vec3 p, vec3 period) { return mod(p + 0.5 * period, period) - 0.5 * period; }
vec3 opRepeatLimited(vec3 p, float period, vec3 limit) { return p - period * clamp(round(p / period), -limit, limit); }
vec3 opRepeatMirror(vec3 p, vec3 period) {                                                 // every other cell mirrored (hg_sdf)
	vec3 half_ = period * 0.5;
	vec3 c = floor((p + half_) / period);
	p = mod(p + half_, period) - half_;
	return p * (mod(c, vec3(2.0)) * 2.0 - 1.0);
}
vec2 opRepeatPolar(vec2 p, float n) {                                                      // n wedges around the origin
	float angle = 2.0 * PRIM_PI / n;
	float a = atan(p.y, p.x) + angle / 2.0;
	float r = length(p);
	a = mod(a, angle) - angle / 2.0;
	return vec2(cos(a), sin(a)) * r;
}
vec3 opTwist(vec3 p, float k) { p.xz *= rot2(k * p.y); return p; }
vec3 opBend(vec3 p, float k) { p.xy *= rot2(k * p.x); return p; }
vec3 opTranslate(vec3 p, vec3 t) { return p - t; }
vec3 opMirror(vec3 p) { return abs(p); }
vec3 opFoldPlane(vec3 p, vec3 n) { n = normalize(n); return p - 2.0 * min(0.0, dot(p, n)) * n; }   // reflect into the half-space of n
float opDisplaceSine(vec3 p, float freq, float amp) { return sin(freq * p.x) * sin(freq * p.y) * sin(freq * p.z) * amp; }

// --- fractal folds (apply in a loop, then divide the primitive's distance by the accumulated scale) -----------------------
vec3 foldBox(vec3 p, float limit) { return clamp(p, -limit, limit) * 2.0 - p; }
vec3 foldSphere(vec3 p, inout float scale, float minRadius2, float fixedRadius2) {
	float r2 = dot(p, p);
	float f = r2 < minRadius2 ? fixedRadius2 / minRadius2 : r2 < fixedRadius2 ? fixedRadius2 / r2 : 1.0;
	scale *= f;
	return p * f;
}
vec3 foldMenger(vec3 p) {                                                                  // sort the axes: x ≥ y ≥ z
	p = abs(p);
	if (p.x < p.y) p.xy = p.yx;
	if (p.x < p.z) p.xz = p.zx;
	if (p.y < p.z) p.yz = p.zy;
	return p;
}
vec3 foldSierpinski(vec3 p) {
	if (p.x + p.y < 0.0) p.xy = -p.yx;
	if (p.x + p.z < 0.0) p.xz = -p.zx;
	if (p.y + p.z < 0.0) p.yz = -p.zy;
	return p;
}
vec3 foldOctahedral(vec3 p) { return foldMenger(p); }
vec2 foldKaleido(vec2 p, float n) { return opRepeatPolar(p, n); }
float smin(float a, float b, float k) { return opSmoothUnion(a, b, k); }
