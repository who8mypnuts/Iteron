#donotrun
// SPDX-License-Identifier: MIT
// From Fractalchemy (Copyright (c) Stan Ragets, MIT), unchanged.
// Triplex.frag — triplex (Mandelbulb) arithmetic for Fractalchemy fragments: the White–Nylander power, a product,
// and the running-derivative bookkeeping the distance estimate needs.
//
//   #include "Triplex.frag"
//   ... inside the iteration:  dr = tPowDeriv(z, Power, dr);  z = tPow(z, Power) + c;
//   ... distance:              return 0.5 * log(r) * r / dr;

// z^n in spherical coordinates (theta from the z axis, phi around it).
vec3 tPow(vec3 z, float n) {
	float r = length(z);
	if (r < 1e-10) return vec3(0.0);
	float theta = acos(clamp(z.z / r, -1.0, 1.0)) * n;
	float phi = atan(z.y, z.x) * n;
	float rn = pow(r, n);
	return rn * vec3(sin(theta) * cos(phi), sin(theta) * sin(phi), cos(theta));
}

// The running derivative for z^n + c: dr = n r^(n-1) dr + 1 (call before tPow).
float tPowDeriv(vec3 z, float n, float dr) {
	return pow(length(z), n - 1.0) * n * dr + 1.0;
}

// Triplex product (the Mandelbulb's multiplication of two vectors, used by hybrids and the Lambdabulb).
vec3 tMul(vec3 a, vec3 b) {
	float ra = length(a), rb = length(b);
	if (ra < 1e-10 || rb < 1e-10) return vec3(0.0);
	float ta = acos(clamp(a.z / ra, -1.0, 1.0)), tb = acos(clamp(b.z / rb, -1.0, 1.0));
	float pa = atan(a.y, a.x), pb = atan(b.y, b.x);
	float t = ta + tb, p = pa + pb;
	return ra * rb * vec3(sin(t) * cos(p), sin(t) * sin(p), cos(t));
}

vec3 tSqr(vec3 z) { return tPow(z, 2.0); }

// The Mandelbulb distance estimate from the final radius and derivative.
float tDistance(vec3 z, float dr) {
	float r = length(z);
	return 0.5 * log(r) * r / dr;
}
