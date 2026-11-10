# SPDX-License-Identifier: MIT
"""Render the README's showcase of the later phases — the bundled flames as points, a few fragments from
Fractalchemy's collection (when the sample sources are there) and hybrids — into docs/images/showcase.png.

    blender -b --factory-startup --python tools/render_showcase.py      (or `python tools/render_showcase.py` with bpy)
"""

import sys

import bpy
from PIL import Image, ImageDraw

from render_common import ROOT, frame, setup_scene
from compose_gallery import CAPTION, INK, NIGHT, font

OUT = ROOT / "docs" / "images" / "showcase.png"
CELL, COLUMNS = 256, 4
FRAGMENTS = ROOT / "sample_source" / "Fractalchemy" / "fractalchemy" / "fragments" / "library" / "Examples" / \
    "Fractalchemy Collection"


def clear() -> None:
    for obj in [o for o in bpy.data.objects if o.type == "MESH"]:
        bpy.data.objects.remove(obj)


def flame(key: str):
    from iteron.jobs.scheduler import SCHEDULER
    clear()
    bpy.ops.iteron.add_flame(flame=key)
    obj = bpy.context.active_object
    obj.iteron.flame.points = 500_000
    SCHEDULER.run_now(obj, final=True)
    obj.iteron.flame.point_radius = 0.004 * max(obj.dimensions)
    return obj, obj.iteron.flame.flame_dict().get("name", key)


def fragment(name: str):
    from iteron.jobs.scheduler import SCHEDULER
    from iteron.ops.fragments import import_fragment
    clear()
    obj = import_fragment(bpy.context, FRAGMENTS / f"{name}.frag", camera=False)
    obj.iteron.final_resolution = 200
    SCHEDULER.run_now(obj, final=True)
    return obj, name.removeprefix("3D - ") + " (.frag)"


def hybrid(preset: str):
    from iteron.jobs.scheduler import SCHEDULER
    clear()
    bpy.ops.iteron.add_fractal(formula="hybrid")
    obj = bpy.context.active_object
    bpy.ops.iteron.apply_preset(preset=preset)
    obj.iteron.final_resolution = 200
    SCHEDULER.run_now(obj, final=True)
    return obj, f"Hybrid: {preset}"


def main() -> int:
    import iteron
    iteron.register()
    from iteron.flames.library import bundled
    scene, camera = setup_scene(CELL)
    jobs = [(flame, key) for key in bundled()]
    if FRAGMENTS.is_dir():
        jobs += [(fragment, n) for n in ("3D - Juliabulb", "3D - Koch Tetrahedron", "3D - Indra's Pearls",
                                         "3D - Dragon Ribbon")]
    jobs += [(hybrid, p) for p in ("Bulb + Menger", "Int Pow + Box", "Lambda + Box", "Bulb + Octahedral")]
    rows = -(-len(jobs) // COLUMNS)
    sheet = Image.new("RGB", (COLUMNS * CELL, rows * (CELL + CAPTION)), NIGHT)
    draw = ImageDraw.Draw(sheet)
    for index, (make, arg) in enumerate(jobs):
        obj, caption = make(arg)
        frame(camera, obj)
        path = ROOT / "docs" / "images" / "_tile.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        x, y = (index % COLUMNS) * CELL, (index // COLUMNS) * (CELL + CAPTION)
        tile = Image.open(path).convert("RGBA")
        sheet.paste(tile, (x, y), tile)
        width = draw.textlength(caption, font=font(15))
        draw.text((x + (CELL - width) / 2, y + CELL + 4), caption, fill=INK, font=font(15))
        path.unlink()
        print(f"{caption}: {len(obj.data.vertices):,} vertices", flush=True)
    sheet.save(OUT)
    print(OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
