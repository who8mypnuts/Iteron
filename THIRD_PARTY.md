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

`ops.sd_box` — the signed distance to a box — follows Inigo Quilez's published distance functions
(https://iquilezles.org/articles/distfunctions/), released under the MIT licence:

> Copyright (c) Inigo Quilez. Permission is hereby granted, free of charge, to any person obtaining a copy of this
> software and associated documentation files (the "Software"), to deal in the Software without restriction,
> including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following
> conditions: The above copyright notice and this permission notice shall be included in all copies or substantial
> portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.

## Code ported from Fractalchemy (Stan Ragets, MIT)

| Iteron | Fractalchemy | Changes |
|---|---|---|
| `core/surface_nets.py` | `solid/isosurface.py` (naive surface nets, `resolve_ambiguities`) | numpy only (no scipy), quads kept as quads, sparse: memory follows the surface, ~12× faster at 384³ |
| `gpu_eval/sampler.py` | `fragments/gl/mesh.py` (slab-packed distance probe) | Blender's `gpu` module instead of moderngl; advanced from a viewport draw callback |
| `core/grid.py` | `fragments/mesh.py` (voxel-offset threshold, memory estimate, coarse fit) | Rewritten around `GridPlan` |

Naive surface nets: Sarah F. Frisken Gibson, *Constrained Elastic Surface Nets* (1998).

## Techniques

* **Simplification** (`core/simplify.py`): adaptive vertex clustering on the voxel octree after Scott Schaefer and Joe
  Warren, *Adaptive Vertex Clustering Using Octrees* (2003), with the quadric error function of Tao Ju, Frank Losasso,
  Scott Schaefer and Joe Warren, *Dual Contouring of Hermite Data* (2002). Written for Iteron.
* **Normals and refinement** (`core/refine.py`): the tetrahedral four-sample gradient popularised by Inigo Quilez
  (https://iquilezles.org/articles/normalsSDF/). Written for Iteron.

## Branding

The logo and icons (`branding/`) are the project's own work (MIT). The social card's tagline is set in DejaVu Sans,
converted to outlines (Bitstream Vera / DejaVu licence, which permits this).
