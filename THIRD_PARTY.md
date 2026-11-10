# Provenance and attribution

Iteron is MIT licensed (see `LICENSE`). This file records where every formula's mathematics and every ported piece of
code came from. No GPL, LGPL or non-commercial (CC BY-NC) source is copied into Iteron; the classic fractals are
written from their published mathematics.

## Formulas (`iteron/formulas/`)

| Formula | Mathematics | Iteron's code |
|---|---|---|
| Mandelbulb (and Juliabulb via *Julia*) | Daniel White and Paul Nylander's triplex power (2009); the running-derivative distance estimate | Written for Iteron after Fractalchemy's `Triplex.frag` (Stan Ragets, MIT) |
| Mandelbox | Tom Lowe's (Tglad) box fold and sphere fold (2010) | Written for Iteron |
| Amazing Surf | The Mandelbulb3D formula of that name: box fold on x and y only, sphere fold, scale, rotation | Translated from Fractalchemy's *Fractalchemy Collection* `3D - Amazing Surf.frag` (Stan Ragets, MIT) |
| Menger Sponge | Karl Menger (1926); the kaleidoscopic-IFS construction by Knighty (fractalforums.com, 2010) | Written for Iteron |
| Mosely Snowflake | Jeannine Mosely's snowflake sponge; the box-cut construction | Translated from the Collection's `3D - Mosely Snowflake.frag` (Stan Ragets, MIT), with two fixes: the cells are centred on the cube's grid, and the corner cut extends past the cube so no phantom skin is left |
| Sierpinski Tetrahedron | Wacław Sierpiński; Knighty's kaleidoscopic-IFS folds | Written for Iteron |
| Octahedral KIFS | Knighty's kaleidoscopic IFS with octahedral symmetry and a per-iteration rotation | Written for Iteron |
| Quaternion Julia | Julia sets in the quaternions (Norton 1982); the distance estimate of Hart, Sandin and Kauffman (1989) | Written for Iteron |
| Folding Int Pow | The Mandelbulb3D formula of that name: a box fold, a triplex power, a z multiplier | Translated from the Collection's `3D - Folding Int Pow.frag` (Stan Ragets, MIT) |
| Lambdabulb | The lambda map z ↦ λz(1 − zⁿ⁻¹) in triplex arithmetic | Translated from the Collection's `3D - Lambdabulb.frag` (Stan Ragets, MIT); Iteron uses a running derivative instead of the fragment's finite differences |
| ABoxMod1 | The Mandelbulb3D formula of that name: per-axis box fold, sphere fold, scale, offset, rotation | Translated from the Collection's `3D - Amazing Box Mod1.frag` (Stan Ragets, MIT) |
| Jerusalem Cube | Eric Baird's Jerusalem cube: a cube minus a cross of slabs, corner and edge cubes at ratios 1 + √2 and (1 + √2)² | Translated from the Collection's `3D - Jerusalem Cube.frag` (Stan Ragets, MIT) |
| Koch Tetrahedron | The 3D Koch snowflake (its limit is a cube) | Translated from the Collection's `3D - Koch Tetrahedron.frag` (Stan Ragets, MIT) |
| Hybrid | Mandelbulb3D's hybrids (Jesse and the Mandelbulb3D authors): formulas alternating within one iteration | Written for Iteron |

`ops.sd_box` — the signed distance to a box — follows Inigo Quilez's published distance functions
(https://iquilezles.org/articles/distfunctions/), released under the MIT licence:

> Copyright (c) Inigo Quilez. Permission is hereby granted, free of charge, to any person obtaining a copy of this
> software and associated documentation files (the "Software"), to deal in the Software without restriction,
> including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following
> conditions: The above copyright notice and this permission notice shall be included in all copies or substantial
> portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.

## Flames (`iteron/flames/`)

* The flame model, the chaos game, density meshing and the `.fa` / `.fa3d` readers are ported from Fractalchemy
  (`fractal/scene.py`, `render/compiled.py`, `render/cpu_engine.py`, `solid/voxelize.py`, `solid/io/blender.py`,
  Stan Ragets, MIT), in numpy only.
* The variations (`var_classic.py`, `var_plugins.py`, `var_depth.py`) are ported from Fractalchemy's natively
  written `formulas/builtin/flam3.py` (MIT). Their formulas are the published ones: flam3's (Scott Draves and Erik
  Reckase, *The Fractal Flame Algorithm*, 2003) and the Apophysis plugins'. `tests/core/test_variation_parity.py`
  checks every shared variation against Fractalchemy's own at test time. `julia3D` and `spherical3D` are written for
  Iteron from their published formulas. Nothing from Fractalchemy's compiled plugin library (GPL-derived) is used.
* The bundled flames (`flames/library/*.json`) are the project's own.

## Fragments (`iteron/fragments/`)

* The preprocessor and the annotation grammar follow Fractalchemy's `fragments/preprocessor.py` (Stan Ragets, MIT),
  itself a translation of FragM's directive rules; the document helpers follow `fragments/document_format.py` and
  `fragments/presets.py`. Written anew in a smaller form.
* **Include shims** (`fragments/shims/`), all MIT:
  * `DE-Raytracer.frag` — written for Iteron; it only declares what a distance estimator touches (the orbit trap,
    the ray tracer's and camera's settings as fixed values). It stands in for every FragM ray tracer, whose code is
    not used.
  * `MathUtils.frag` — written for Iteron from the textbook formulas (axis–angle rotation, translation and scale
    matrices), keeping Fragmentarium's function names and conventions; Thomas Wang's integer hash; the well-known
    one-line sine hash.
  * `Triplex.frag` — Fractalchemy's own (Stan Ragets, MIT), unchanged.
  * `QuilezLib.frag` — Inigo Quilez's distance functions (MIT, notice above) under the names Fragmentarium's library
    uses.
  * `Primitives.frag` — Fractalchemy's `Primitives.frag` (Stan Ragets, MIT) with only its MIT-sourced functions:
    Inigo Quilez's distance functions (MIT), the hg_sdf library by Mercury (http://mercury.sexy/hg_sdf/, MIT — Copyright
    (c) 2015 Mercury Demogroup) and Akleman & Chen's generalized distance functions via hg_sdf. The functions that
    Fractalchemy took from Jon Baker's *Distance Estimator Compendium* (CC BY-NC-SA) are left out.
* FragM's own include files and example fragments (GPL / LGPL) are **not** part of Iteron. Users can point the
  *Include Folders* preference at their own copies, which are read at run time. `tests/fixtures/fractalchemy/
  PseudoKleinian.fafrag` is a test fixture only (Knighty's fragment as exported by Fractalchemy) and is not shipped.

## Code ported from Fractalchemy (Stan Ragets, MIT)

| Iteron | Fractalchemy | Changes |
|---|---|---|
| `core/surface_nets.py` | `solid/isosurface.py` (naive surface nets, `resolve_ambiguities`) | numpy only (no scipy), quads kept as quads, sparse: memory follows the surface, ~12× faster at 384³ |
| `gpu_eval/sampler.py` | `fragments/gl/mesh.py` (slab-packed distance probe) | Blender's `gpu` module instead of moderngl; advanced from a viewport draw callback |
| `core/grid.py` | `fragments/mesh.py` (voxel-offset threshold, memory estimate, coarse fit) | Rewritten around `GridPlan` |
| `cli/gl_sampler.py` | `fragments/gl/mesh.py` (moderngl probe) | The add-on's probe sources; also serves the tests |

Naive surface nets: Sarah F. Frisken Gibson, *Constrained Elastic Surface Nets* (1998).

## Techniques

* **Simplification** (`core/simplify.py`): adaptive vertex clustering on the voxel octree after Scott Schaefer and Joe
  Warren, *Adaptive Vertex Clustering Using Octrees* (2003), with the quadric error function of Tao Ju, Frank Losasso,
  Scott Schaefer and Joe Warren, *Dual Contouring of Hermite Data* (2002). Written for Iteron.
* **Normals and refinement** (`core/refine.py`): the tetrahedral four-sample gradient popularised by Inigo Quilez
  (https://iquilezles.org/articles/normalsSDF/). Written for Iteron.
* **Live preview** (`core/raymarch.py`): sphere tracing (John C. Hart, *Sphere Tracing*, 1996) with a pixel-footprint
  threshold and the same tetrahedral normals. Written for Iteron.

## Branding

The logo and icons (`branding/`) are the project's own work (MIT). The social card's tagline is set in DejaVu Sans,
converted to outlines (Bitstream Vera / DejaVu licence, which permits this).
