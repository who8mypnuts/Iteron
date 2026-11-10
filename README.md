<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="branding/svg/iteron-logo-on-dark.svg">
    <img src="branding/svg/iteron-logo-on-light.svg" alt="Iteron" height="96">
  </picture>
</p>

<p align="center"><b>3D fractals as real, editable Blender meshes.</b></p>

<p align="center"><img src="docs/images/gallery.png" alt="The eight Phase 1 formulas, rendered in Blender with EEVEE"></p>

Iteron adds Mandelbulbs, Mandelboxes, Menger sponges, kaleidoscopic IFS and quaternion Julia sets to Blender as
ordinary mesh objects. You shape a fractal from one sidebar tab while a preview rebuilds live, then build it at high
resolution. It renders in Cycles and EEVEE, exports with Blender's own exporters (colours included), and takes
modifiers, materials and undo like any other mesh.

## Install

Iteron needs **Blender 4.2 or newer**; it is developed on Blender 5.x.

1. Download `iteron-x.y.z.zip` from the [releases](../../releases).
2. In Blender, open **Edit ▸ Preferences ▸ Get Extensions**, click **▾** (top right) and choose **Install from
   Disk…**, then pick the zip. You can also drag the zip onto Blender.

To build the zip yourself, run `python tools/build.py`; the zip is written to `dist/`.

## Use

* **Add** a fractal with **Shift+A ▸ Iteron Fractal ▸** *Mandelbulb*, *Mandelbox*, … The fractal appears at the 3D
  cursor and its preview builds a moment later. You can also use the **Iteron** tab in the 3D Viewport sidebar (**N**),
  which shows a thumbnail gallery of the formulas, or search for *Iteron* with **F3**.
* **Shape** it in the **Iteron** tab. Every slider rebuilds the preview while **Live** (the ▶ in the panel header)
  is on.
  * **Presets:** pick a built-in preset, save your own with **+**, delete yours with **−**, or reset everything
    with ↺.
  * **Julia:** escape-time formulas have a **Julia** section.
* **Region** sets what is sampled:
  * **Frame View** meshes only what the viewport is looking at, around its pivot and at its current zoom. Zoom in on
    a detail, press Frame View, then Build Final to get that detail at full resolution. ↺ goes back to the whole
    fractal.
  * **Auto-Fit**, **Center** and **Size** set the box by hand.
  * **Cut** slices the fractal open along X, Y or Z to show its inside. The cut face is closed, so the mesh stays
    solid.
* **Mesh** holds the build's quality settings. How each one trades detail for speed:
  * **Preview** is the live resolution.
  * **Surface Offset** is how far out the surface sits, in voxels of true distance (Iteron measures how much each
    formula's distance estimate underestimates and corrects for it). Lower shows finer detail; higher is cleaner and
    has fewer faces. Each formula starts at a sensible value.
  * **Refine** is how many Newton steps move every vertex exactly onto the fractal's surface, so ridges and grooves
    come out crisp instead of melted. Previews use at most one step.
  * **Shading:** *Field Normals* (the default) takes the normals from the fractal itself, so the shading shows
    detail finer than the faces.
  * **Final** is the Build Final resolution, with an estimate of the face count and memory.
  * **Simplify** lets Build Final merge flat areas into larger faces, within a fraction of a voxel, while intricate
    areas keep every face. The mesh stays closed and manifold.
  * **Apply as Plain Mesh** stops rebuilding and keeps the mesh as it is, for sculpting or editing.
* **Color** chooses what drives the colour ramp (*Orbit Trap*, *Iterations*, *Radius*, *Solid*) and shows the
  ramp itself. The ramp is the object's material: editing it here or in the Shader Editor is the same thing.

The fractal is a normal mesh object, so all of Blender's tools apply:

* **Modifiers** survive rebuilds.
* **Undo, `.blend` files and linked duplicates** work. Opening a file never recomputes anything.
* **Exporting:** for glTF, set *Data ▸ Mesh ▸ Vertex Color* to **Active** to include the colours. PLY and USD carry
  the `Col` attribute too.

### Detail, speed and face counts

Fractal surfaces grow faster than the square of the resolution (faces ≈ resolution^2.5), so detail costs faces. To
make the most of each one:

* Use **Frame View** for close-ups. A detail that fills the screen gets the whole resolution budget.
* Raise **Final** for whole-object renders, and keep **Simplify** on.
* Lower **Surface Offset** for crisper fine detail, or raise it for a cleaner, lighter mesh.

Builds sample only the parts of space the surface passes through, one block at a time, so memory follows the surface
rather than the volume. Resolutions up to 1024 work. The limit is a preference.

The field is sampled on the **GPU** through Blender's own `gpu` module when it can be, and on the CPU with numpy
otherwise. The CPU is slower but works everywhere, including `blender -b`. You can choose either in the add-on's
preferences.

### Scripting

```python
import bpy
bpy.ops.iteron.add_fractal(formula="mandelbulb")
obj = bpy.context.active_object
obj.iteron.f_mandelbulb.power = 6.0          # each formula's parameters live in obj.iteron.f_<formula id>
obj.iteron.final_resolution = 320
bpy.ops.iteron.build_final()                 # from a script (or blender -b) this builds synchronously
```

Formula ids are the names in lower case with underscores (`mandelbulb`, `menger_sponge`, `folding_int_pow`, …;
`aboxmod1` for ABoxMod1). In background mode, changing a parameter doesn't start a build; call
`bpy.ops.iteron.rebuild()` or `bpy.ops.iteron.build_final()`.

## Formulas

| Family | Formula | Presets |
|---|---|---|
| Bulbs | Mandelbulb | Classic, Power 4, Power 3, Juliabulb |
| Bulbs | Folding Int Pow | Default, Power 2, Flattened, Julia |
| Bulbs | Lambdabulb | Default, Power 2, Spiral |
| Boxes | Mandelbox | Classic, Open, Sculpted, Amazing Box |
| Boxes | Amazing Surf | Default, Flat, Waves |
| Boxes | ABoxMod1 | Default, Negative, Turned, Offset |
| Sponges | Menger Sponge | Level 4, Level 2, Level 5, Stretched |
| Sponges | Mosely Snowflake | Default, Keep Centre, Lace |
| Sponges | Jerusalem Cube | Default, Level 2, Chunky, Airy |
| Kaleidoscopic IFS | Sierpinski Tetrahedron | Default, Sparse, Skewed |
| Kaleidoscopic IFS | Octahedral KIFS | Default, Truncated, Star, Twisted |
| Kaleidoscopic IFS | Koch Tetrahedron | Default, Level 2, Stretched |
| Quaternion | Quaternion Julia | Default, Coral, Dendrite |

Where each formula's mathematics comes from is in [THIRD_PARTY.md](THIRD_PARTY.md).

## Development

```
iteron/            the extension (what the zip contains)
  core/            formulas' machinery, numpy evaluation, GLSL tracing, blocks, surface nets, refinement,
                   simplification — never imports bpy
  formulas/        one small file per family of @formula functions
  gpu_eval/        the GPU sampler (Blender's gpu module)
  bridge/          Blender data: generated properties, mesh writing, material, colours, staleness
  jobs/            the build pipeline (bpy-free) and the scheduler that runs it between UI events
  ops/  ui/        operators, the sidebar panel, the Add menu
  thumbnails/      the formula gallery (tools/render_thumbnails.py)
tests/core/        pytest, no Blender: formulas, surface nets, GLSL ↔ numpy parity (moderngl)
tests/blender/     pytest inside Blender: the add-on end to end, the scheduler, the GPU sampler, the UI
tools/             build.py, check_install.py, run_blender_tests.py, render_thumbnails.py, compose_gallery.py
branding/          the logo and icons (and their generator)
```

**Adding a formula** means writing one function. Its parameters, Blender properties, sidebar widgets, GLSL shader,
CPU fallback and presets are all generated from this:

```python
@formula("Mandelbulb", family="Bulbs", kind=ESCAPE, distance=LOG, bounds=1.4,
         params=(Float("power", 8.0, min=2.0, max=16.0),), presets={"Power 4": {"power": 4.0}})
def mandelbulb(z, dr, c, p):
    r = ops.max(ops.length(z), TINY)
    dr = ops.pow(r, p.power - 1.0) * p.power * dr + 1.0
    return triplex_power(z, p.power) + c, dr
```

Formulas use the GLSL-named functions in `iteron.core.ops`. Run with numpy arrays they compute (the CPU path); run
with symbolic values they are traced into GLSL (the GPU path). Use `ops.select` for choices that depend on the point,
and `ops.loop` for runtime-bounded loops. The parity tests then check that both paths agree.

**Tests**

```bash
python -m pytest tests/core                           # numpy + pytest (+ moderngl for the GPU parity tests)
python -m pip install bpy && python -m pytest tests   # the whole suite against the bpy module (Python 3.11)
blender -b --factory-startup --python tools/run_blender_tests.py    # or inside a real Blender
```

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Stan Ragets.
