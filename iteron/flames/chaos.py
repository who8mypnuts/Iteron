# SPDX-License-Identifier: MIT
"""The chaos game in numpy: a flame's orbit as points (positions, palette positions, the transform that made each).

Ported from Fractalchemy (`render/compiled.py`, `render/cpu_engine.py`, Stan Ragets, MIT): transforms are resolved
once (variations ordered pre → normal → post, xaos turned into a selection table), then a population of points is
iterated in parallel — each step every point takes one transform chosen by weight (and by the previous transform's
xaos row), the final transform is applied to what is plotted, and points that blow up are re-seeded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from .model import IDENTITY, Flame, XForm
from .variations import POST, PRE, Point, Variation, canonical, resolve

RESET_LIMIT = 1e10          # |coordinate| beyond this (or NaN) re-seeds the point
FUSE = 20                   # iterations before anything is kept (the orbit settles onto the attractor)
POPULATION = 1 << 16        # points iterated in parallel


@dataclass(frozen=True)
class CompiledXForm:
    coefs: tuple
    post: tuple
    pre: tuple
    color: float
    color_speed: float
    opacity: float
    pre_blur: float
    variations: tuple[tuple[Variation, float, dict], ...]     # (variation, weight, parameters), in run order

    @classmethod
    def build(cls, xform: XForm, unsupported: set[str]) -> "CompiledXForm":
        active, pre_blur = [], 0.0
        for name, weight in xform.variations.items():
            var = resolve(name)
            if var is None:
                unsupported.add(name)
                continue
            if not weight:
                continue
            if var.name == "pre_blur":
                pre_blur = weight
                continue
            params = {key: _param(xform.params, name, key, default) for key, default in var.params.items()}
            active.append((var, float(weight), params))
        order = {PRE: 0, POST: 2}
        active.sort(key=lambda item: order.get(item[0].kind, 1))
        return cls(tuple(xform.coefs), tuple(xform.post), tuple(xform.pre), xform.color,
                   float(np.clip(xform.color_speed, 0.0, 1.0)), float(np.clip(xform.opacity, 0.0, 1.0)), pre_blur,
                   tuple(active))


def _param(params: dict, name: str, key: str, default: float) -> float:
    """A parameter by its canonical key, or by the alias the file used (`linear3D_…`)."""
    if key in params:
        return params[key]
    alias_key = name + key[len(canonical(name)):]
    return params.get(alias_key, default)


@dataclass(frozen=True)
class CompiledFlame:
    xforms: tuple[CompiledXForm, ...]
    final: CompiledXForm | None
    selection: np.ndarray          # (N, N) cumulative choice probabilities, row = previous transform
    palette: np.ndarray            # (256, 3) float32 in 0…1
    unsupported: tuple[str, ...]

    @classmethod
    def build(cls, flame: Flame) -> "CompiledFlame":
        usable = [x for x in flame.xforms if x.weight > 0]
        if not usable:
            raise ValueError(f"'{flame.name}' has no transform with a positive weight")
        unsupported: set[str] = set()
        xforms = tuple(CompiledXForm.build(x, unsupported) for x in usable)
        final = CompiledXForm.build(flame.final, unsupported) if flame.final is not None else None
        if final is not None and not final.variations:
            final = None        # none of the final transform's variations can run: skip it rather than collapse all
        return cls(xforms, final, selection_table(usable), palette_array(flame.palette), tuple(sorted(unsupported)))


def selection_table(xforms: list[XForm]) -> np.ndarray:
    n = len(xforms)
    weights = np.array([x.weight for x in xforms], dtype=np.float64)
    table = np.empty((n, n))
    for i, x in enumerate(xforms):
        chaos = np.ones(n) if x.chaos is None else np.array((list(x.chaos) + [1.0] * n)[:n], dtype=np.float64)
        row = weights * np.clip(chaos, 0.0, None)
        row = row if row.sum() > 0 else weights
        cumulative = np.cumsum(row / row.sum())
        cumulative[-1] = 1.0
        table[i] = cumulative
    return table


def palette_array(palette) -> np.ndarray:
    colours = np.array(palette if len(palette) >= 2 else [(0, 0, 0), (255, 255, 255)], dtype=np.float32) / 255.0
    if len(colours) != 256:
        index = np.linspace(0, len(colours) - 1, 256)
        colours = np.stack([np.interp(index, np.arange(len(colours)), colours[:, c]) for c in range(3)], axis=1)
    return colours.astype(np.float32)


def apply_xform(xform: CompiledXForm, x, y, z, c, rng: np.random.Generator):
    """Points through one transform, in Apophysis's order: colour blend → pre affine → affine → pre_blur →
    variations (pre, normal, post) → post affine."""
    c = c * (1.0 - xform.color_speed) + xform.color * xform.color_speed
    if xform.pre != IDENTITY:
        a, b, cc, d, e, f = xform.pre
        x, y = a * x + cc * y + e, b * x + d * y + f
    a, b, cc, d, e, f = xform.coefs
    tx, ty, tz = a * x + cc * y + e, b * x + d * y + f, z
    if xform.pre_blur:
        angle = rng.random(x.shape[0]) * 2.0 * np.pi
        k = xform.pre_blur * (rng.random(x.shape[0]) + rng.random(x.shape[0]) + rng.random(x.shape[0])
                              + rng.random(x.shape[0]) - 2.0)
        tx, ty = tx + k * np.cos(angle), ty + k * np.sin(angle)
    vx, vy, vz = np.zeros_like(tx), np.zeros_like(tx), np.zeros_like(tx)
    with np.errstate(all="ignore"):
        for variation, weight, params in xform.variations:
            point = Point(tx, ty, tz, vx, vy, vz, weight, xform.coefs, params, rng)
            tx, ty, tz, vx, vy, vz = variation.apply(point)
    if xform.post != IDENTITY:
        a, b, cc, d, e, f = xform.post
        vx, vy = a * vx + cc * vy + e, b * vx + d * vy + f
    return vx, vy, vz, c


@dataclass
class Orbit:
    points: np.ndarray             # (M, 3) float32
    colour: np.ndarray             # (M,) float32: palette position 0…1
    xform: np.ndarray              # (M,) int16: the transform that made the point
    palette: np.ndarray            # (256, 3) float32
    unsupported: tuple[str, ...]

    @property
    def rgb(self) -> np.ndarray:
        return self.palette[np.clip((self.colour * 255.0 + 0.5).astype(np.int64), 0, 255)]


def chaos_game(flame: Flame, count: int, seed: int = 1, progress: Callable[[float], None] | None = None,
               cancelled: Callable[[], bool] | None = None) -> Orbit | None:
    """About `count` orbit points of `flame` (None when cancelled)."""
    compiled = CompiledFlame.build(flame)
    rng = np.random.default_rng(seed)
    n = max(64, min(POPULATION, count))
    x, y, z = rng.uniform(-1.0, 1.0, n), rng.uniform(-1.0, 1.0, n), np.zeros(n)
    c, previous = rng.random(n), np.zeros(n, dtype=np.int64)
    opacity = np.array([xf.opacity for xf in compiled.xforms])
    kept_points, kept_colour, kept_xform, kept = [], [], [], 0
    step = 0
    while kept < count:
        if cancelled and cancelled():
            return None
        chosen = _select(compiled.selection, previous, rng.random(n))
        for index, xform in enumerate(compiled.xforms):
            sel = np.nonzero(chosen == index)[0]
            if sel.size:
                x[sel], y[sel], z[sel], c[sel] = apply_xform(xform, x[sel], y[sel], z[sel], c[sel], rng)
        bad = ~((np.abs(x) < RESET_LIMIT) & (np.abs(y) < RESET_LIMIT) & (np.abs(z) < RESET_LIMIT))
        if bad.any():
            k = int(bad.sum())
            x[bad], y[bad], z[bad], c[bad] = rng.uniform(-1, 1, k), rng.uniform(-1, 1, k), 0.0, rng.random(k)
        previous = chosen
        step += 1
        if step <= FUSE:
            continue
        px, py, pz, pc = x, y, z, c
        if compiled.final is not None:
            px, py, pz, pc = apply_xform(compiled.final, x, y, z, c, rng)
        keep = (opacity[chosen] > 0) & ~bad & np.isfinite(px) & np.isfinite(py) & np.isfinite(pz)
        keep &= (np.abs(px) < RESET_LIMIT) & (np.abs(py) < RESET_LIMIT) & (np.abs(pz) < RESET_LIMIT)
        kept_points.append(np.stack([px[keep], py[keep], pz[keep]], axis=1).astype(np.float32))
        kept_colour.append(np.clip(pc[keep], 0.0, 1.0).astype(np.float32))
        kept_xform.append(chosen[keep].astype(np.int16))
        kept += int(keep.sum())
        if progress:
            progress(min(kept / count, 1.0))
        if step > FUSE + 50 and kept == 0:
            break                                        # nothing ever lands: a degenerate flame
    points = np.concatenate(kept_points)[:count] if kept_points else np.zeros((0, 3), np.float32)
    colour = np.concatenate(kept_colour)[:count] if kept_colour else np.zeros(0, np.float32)
    xform = np.concatenate(kept_xform)[:count] if kept_xform else np.zeros(0, np.int16)
    return Orbit(points, colour, xform, compiled.palette, compiled.unsupported)


def _select(table: np.ndarray, previous: np.ndarray, r: np.ndarray) -> np.ndarray:
    """The transform each point moves to: the first whose cumulative probability (in the previous one's row) exceeds r."""
    chosen = np.empty_like(previous)
    for row in np.unique(previous):
        sel = previous == row
        chosen[sel] = np.searchsorted(table[row], r[sel], side="right")
    return np.minimum(chosen, table.shape[1] - 1)
