#donotrun
// SPDX-License-Identifier: MIT
// Iteron's stand-in for Fragmentarium's MathUtils.frag: the same function names, written for Iteron from the
// textbook formulas (axis–angle rotation, homogeneous translation and scale, a hash for pseudo-random numbers).
#ifndef FLT_MAX
#define FLT_MAX 3.402823466e+38
#endif
#ifndef FLT_MIN
#define FLT_MIN 1.175494351e-38
#endif

// The rotation about the unit axis v by `angle` degrees, in Fragmentarium's convention (the matrix is the
// transpose of the right-handed rotation: `m * p` turns p by −angle).
mat3 rotationMatrix3(vec3 v, float angle) {
	float a = radians(angle);
	float c = cos(a), s = sin(a);
	mat3 cross = mat3(0.0, -v.z, v.y, v.z, 0.0, -v.x, -v.y, v.x, 0.0);
	return mat3(c) + (1.0 - c) * outerProduct(v, v) + s * cross;
}

// Rotations about x, then y, then z (degrees), multiplied in that order.
mat3 rotationMatrixXYZ(vec3 v) {
	return rotationMatrix3(vec3(1.0, 0.0, 0.0), v.x) * rotationMatrix3(vec3(0.0, 1.0, 0.0), v.y)
		* rotationMatrix3(vec3(0.0, 0.0, 1.0), v.z);
}

mat4 rotationMatrix(vec3 v, float angle) { return mat4(rotationMatrix3(v, angle)); }

mat4 translate(vec3 v) {
	mat4 m = mat4(1.0);
	m[3] = vec4(v, 1.0);
	return m;
}

mat4 scale4(float s) { return mat4(vec4(s, 0.0, 0.0, 0.0), vec4(0.0, s, 0.0, 0.0), vec4(0.0, 0.0, s, 0.0), vec4(0.0, 0.0, 0.0, 1.0)); }

#ifdef WANG_HASH
// Thomas Wang's 32-bit integer hash.
uint wang_hash(uint seed) {
	seed = (seed ^ 61u) ^ (seed >> 16u);
	seed *= 9u;
	seed ^= seed >> 4u;
	seed *= 0x27d4eb2du;
	seed ^= seed >> 15u;
	return seed;
}
float wang_hash_fp(float v) { return float(wang_hash(floatBitsToUint(v))) / 4294967296.0; }
vec2 wang_hash_fp(vec2 v) {
	uint x = floatBitsToUint(v.x), y = floatBitsToUint(v.y);
	return vec2(float(wang_hash(wang_hash(x) + y)), float(wang_hash(wang_hash(y) + x))) / 4294967296.0;
}
vec3 wang_hash_fp(vec3 v) {
	uint x = floatBitsToUint(v.x), y = floatBitsToUint(v.y), z = floatBitsToUint(v.z);
	return vec3(float(wang_hash(wang_hash(wang_hash(x) + y) + z)), float(wang_hash(wang_hash(wang_hash(y) + x) + z)),
		float(wang_hash(wang_hash(wang_hash(z) + x) + y))) / 4294967296.0;
}
float rand(float v) { return wang_hash_fp(v); }
float rand(vec2 p) { return wang_hash_fp(p).x; }
float rand(vec3 p) { return wang_hash_fp(p).x; }
vec2 rand2(vec2 p) { return wang_hash_fp(p); }
#else
// The classic one-line sine hash.
float rand(float v) { return fract(sin(v * 78.233) * 43758.5453); }
float rand(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
float rand(vec3 p) { return fract(sin(dot(p * 0.123, vec3(12.9898, 78.233, 112.166))) * 43758.5453); }
vec2 rand2(vec2 p) {
	return vec2(fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453), fract(cos(dot(p, vec2(4.898, 7.23))) * 23421.631));
}
#endif
