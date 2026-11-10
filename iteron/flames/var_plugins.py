# SPDX-License-Identifier: MIT
"""Popular Apophysis plugin variations (numpy). Ported from Fractalchemy's natively written
`formulas/builtin/flam3.py` (Stan Ragets, MIT); the formulas are the plugins' published ones."""

from __future__ import annotations

import numpy as np

from .variations import EPS, PASS, PI, Point, variation


@variation("elliptic", z=PASS)
def _elliptic(p: Point):
    tmp, x2 = p.r2 + 1.0, 2.0 * p.x
    xmax = 0.5 * (np.sqrt(tmp + x2) + np.sqrt(tmp - x2))
    a = p.x / xmax
    b = np.sqrt(np.maximum(1.0 - a * a, 0.0))
    ssx = np.sqrt(np.maximum(xmax - 1.0, 0.0))
    wp = p.w / (PI * 0.5)
    return wp * np.arctan2(a, b), np.where(p.y > 0, 1.0, -1.0) * wp * np.log(xmax + ssx)


@variation("splits", {"x": 0.0, "y": 0.0}, z=PASS)
def _splits(p: Point):
    sx, sy = p.p("splits_x"), p.p("splits_y")
    return p.w * np.where(p.x >= 0, p.x + sx, p.x - sx), p.w * np.where(p.y >= 0, p.y + sy, p.y - sy)


@variation("bipolar", {"shift": 0.0}, z=PASS)
def _bipolar(p: Point):
    tt, x2, ps = p.r2 + 1.0, 2.0 * p.x, -PI * 0.5 * p.p("bipolar_shift")
    yy = 0.5 * np.arctan2(2.0 * p.y, p.r2 - 1.0) + ps
    yy = np.where(yy > PI * 0.5, -PI * 0.5 + np.mod(yy + PI * 0.5, PI), yy)
    yy = np.where(yy < -PI * 0.5, PI * 0.5 - np.mod(PI * 0.5 - yy, PI), yy)
    f, g = tt + x2, tt - x2
    safe_g = np.where(g == 0, 1.0, g)
    ok = (g != 0) & (f / safe_g > 0)
    lx = np.where(ok, 0.25 * np.log(np.where(ok, f / safe_g, 1.0)), 0.0)
    return p.w * (2.0 / PI) * lx, np.where(ok, p.w * (2.0 / PI) * yy, 0.0)


@variation("hemisphere", z=PASS)
def _hemisphere(p: Point):
    k = p.w / np.sqrt(p.r2 + 1.0)
    return k * p.x, k * p.y


@variation("lazysusan", {"spin": 0.0, "space": 0.0, "twist": 0.0, "x": 0.0, "y": 0.0}, z=PASS)
def _lazysusan(p: Point):
    spin, space, twist = p.p("lazysusan_spin"), p.p("lazysusan_space"), p.p("lazysusan_twist")
    lx, ly = p.p("lazysusan_x"), p.p("lazysusan_y")
    xx, yy = p.x - lx, p.y + ly
    rr = np.sqrt(xx * xx + yy * yy)
    inside = rr < p.w
    a = np.arctan2(yy, xx) + spin + twist * (p.w - rr)
    outer = p.w * (1.0 + space / (rr + EPS))
    return (np.where(inside, p.w * (rr * np.cos(a) + lx), outer * (xx + lx)),
            np.where(inside, p.w * (rr * np.sin(a) - ly), outer * (yy - ly)))


@variation("mobius", {"Re_A": 1.0, "Im_A": 0.0, "Re_B": 0.0, "Im_B": 0.0, "Re_C": 0.0, "Im_C": 0.0, "Re_D": 1.0,
                      "Im_D": 0.0}, z=PASS)
def _mobius(p: Point):
    ra, ia, rb, ib = p.p("mobius_Re_A"), p.p("mobius_Im_A"), p.p("mobius_Re_B"), p.p("mobius_Im_B")
    rc, ic, rd, id_ = p.p("mobius_Re_C"), p.p("mobius_Im_C"), p.p("mobius_Re_D"), p.p("mobius_Im_D")
    re_u, im_u = ra * p.x - ia * p.y + rb, ra * p.y + ia * p.x + ib
    re_v, im_v = rc * p.x - ic * p.y + rd, rc * p.y + ic * p.x + id_
    k = p.w / (re_v * re_v + im_v * im_v + EPS)
    return k * (re_u * re_v + im_u * im_v), k * (im_u * re_v - re_u * im_v)


@variation("polynomial", {"powx": 1.0, "powy": 1.0, "lcx": 0.0, "lcy": 0.0, "scx": 0.0, "scy": 0.0})
def _polynomial(p: Point):
    px, py = p.p("polynomial_powx"), p.p("polynomial_powy")
    lcx, lcy, scx, scy = p.p("polynomial_lcx"), p.p("polynomial_lcy"), p.p("polynomial_scx"), p.p("polynomial_scy")
    return (p.w * (lcx * p.x + scx * np.sign(p.x) * np.power(np.abs(p.x), px)),
            p.w * (lcy * p.y + scy * np.sign(p.y) * np.power(np.abs(p.y), py)))


@variation("wedge", {"angle": 0.0, "hole": 0.0, "count": 1.0, "swirl": 0.0}, z=PASS)
def _wedge(p: Point):
    angle, hole, count, swirl = p.p("wedge_angle"), p.p("wedge_hole"), p.p("wedge_count"), p.p("wedge_swirl")
    a = p.phi + swirl * p.r
    cc = np.floor((count * a + PI) * (1.0 / PI) * 0.5)
    a = a * (1.0 - angle * count * (1.0 / PI) * 0.5) + cc * angle
    k = p.w * (p.r + hole)
    return k * np.cos(a), k * np.sin(a)
