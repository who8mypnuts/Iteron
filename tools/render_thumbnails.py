# SPDX-License-Identifier: MIT
"""Render every formula's default as a transparent thumbnail into iteron/thumbnails/ — the add-on's gallery, and the
README's (tools/compose_gallery.py). Re-run after adding a formula or changing a default.

    blender -b --factory-startup --python tools/render_thumbnails.py -- [resolution] [pixels] [formula ids…]
    (or `python tools/render_thumbnails.py …` with the `bpy` module)
"""

import sys

import bpy

from render_common import ROOT, build_default, frame, setup_scene

OUT = ROOT / "iteron" / "thumbnails"


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    resolution = int(args[0]) if args else 160
    pixels = int(args[1]) if len(args) > 1 else 256
    import iteron
    iteron.register()
    from iteron.core.formula import REGISTRY
    only = args[2:] or list(REGISTRY)
    scene, camera = setup_scene(pixels)
    OUT.mkdir(parents=True, exist_ok=True)
    for fid in only:
        obj = build_default(fid, resolution)
        frame(camera, obj)
        scene.render.filepath = str(OUT / f"{fid}.png")
        bpy.ops.render.render(write_still=True)
        print(f"{fid}: {obj.iteron.built_faces:,} faces on the {obj.iteron.built_device}", flush=True)


if __name__ == "__main__":
    main()
