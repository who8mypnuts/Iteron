# SPDX-License-Identifier: MIT
"""The flam3 classics (numpy). Ported from Fractalchemy's natively written `formulas/builtin/flam3.py` (Stan Ragets,
MIT); the formulas are flam3's (Scott Draves et al.)."""

from __future__ import annotations

import numpy as np

from .variations import EPS, PASS, PI, Point, variation


@variation("linear", z=PASS, aliases=("linear3D",))
def _linear(p: Point):
    return p.w * p.x, p.w * p.y


@variation("sinusoidal", z=PASS)
def _sinusoidal(p: Point):
    return p.w * np.sin(p.x), p.w * np.sin(p.y)


@variation("spherical", z=PASS)
def _spherical(p: Point):
    k = p.w / (p.r2 + EPS)
    return k * p.x, k * p.y


@variation("swirl", z=PASS)
def _swirl(p: Point):
    sr, cr = np.sin(p.r2), np.cos(p.r2)
    return p.w * (sr * p.x - cr * p.y), p.w * (cr * p.x + sr * p.y)


@variation("horseshoe", z=PASS)
def _horseshoe(p: Point):
    k = p.w / (p.r + EPS)
    return k * (p.x - p.y) * (p.x + p.y), k * 2.0 * p.x * p.y


@variation("polar", z=PASS)
def _polar(p: Point):
    return p.w * p.theta / PI, p.w * (p.r - 1.0)


@variation("handkerchief")
def _handkerchief(p: Point):
    return p.w * p.r * np.sin(p.theta + p.r), p.w * p.r * np.cos(p.theta - p.r)


@variation("heart")
def _heart(p: Point):
    a = p.theta * p.r
    return p.w * p.r * np.sin(a), -p.w * p.r * np.cos(a)


@variation("disc", z=PASS)
def _disc(p: Point):
    a, pr = p.theta / PI, PI * p.r
    return p.w * a * np.sin(pr), p.w * a * np.cos(pr)


@variation("spiral", z=PASS)
def _spiral(p: Point):
    k = p.w / (p.r + EPS)
    return k * (np.cos(p.theta) + np.sin(p.r)), k * (np.sin(p.theta) - np.cos(p.r))


@variation("hyperbolic", z=PASS)
def _hyperbolic(p: Point):
    return p.w * np.sin(p.theta) / (p.r + EPS), p.w * np.cos(p.theta) * p.r


@variation("diamond", z=PASS)
def _diamond(p: Point):
    return p.w * np.sin(p.theta) * np.cos(p.r), p.w * np.cos(p.theta) * np.sin(p.r)


@variation("ex")
def _ex(p: Point):
    n0, n1 = np.sin(p.theta + p.r), np.cos(p.theta - p.r)
    m0, m1 = n0 ** 3 * p.r, n1 ** 3 * p.r
    return p.w * (m0 + m1), p.w * (m0 - m1)


@variation("julia")
def _julia(p: Point):
    a = 0.5 * p.theta + np.where(p.rnd() < 0.5, 0.0, PI)
    sr = p.w * np.sqrt(p.r)
    return sr * np.cos(a), sr * np.sin(a)


@variation("bent")
def _bent(p: Point):
    return p.w * np.where(p.x < 0, p.x * 2.0, p.x), p.w * np.where(p.y < 0, p.y * 0.5, p.y)


@variation("waves")
def _waves(p: Point):
    _a, _b, c, d, e, f = p.coefs
    return p.w * (p.x + c * np.sin(p.y / (e * e + EPS))), p.w * (p.y + d * np.sin(p.x / (f * f + EPS)))


@variation("fisheye")
def _fisheye(p: Point):
    k = 2.0 * p.w / (p.r + 1.0)
    return k * p.y, k * p.x


@variation("popcorn")
def _popcorn(p: Point):
    e, f = p.coefs[4], p.coefs[5]
    return p.w * (p.x + e * np.sin(np.tan(3.0 * p.y))), p.w * (p.y + f * np.sin(np.tan(3.0 * p.x)))


@variation("exponential")
def _exponential(p: Point):
    dx, dy = p.w * np.exp(p.x - 1.0), PI * p.y
    return dx * np.cos(dy), dx * np.sin(dy)


@variation("power")
def _power(p: Point):
    k = p.w * np.power(p.r + EPS, np.sin(p.theta))
    return k * np.cos(p.theta), k * np.sin(p.theta)


@variation("cosine")
def _cosine(p: Point):
    a = PI * p.x
    return p.w * np.cos(a) * np.cosh(p.y), -p.w * np.sin(a) * np.sinh(p.y)


@variation("rings")
def _rings(p: Point):
    dx = p.coefs[4] ** 2 + EPS
    k = p.w * (np.mod(p.r + dx, 2.0 * dx) - dx + p.r * (1.0 - dx))
    return k * np.cos(p.theta), k * np.sin(p.theta)


@variation("fan")
def _fan(p: Point):
    dx = PI * (p.coefs[4] ** 2 + EPS)
    dx2, dy = dx * 0.5, p.coefs[5]
    a = np.where(np.mod(p.theta + dy, dx) > dx2, p.theta - dx2, p.theta + dx2)
    return p.w * p.r * np.cos(a), p.w * p.r * np.sin(a)


@variation("blob", {"low": 0.2, "high": 1.0, "waves": 2.0})
def _blob(p: Point):
    low, high, waves = p.p("blob_low"), p.p("blob_high"), p.p("blob_waves")
    k = p.r * (low + (high - low) * (0.5 + 0.5 * np.sin(waves * p.theta)))
    return p.w * k * np.sin(p.theta), p.w * k * np.cos(p.theta)


@variation("pdj", {"a": 0.0, "b": 0.0, "c": 0.0, "d": 0.0}, z=PASS)
def _pdj(p: Point):
    a, b, c, d = p.p("pdj_a"), p.p("pdj_b"), p.p("pdj_c"), p.p("pdj_d")
    return p.w * (np.sin(a * p.y) - np.cos(b * p.x)), p.w * (np.sin(c * p.x) - np.cos(d * p.y))


@variation("fan2", {"x": 0.0, "y": 0.0}, z=PASS)
def _fan2(p: Point):
    dy, dx = p.p("fan2_y"), PI * (p.p("fan2_x") ** 2 + EPS)
    tt = p.theta + dy - dx * np.floor((p.theta + dy) / dx)
    a = np.where(tt > dx * 0.5, p.theta - dx * 0.5, p.theta + dx * 0.5)
    return p.w * p.r * np.sin(a), p.w * p.r * np.cos(a)


@variation("rings2", {"val": 0.0}, z=PASS)
def _rings2(p: Point):
    dx = p.p("rings2_val") ** 2 + EPS
    rr = p.r + (-2.0 * dx * np.floor((p.r + dx) / (2.0 * dx)) + p.r * (1.0 - dx))
    return p.w * rr * np.sin(p.theta), p.w * rr * np.cos(p.theta)


@variation("eyefish", z=PASS)
def _eyefish(p: Point):
    k = 2.0 * p.w / (p.r + 1.0)
    return k * p.x, k * p.y


@variation("bubble", z="formula")
def _bubble(p: Point):
    rr = p.r2 * 0.25 + 1.0
    return p.w / rr * p.x, p.w / rr * p.y, p.w * (2.0 / rr - 1.0)


@variation("cylinder", z="formula")
def _cylinder(p: Point):
    return p.w * np.sin(p.x), p.w * p.y, p.w * np.cos(p.x)


@variation("perspective", {"angle": 0.0, "dist": 1.0})
def _perspective(p: Point):
    angle, dist = p.p("perspective_angle"), p.p("perspective_dist")
    k = 1.0 / (dist - p.y * np.sin(angle))
    return p.w * dist * k * p.x, p.w * dist * k * p.y * np.cos(angle)


@variation("noise", z=PASS)
def _noise(p: Point):
    a, k = p.rnd() * 2.0 * PI, p.w * p.rnd()
    return k * p.x * np.cos(a), k * p.y * np.sin(a)


@variation("julian", {"power": 1.0, "dist": 1.0}, z=PASS)
def _julian(p: Point):
    power, dist = p.p("julian_power"), p.p("julian_dist")
    n = np.floor(p.rnd() * abs(power))
    a = (p.phi + 2.0 * PI * n) / power
    k = p.w * np.power(p.r2 + EPS, dist / power * 0.5)
    return k * np.cos(a), k * np.sin(a)


@variation("juliascope", {"power": 1.0, "dist": 1.0}, z=PASS)
def _juliascope(p: Point):
    power, dist = p.p("juliascope_power"), p.p("juliascope_dist")
    n = np.floor(p.rnd() * abs(power))
    sign = np.where(np.mod(n, 2.0) == 0.0, 1.0, -1.0)
    a = (sign * p.phi + 2.0 * PI * n) / power
    k = p.w * np.power(p.r2 + EPS, dist / power * 0.5)
    return k * np.cos(a), k * np.sin(a)


@variation("blur", z=PASS)
def _blur(p: Point):
    a, k = p.rnd() * 2.0 * PI, p.w * p.rnd()
    return k * np.cos(a), k * np.sin(a)


def gaussian(p: Point):
    """flam3's cheap Gaussian: the sum of four uniforms, centred."""
    return p.rnd() + p.rnd() + p.rnd() + p.rnd() - 2.0


@variation("gaussian_blur", z=PASS)
def _gaussian_blur(p: Point):
    a, k = p.rnd() * 2.0 * PI, p.w * gaussian(p)
    return k * np.cos(a), k * np.sin(a)


@variation("radial_blur", {"angle": 0.0}, z=PASS)
def _radial_blur(p: Point):
    angle = p.p("radial_blur_angle")
    spin, zoom = np.sin(angle * PI * 0.5), np.cos(angle * PI * 0.5)
    g = p.w * gaussian(p)
    a, rz = p.phi + spin * g, zoom * g - 1.0
    return p.r * np.cos(a) + rz * p.x, p.r * np.sin(a) + rz * p.y


@variation("pie", {"slices": 6.0, "rotation": 0.0, "thickness": 0.5})
def _pie(p: Point):
    slices, rotation, thickness = p.p("pie_slices"), p.p("pie_rotation"), p.p("pie_thickness")
    sl = np.floor(p.rnd() * slices + 0.5)
    a = rotation + 2.0 * PI * (sl + p.rnd() * thickness) / slices
    k = p.w * p.rnd()
    return k * np.cos(a), k * np.sin(a)


@variation("ngon", {"sides": 5.0, "power": 3.0, "circle": 1.0, "corners": 2.0}, z=PASS)
def _ngon(p: Point):
    sides, power, circle, corners = p.p("ngon_sides"), p.p("ngon_power"), p.p("ngon_circle"), p.p("ngon_corners")
    rf = np.power(p.r2 + EPS, power * 0.5)
    b = 2.0 * PI / sides
    ph = p.phi - b * np.floor(p.phi / b)
    ph = np.where(ph > b * 0.5, ph - b, ph)
    k = p.w * (corners * (1.0 / (np.cos(ph) + EPS) - 1.0) + circle) / (rf + EPS)
    return k * p.x, k * p.y


@variation("curl", {"c1": 0.0, "c2": 0.0}, z=PASS)
def _curl(p: Point):
    c1, c2 = p.p("curl_c1"), p.p("curl_c2")
    re = 1.0 + c1 * p.x + c2 * (p.x * p.x - p.y * p.y)
    im = c1 * p.y + 2.0 * c2 * p.x * p.y
    k = p.w / (re * re + im * im + EPS)
    return k * (p.x * re + p.y * im), k * (p.y * re - p.x * im)


@variation("rectangles", {"x": 1.0, "y": 1.0}, z=PASS)
def _rectangles(p: Point):
    rx, ry = p.p("rectangles_x"), p.p("rectangles_y")
    nx = p.x if rx == 0 else (2.0 * np.floor(p.x / rx) + 1.0) * rx - p.x
    ny = p.y if ry == 0 else (2.0 * np.floor(p.y / ry) + 1.0) * ry - p.y
    return p.w * nx, p.w * ny


@variation("arch")
def _arch(p: Point):
    a = p.rnd() * PI * p.w
    sa, ca = np.sin(a), np.cos(a)
    return p.w * sa, p.w * sa * sa / (ca + EPS)


@variation("tangent")
def _tangent(p: Point):
    return p.w * np.sin(p.x) / (np.cos(p.y) + EPS), p.w * np.tan(p.y)


@variation("square")
def _square(p: Point):
    return p.w * (p.rnd() - 0.5), p.w * (p.rnd() - 0.5)


@variation("rays")
def _rays(p: Point):
    a = p.w * p.rnd() * PI
    tr = p.w * np.tan(a) * p.w / (p.r2 + EPS)
    return tr * np.cos(p.x), tr * np.sin(p.y)


@variation("blade")
def _blade(p: Point):
    a = p.rnd() * p.w * p.r
    sa, ca = np.sin(a), np.cos(a)
    return p.w * p.x * (ca + sa), p.w * p.x * (ca - sa)


@variation("secant2")
def _secant2(p: Point):
    cr = np.cos(p.w * p.r)
    icr = 1.0 / (cr + EPS)
    return p.w * p.x, p.w * np.where(cr < 0, icr + 1.0, icr - 1.0)


@variation("cross", z=PASS)
def _cross(p: Point):
    ss = p.x * p.x - p.y * p.y
    k = p.w * np.sqrt(1.0 / (ss * ss + EPS))
    return k * p.x, k * p.y
