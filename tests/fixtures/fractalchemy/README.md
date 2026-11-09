# Test fixtures — not part of the add-on

These files exercise the `.fa` / `.fa3d` / `.fafrag` readers in `iteron/interop/`. They are **not** shipped in the
extension zip (the build script only packages `iteron/`) and are not redistributed anywhere else.

| File | Source | Licence |
|---|---|---|
| `anew.fa` | `sample_source/Fractalchemy/samples/sample flames/archive/ANEW-261026-203.fa` | Fractalchemy sample, MIT (author's) |
| `musk_sphere.fa3d` | Provided by the project owner, exported from Fractalchemy's 3D Editor | MIT (author's) |
| `pseudo_kleinian.fafrag` | Provided by the project owner; the formula is Knighty's Pseudo Kleinian, bundled with Fragmentarium/FragM's example library (`Examples/Knighty Collection/PseudoKleinian.frag`) | **GPL-3 / LGPL** (FragM examples) — test fixture only, used to check the reader and the compatibility shims against a real file; never copied into `iteron/`. |
