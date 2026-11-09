// MathUtils.frag — Iteron's own minimal stand-in for FragM's include of the same name.
// SPDX-License-Identifier: MIT
//
// FragM's MathUtils.frag is GPL / LGPL and is not bundled (see PLAN.md §7 / §8); this shim provides just the
// handful of helpers the Fractalchemy Collection's own fragments call, written from scratch from their
// mathematics (the same formulas as iteron/formulas/common.py's rotate_axis_angle, here as plain GLSL).
// A fragment that needs more than this should point Preferences' include folders at a real FragM install.

mat3 rotationMatrix3(vec3 axis, float angleRadians) {
    axis = normalize(axis);
    float s = sin(angleRadians);
    float c = cos(angleRadians);
    float t = 1.0 - c;
    return mat3(
        t * axis.x * axis.x + c,          t * axis.x * axis.y + s * axis.z, t * axis.x * axis.z - s * axis.y,
        t * axis.x * axis.y - s * axis.z, t * axis.y * axis.y + c,          t * axis.y * axis.z + s * axis.x,
        t * axis.x * axis.z + s * axis.y, t * axis.y * axis.z - s * axis.x, t * axis.z * axis.z + c
    );
}

mat3 rotationMatrixXYZ(vec3 anglesDegrees) {
    vec3 r = radians(anglesDegrees);
    mat3 rx = mat3(1.0, 0.0, 0.0,  0.0, cos(r.x), sin(r.x),  0.0, -sin(r.x), cos(r.x));
    mat3 ry = mat3(cos(r.y), 0.0, -sin(r.y),  0.0, 1.0, 0.0,  sin(r.y), 0.0, cos(r.y));
    mat3 rz = mat3(cos(r.z), sin(r.z), 0.0,  -sin(r.z), cos(r.z), 0.0,  0.0, 0.0, 1.0);
    return rz * ry * rx;
}
