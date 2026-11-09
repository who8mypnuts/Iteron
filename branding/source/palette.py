# SPDX-License-Identifier: MIT
"""The Iteron palette — the one place brand colours are defined."""

# The mark's hue sweep, from its top point to its bottom point (position 0..1, hex colour).
SWEEP = ((0.00, "#1FF0FF"), (0.30, "#2F9BFF"), (0.55, "#6A4DFF"), (0.80, "#B23CFF"), (1.00, "#FF3F93"))

# Lightness of each face orientation (1 = the sweep colour as is): light from the upper left.
FACE_LIGHT = {"top": 1.06, "left": 0.80, "right": 0.54}

# Extra darkening for faces inside the sponge's tunnels, by depth bucket (0 = outer surface).
DEPTH_SHADE = (1.00, 0.62, 0.40)

INK_DARK = "#0E1020"      # wordmark on light backgrounds
INK_LIGHT = "#F4F6FF"     # wordmark on dark backgrounds
NIGHT = "#0B0C18"         # background of tiles and the social card
NIGHT_GLOW = "#1C1640"    # the soft glow behind the mark on dark tiles
MUTED = "#9AA3C7"         # secondary text on dark


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def rgb_to_hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in rgb)


def shade(colour: str, factor: float) -> str:
    """Brighten (factor > 1, towards white) or darken (factor < 1, towards black) a colour."""
    r, g, b = hex_to_rgb(colour)
    if factor >= 1.0:
        t = factor - 1.0
        return rgb_to_hex((r + (1 - r) * t, g + (1 - g) * t, b + (1 - b) * t))
    return rgb_to_hex((r * factor, g * factor, b * factor))
