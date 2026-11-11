# SPDX-License-Identifier: MIT
"""Holons: instances of a mesh placed along a flame, turned and scaled by the orbit's accumulated frames.

Ported from Fractalchemy's `solid/holon.py` (Stan Ragets, MIT), on Iteron's chaos game. Every transform maps a
neighbourhood of a point somewhere else, turning and squashing it; the local Jacobian (central differences — exact
for affine transforms, sensible for the variations) says how, and its polar decomposition gives a rotation and a
uniform scale. Composing them along the orbit gives each orbit point a frame, and an instance placed with that frame
sits in the fractal the way a Xenodream holon does. Points come from the chaos game (`chaos_instances`: each frame
the product of the last `depth` Jacobians) or from the tree of every composition to `depth` (`tree_instances`).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .chaos import CompiledFlame, CompiledXForm, _select, apply_xform
from .model import Flame

EPSILON = 1e-4
MIN_SCALE, MAX_SCALE = 1e-9, 1e9
FUSE, POPULATION = 20, 8192


@dataclass
class InstanceSet:
    positions: np.ndarray      # (N, 3)
    rotations: np.ndarray      # (N, 3, 3): columns are the instance's axes
    scales: np.ndarray         # (N,) uniform scale accumulated along the orbit
    colour: np.ndarray         # (N,) palette position 0…1
    xform: np.ndarray          # (N,) int16: the transform that made the point

    def __len__(self) -> int:
        return int(self.positions.shape[0])

    @classmethod
    def empty(cls) -> "InstanceSet":
        return cls(np.zeros((0, 3)), np.zeros((0, 3, 3)), np.zeros(0), np.zeros(0), np.zeros(0, np.int16))

    def subset(self, mask) -> "InstanceSet":
        return InstanceSet(self.positions[mask], self.rotations[mask], self.scales[mask], self.colour[mask],
                           self.xform[mask])

    def sized(self, size: float, falloff: float = 1.0, min_size: float = 0.0, cap: int = 0) -> "InstanceSet":
        """Scales `size · s^falloff`; instances under `min_size` dropped; the `cap` largest kept."""
        out = InstanceSet(self.positions, self.rotations,
                          size * np.power(np.maximum(self.scales, MIN_SCALE), falloff), self.colour, self.xform)
        if min_size > 0:
            out = out.subset(out.scales >= min_size)
        if cap > 0 and len(out) > cap:
            out = out.subset(np.sort(np.argsort(-out.scales, kind="stable")[:cap]))
        return out


def polar_decompose(m: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """`(rotation (N, 3, 3) with det +1, uniform scale ∛|det| (N,))` of `(N, 3, 3)` matrices, by SVD."""
    m = np.asarray(m, dtype=np.float64)
    finite = np.isfinite(m).all(axis=(1, 2))
    u, sigma, vt = np.linalg.svd(np.where(finite[:, None, None], m, np.eye(3)))
    flip = np.linalg.det(u @ vt) < 0
    u[flip, :, 2] *= -1
    scale = np.cbrt(np.abs(np.prod(sigma, axis=1)))
    return u @ vt, np.clip(np.where(finite, scale, 1.0), MIN_SCALE, MAX_SCALE)


def apply_with_jacobian(xform: CompiledXForm, x, y, z, c, rng: np.random.Generator, eps: float = EPSILON):
    """`apply_xform` plus the local Jacobian `(N, 3, 3)` (column j = ∂T/∂x_j), with one random stream for all
    evaluations so random variations don't swamp the differences."""
    seed = int(rng.integers(0, 2 ** 31 - 1))
    base = apply_xform(xform, x, y, z, c, np.random.default_rng(seed))
    jacobian = np.zeros((x.shape[0], 3, 3))
    for j, (dx, dy, dz) in enumerate(((eps, 0.0, 0.0), (0.0, eps, 0.0), (0.0, 0.0, eps))):
        plus = apply_xform(xform, x + dx, y + dy, z + dz, c, np.random.default_rng(seed))
        minus = apply_xform(xform, x - dx, y - dy, z - dz, c, np.random.default_rng(seed))
        for i in range(3):
            jacobian[:, i, j] = (plus[i] - minus[i]) / (2.0 * eps)
    return (*base, jacobian)


def _compose(rotation, scale, jacobian, frames: str):
    turn, stretch = polar_decompose(jacobian)
    return (turn @ rotation if frames == "JACOBIAN" else rotation), np.clip(scale * stretch, MIN_SCALE, MAX_SCALE)


def _final(compiled: CompiledFlame, x, y, z, c, rotation, scale, rng, frames: str):
    if compiled.final is None:
        return x, y, z, c, rotation, scale
    x, y, z, c, jacobian = apply_with_jacobian(compiled.final, x, y, z, c, rng)
    rotation, scale = _compose(rotation, scale, jacobian, frames)
    return x, y, z, c, rotation, scale


def chaos_instances(flame: Flame, count: int, depth: int = 6, seed: int = 1, frames: str = "JACOBIAN") -> InstanceSet:
    """Orbit samples, each with the frame of its last `depth` transforms (the sizes of depth-`depth` holons)."""
    compiled = CompiledFlame.build(flame)
    rng = np.random.default_rng(seed * 7919 + 13)
    n = max(16, min(POPULATION, int(count)))
    x, y, z, c = rng.uniform(-1, 1, n), rng.uniform(-1, 1, n), np.zeros(n), rng.random(n)
    previous = np.zeros(n, dtype=np.int64)
    parts, collected = [], 0

    def step(x, y, z, c, previous, rotation=None, scale=None):
        chosen = _select(compiled.selection, previous, rng.random(n))
        for index, xform in enumerate(compiled.xforms):
            sel = np.nonzero(chosen == index)[0]
            if not sel.size:
                continue
            if rotation is None:
                x[sel], y[sel], z[sel], c[sel] = apply_xform(xform, x[sel], y[sel], z[sel], c[sel], rng)
            else:
                x[sel], y[sel], z[sel], c[sel], jacobian = apply_with_jacobian(xform, x[sel], y[sel], z[sel], c[sel], rng)
                rotation[sel], scale[sel] = _compose(rotation[sel], scale[sel], jacobian, frames)
        bad = ~((np.abs(x) < 1e10) & (np.abs(y) < 1e10) & (np.abs(z) < 1e10))
        if bad.any():
            k = int(bad.sum())
            x[bad], y[bad], z[bad], c[bad] = rng.uniform(-1, 1, k), rng.uniform(-1, 1, k), 0.0, rng.random(k)
            if rotation is not None:
                rotation[bad], scale[bad] = np.eye(3), 1.0
        return chosen

    for _ in range(FUSE):
        previous = step(x, y, z, c, previous)
    while collected < count:
        rotation, scale = np.tile(np.eye(3), (n, 1, 1)), np.ones(n)
        for _ in range(max(1, int(depth))):
            previous = step(x, y, z, c, previous, rotation, scale)
        fx, fy, fz, fc, frot, fscale = _final(compiled, x.copy(), y.copy(), z.copy(), c.copy(), rotation, scale, rng,
                                              frames)
        keep = np.isfinite(fx) & np.isfinite(fy) & np.isfinite(fz)
        parts.append(InstanceSet(np.stack([fx, fy, fz], axis=1)[keep], frot[keep], fscale[keep],
                                 np.clip(fc[keep], 0.0, 1.0), previous[keep].astype(np.int16)))
        collected += int(keep.sum())
    out = _concat(parts)
    return out.subset(np.arange(min(len(out), int(count))))


def tree_instances(flame: Flame, depth: int = 4, leaves_only: bool = False, frames: str = "JACOBIAN",
                   cap: int = 200_000, seed: int = 1) -> InstanceSet:
    """Every composition of the transforms to `depth`, applied to the origin with frames composed on the way (the
    whole tree, or only its deepest level); a level larger than `cap` is sampled."""
    compiled = CompiledFlame.build(flame)
    rng = np.random.default_rng(seed)
    x, y, z, c = np.zeros(1), np.zeros(1), np.zeros(1), np.full(1, 0.5)
    rotation, scale = np.eye(3)[None], np.ones(1)
    collected = []
    for level in range(1, max(1, int(depth)) + 1):
        parts = [(index, *apply_with_jacobian(xform, x, y, z, c, rng)) for index, xform in enumerate(compiled.xforms)
                 if xform.opacity > 0]
        x, y, z, c = (np.concatenate([p[k] for p in parts]) for k in (1, 2, 3, 4))
        turns = [_compose(rotation, scale, p[5], frames) for p in parts]
        rotation, scale = np.concatenate([t[0] for t in turns]), np.concatenate([t[1] for t in turns])
        xform = np.concatenate([np.full(len(p[1]), p[0], dtype=np.int16) for p in parts])
        ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
        if x.shape[0] > cap:
            ok &= np.isin(np.arange(x.shape[0]), rng.choice(x.shape[0], cap, replace=False))
        x, y, z, c, rotation, scale, xform = x[ok], y[ok], z[ok], c[ok], rotation[ok], scale[ok], xform[ok]
        if not leaves_only or level == depth:
            fx, fy, fz, fc, frot, fscale = _final(compiled, x, y, z, c, rotation, scale, rng, frames)
            collected.append(InstanceSet(np.stack([fx, fy, fz], axis=1), frot, fscale, np.clip(fc, 0.0, 1.0), xform))
    return _concat(collected)


def _concat(parts: list[InstanceSet]) -> InstanceSet:
    if not parts:
        return InstanceSet.empty()
    return InstanceSet(*(np.concatenate([getattr(p, f) for p in parts])
                         for f in ("positions", "rotations", "scales", "colour", "xform")))


def euler_xyz(rotations: np.ndarray) -> np.ndarray:
    """`(N, 3)` XYZ Euler angles (Blender's default order: R = Rz · Ry · Rx) of `(N, 3, 3)` rotations."""
    r = np.asarray(rotations, dtype=np.float64)
    sy = -np.clip(r[:, 2, 0], -1.0, 1.0)
    y = np.arcsin(sy)
    regular = np.abs(sy) < 0.999999
    x = np.where(regular, np.arctan2(r[:, 2, 1], r[:, 2, 2]), np.arctan2(-r[:, 1, 2], r[:, 1, 1]))
    z = np.where(regular, np.arctan2(r[:, 1, 0], r[:, 0, 0]), 0.0)
    return np.stack([x, y, z], axis=1)
