# SPDX-License-Identifier: MIT
"""A fragment's textures on the GPU: Blender images (packed into the `.blend`, Non-Color so their values are raw)
uploaded as float textures, cached per image and size (an edited or reloaded image is uploaded again). The pixels
are read through `Image.pixels` rather than `gpu.texture.from_image`, so the values a fragment sees are exactly the
image's, the same as in the command line's moderngl path."""

from __future__ import annotations

import gpu
import numpy as np

from .shaders import float_buffer

_CACHE: dict[tuple, object] = {}


def gpu_textures(images: dict) -> dict:
    """`{sampler name: GPUTexture}` for `{sampler name: bpy.types.Image}` (images that are None are left out)."""
    out = {}
    for name, image in images.items():
        if image is None:
            continue
        width, height = image.size
        key = (image.name, width, height, image.filepath_raw, bool(image.packed_file), image.is_dirty)
        if key not in _CACHE:
            if len(_CACHE) > 64:
                _CACHE.clear()
            pixels = np.empty(width * height * 4, dtype=np.float32)
            image.pixels.foreach_get(pixels)
            _CACHE[key] = gpu.types.GPUTexture((width, height), format="RGBA32F", data=float_buffer(pixels))
        out[name] = _CACHE[key]
    return out


def clear_cache() -> None:
    _CACHE.clear()
