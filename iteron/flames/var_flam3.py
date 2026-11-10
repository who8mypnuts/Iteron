# SPDX-License-Identifier: MIT
"""More of flam3's built-in variations and Apophysis 7X's complex functions (numpy), written for Iteron from their
published formulas (flam3's variation list; the Apophysis documentation), for `.flame` files that use them.
`tests/core/test_variation_parity.py` checks each against Fractalchemy's implementation where it has one."""

from __future__ import annotations

import numpy as np

from .variations import EPS, PASS, PI, Point, variation


@variation("butterfly")
def _butterfly(p: Point):
    y2 = 2.0 * p.y
    r = p.w * 1.3029400317411197 * np.sqrt(np.abs(p.x * p.y) / (EPS + p.x * p.x + y2 * y2))
    return r * p.x, r * y2


@variation("polar2", z=PASS)
def _polar2(p: Point):
    k = p.w / PI
    return k * p.theta, k * 0.5 * np.log(p.r2)


@variation("modulus", {"x": 1.0, "y": 1.0})
def _modulus(p: Point):
    def wrap(v, m):
        return np.where(v > m, -m + np.fmod(v + m, 2.0 * m), np.where(v < -m, m - np.fmod(m - v, 2.0 * m), v))
    return p.w * wrap(p.x, p.p("modulus_x")), p.w * wrap(p.y, p.p("modulus_y"))


@variation("separation", {"x": 1.0, "xinside": 0.0, "y": 1.0, "yinside": 0.0}, z=PASS)
def _separation(p: Point):
    def part(v, s, inside):
        root = np.sqrt(v * v + s * s)
        return np.where(v > 0, root - v * inside, -(root + v * inside))
    return (p.w * part(p.x, p.p("separation_x"), p.p("separation_xinside")),
            p.w * part(p.y, p.p("separation_y"), p.p("separation_yinside")))


@variation("waves2", {"freqx": 2.0, "scalex": 1.0, "freqy": 2.0, "scaley": 1.0, "freqz": 0.0, "scalez": 0.0})
def _waves2(p: Point):
    """Apophysis 7X's waves2, with its depth wave."""
    return (p.w * (p.x + p.p("waves2_scalex") * np.sin(p.y * p.p("waves2_freqx"))),
            p.w * (p.y + p.p("waves2_scaley") * np.sin(p.x * p.p("waves2_freqy"))),
            p.w * (p.z + p.p("waves2_scalez") * np.sin(p.r * p.p("waves2_freqz"))))


@variation("whorl", {"inside": 1.0, "outside": 1.0})
def _whorl(p: Point):
    twist = np.where(p.r < p.w, p.p("whorl_inside"), p.p("whorl_outside"))
    a = p.phi + twist / (p.w - p.r)
    return p.w * p.r * np.cos(a), p.w * p.r * np.sin(a)


@variation("escher", {"beta": 0.0}, z=PASS)
def _escher(p: Point):
    beta = p.p("escher_beta")
    lnr = 0.5 * np.log(p.r2)
    vc, vd = 0.5 * (1.0 + np.cos(beta)), 0.5 * np.sin(beta)
    m, n = p.w * np.exp(vc * lnr - vd * p.phi), vc * p.phi + vd * lnr
    return m * np.cos(n), m * np.sin(n)


@variation("foci", z=PASS)
def _foci(p: Point):
    expx = np.exp(p.x) * 0.5
    expnx = 0.25 / expx
    k = p.w / (expx + expnx - np.cos(p.y))
    return k * (expx - expnx), k * np.sin(p.y)


@variation("loonie", z=PASS)
def _loonie(p: Point):
    w2 = p.w * p.w
    inside = p.r2 < w2
    k = np.where(inside, p.w * np.sqrt(np.maximum(w2 / np.where(inside, p.r2, 1.0) - 1.0, 0.0)), p.w)
    return k * p.x, k * p.y


@variation("scry", z=PASS)
def _scry(p: Point):
    k = 1.0 / (p.r * (p.r2 + 1.0 / (p.w + EPS)))
    return k * p.x, k * p.y


@variation("curve", {"xamp": 0.0, "yamp": 0.0, "xlength": 1.0, "ylength": 1.0})
def _curve(p: Point):
    xl, yl = max(p.p("curve_xlength") ** 2, 1e-20), max(p.p("curve_ylength") ** 2, 1e-20)
    return (p.w * (p.x + p.p("curve_xamp") * np.exp(-p.y * p.y / xl)),
            p.w * (p.y + p.p("curve_yamp") * np.exp(-p.x * p.x / yl)))


@variation("edisc")
def _edisc(p: Point):
    tmp, tmp2 = p.r2 + 1.0, 2.0 * p.x
    xmax = (np.sqrt(tmp + tmp2) + np.sqrt(tmp - tmp2)) * 0.5
    a1 = np.log(xmax + np.sqrt(np.maximum(xmax - 1.0, 0.0)))
    a2 = -np.arccos(np.clip(p.x / xmax, -1.0, 1.0))
    w = p.w / 11.57034632
    snv = np.where(p.y > 0, -np.sin(a1), np.sin(a1))
    return w * np.cosh(a2) * np.cos(a1), w * np.sinh(a2) * snv


@variation("flux", {"spread": 0.0})
def _flux(p: Point):
    """(The plugin passes depth through unweighted.)"""
    xpw, xmw = p.x + p.w, p.x - p.w
    avgr = p.w * (2.0 + p.p("flux_spread")) * np.sqrt(np.sqrt(p.y * p.y + xpw * xpw) / np.sqrt(p.y * p.y + xmw * xmw))
    avga = (np.arctan2(p.y, xmw) - np.arctan2(p.y, xpw)) * 0.5
    return avgr * np.cos(avga), avgr * np.sin(avga), p.z


@variation("cell", {"size": 1.0})
def _cell(p: Point):
    size = p.p("cell_size")
    x, y = np.floor(p.x / size), np.floor(p.y / size)
    dx, dy = p.x - x * size, p.y - y * size
    x = np.where(x >= 0, 2.0 * x, -(2.0 * x + 1.0))
    y = np.where(y >= 0, 2.0 * y, -(2.0 * y + 1.0))
    return p.w * (dx + x * size), -p.w * (dy + y * size)


@variation("oscilloscope", {"separation": 1.0, "frequency": PI, "amplitude": 1.0, "damping": 0.0}, prefix="oscope")
def _oscilloscope(p: Point):
    tpf = 2.0 * PI * p.p("oscope_frequency")
    amp, damp = p.p("oscope_amplitude"), p.p("oscope_damping")
    t = (amp * np.exp(-np.abs(p.x) * damp) if damp else amp) * np.cos(tpf * p.x) + p.p("oscope_separation")
    return p.w * p.x, np.where(np.abs(p.y) <= t, -p.w * p.y, p.w * p.y)


@variation("bent2", {"x": 1.0, "y": 1.0})
def _bent2(p: Point):
    return (p.w * np.where(p.x < 0, p.x * p.p("bent2_x"), p.x), p.w * np.where(p.y < 0, p.y * p.p("bent2_y"), p.y))


@variation("auger", {"freq": 1.0, "weight": 0.5, "sym": 0.0, "scale": 1.0}, z=PASS)
def _auger(p: Point):
    freq, strength, scale = p.p("auger_freq"), p.p("auger_weight"), p.p("auger_scale")
    s, t = np.sin(freq * p.x), np.sin(freq * p.y)
    dy = p.y + strength * (scale * s / 2.0 + np.abs(p.y) * s)
    dx = p.x + strength * (scale * t / 2.0 + np.abs(p.x) * t)
    return p.w * (p.x + p.p("auger_sym") * (dx - p.x)), p.w * dy


# --- Apophysis 7X's complex functions -------------------------------------------------------------------------------
@variation("exp")
def _exp(p: Point):
    e = p.w * np.exp(p.x)
    return e * np.cos(p.y), e * np.sin(p.y)


@variation("log", {"base": np.e}, z=PASS)
def _log(p: Point):
    base = p.p("log_base")
    scale = 0.5 / np.log(base) if abs(base - 1.0) > 1e-6 and base > 1e-6 else 0.5
    return p.w * scale * np.log(p.r2 + 1e-6), p.w * p.phi


@variation("sin")
def _sin(p: Point):
    return p.w * np.sin(p.x) * np.cosh(p.y), p.w * np.cos(p.x) * np.sinh(p.y)


@variation("cos")
def _cos(p: Point):
    return p.w * np.cos(p.x) * np.cosh(p.y), -p.w * np.sin(p.x) * np.sinh(p.y)


@variation("sinh")
def _sinh(p: Point):
    """The plugin's: sinh(z · π/4)."""
    a, b = p.x * PI / 4.0, p.y * PI / 4.0
    return p.w * np.sinh(a) * np.cos(b), p.w * np.cosh(a) * np.sin(b)


@variation("cosh")
def _cosh(p: Point):
    return p.w * np.cosh(p.x) * np.cos(p.y), p.w * np.sinh(p.x) * np.sin(p.y)


@variation("tan")
def _tan(p: Point):
    den = p.w / (np.cos(2.0 * p.x) + np.cosh(2.0 * p.y) + EPS)
    return den * np.sin(2.0 * p.x), den * np.sinh(2.0 * p.y)


@variation("tanh")
def _tanh(p: Point):
    """The plugin's: tanh(z · π/4)."""
    a, b = p.x * PI / 2.0, p.y * PI / 2.0
    den = p.w / (np.cosh(a) + np.cos(b))
    return den * np.sinh(a), den * np.sin(b)
