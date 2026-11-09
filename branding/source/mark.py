# SPDX-License-Identifier: MIT
"""The Iteron mark as SVG: the isometric Menger sponge, each face painted with the brand's hue sweep,
lit by orientation and darkened inside the tunnels."""

from __future__ import annotations

from menger import menger_voxels, outline, paint, project, regions, to_screen
from palette import DEPTH_SHADE, FACE_LIGHT, SWEEP, shade

SEAM = 0.02     # a hairline same-colour stroke (in level-2 voxels) so neighbouring regions overlap slightly
EDGE_WIDTH = 0.10       # the light "Y" on the three front edges, as a fraction of a level-2 voxel
EDGE_OPACITY = 0.55


def _bucket(depth: int) -> int:
    return 0 if depth == 0 else (1 if depth <= 2 else 2)


def _bounds(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _gradients(prefix: str, box) -> str:
    """One linear gradient per (orientation, depth bucket), all sweeping the same way across the mark."""
    x0, y0, x1, y1 = box
    x0 = x1 = (x0 + x1) / 2             # vertical sweep: each face of the cube gets its own band of hues
    defs = []
    for name, light in FACE_LIGHT.items():
        for bucket, depth_shade in enumerate(DEPTH_SHADE):
            stops = "".join(f'<stop offset="{offset:.2f}" stop-color="{shade(shade(colour, light), depth_shade)}"/>'
                            for offset, colour in SWEEP)
            defs.append(f'<linearGradient id="{prefix}-{name}-{bucket}" gradientUnits="userSpaceOnUse" '
                        f'x1="{x0:.3f}" y1="{y0:.3f}" x2="{x1:.3f}" y2="{y1:.3f}">{stops}</linearGradient>')
    return "".join(defs)


def mark_group(level: int, prefix: str = "im") -> tuple[str, str, tuple[float, float, float, float]]:
    """(defs, body, bounding box) of the mark in voxel units; the caller places and scales it."""
    size = 3 ** level
    hexagon = outline(size)
    box = _bounds(hexagon)
    scale = size / 9                    # stroke widths are tuned on the level-2 sponge
    # an underlay in the darkest tone, so anti-aliasing at region boundaries never lets the background through
    underlay = "M" + "L".join(f"{x:.3f},{y:.3f}" for x, y in hexagon) + "Z"
    body = [f'<path d="{underlay}" fill="url(#{prefix}-right-2)"/>']
    seen = paint(menger_voxels(level), size)
    for (orientation, bucket), loops in sorted(regions(seen, lambda f: (f[0], _bucket(f[1]))).items()):
        d = "".join("M" + "L".join(f"{x:.3f},{y:.3f}" for x, y in map(to_screen, loop)) + "Z" for loop in loops)
        paint_url = f"url(#{prefix}-{orientation}-{bucket})"
        body.append(f'<path d="{d}" fill="{paint_url}" stroke="{paint_url}" fill-rule="evenodd"/>')
    group = (f'<g stroke-width="{SEAM * scale:.3f}" stroke-linejoin="round">' + "".join(body) + "</g>" + _edges(size, scale))
    return _gradients(prefix, box), group, box


def _edges(size: int, scale: float) -> str:
    """A soft highlight on the three edges that meet at the front corner (a Menger sponge's edges are always solid)."""
    corner = project(size, size, size)
    ends = [project(size, 0, size), project(0, size, size), project(size, size, 0)]
    d = "".join(f"M{corner[0]:.3f},{corner[1]:.3f}L{x:.3f},{y:.3f}" for x, y in ends)
    return (f'<path d="{d}" fill="none" stroke="#FFFFFF" stroke-opacity="{EDGE_OPACITY}" '
            f'stroke-width="{EDGE_WIDTH * scale:.3f}" stroke-linecap="round"/>')


def mark_svg(level: int, pixels: int = 512, padding: float = 0.04) -> str:
    """A square, transparent SVG of the mark alone."""
    defs, body, (x0, y0, x1, y1) = mark_group(level)
    side = max(x1 - x0, y1 - y0) * (1 + 2 * padding)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    view = f"{cx - side / 2:.3f} {cy - side / 2:.3f} {side:.3f} {side:.3f}"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{pixels}" height="{pixels}" viewBox="{view}">'
            f"<title>Iteron</title><defs>{defs}</defs>{body}</svg>\n")
