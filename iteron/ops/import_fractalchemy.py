# SPDX-License-Identifier: MIT
"""`File \u25b8 Import \u25b8 Fractalchemy (.fa / .fa3d / .fafrag / .frag)` (PLAN.md §7).

**Scope today**: this reads and validates a file through `iteron.interop` (which is fully tested against real
fixtures in `tests/core`) and reports what it found. Turning a flame into a point-cloud / mesh object is Phase 4's
chaos-game renderer and turning a fragment into a live Iteron object is Phase 5's GPU wrapper \u2014 neither
exists yet, so this operator says so rather than guessing at unverified bpy/GPU code on top of unverified bpy/GPU
code. Re-running this import once those phases land should need no change here beyond the two `# TODO` markers.
"""

from pathlib import Path

import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from ..interop.fa import FaFormatError
from ..interop.fa import parse_file as parse_fa
from ..interop.fa3d import Fa3dFormatError
from ..interop.fa3d import parse_file as parse_fa3d
from ..interop.fragment.reader import read_file as read_fragment


class ITERON_OT_import_fractalchemy(Operator, ImportHelper):
    bl_idname = "iteron.import_fractalchemy"
    bl_label = "Import Fractalchemy / Fragmentarium"
    bl_description = "Open a Fractalchemy .fa / .fa3d or a Fragmentarium .fafrag / .frag file"
    bl_options = {"REGISTER"}

    filename_ext = ""
    filter_glob: StringProperty(default="*.fa;*.fa3d;*.fafrag;*.frag", options={"HIDDEN"})

    def execute(self, context):
        path = Path(self.filepath)
        try:
            summary = _summarise(path)
        except (FaFormatError, Fa3dFormatError, OSError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, summary)
        return {"FINISHED"}


def _summarise(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".fa":
        flames = parse_fa(path)
        names = ", ".join(f.name for f in flames)
        unsupported = sorted({v for f in flames for v in f.unsupported})
        note = f"; unsupported variations: {', '.join(unsupported)}" if unsupported else ""
        # TODO (Phase 4): build a point-cloud / mesh object per chosen flame via the chaos game.
        return f"{len(flames)} flame(s) read ({names}){note} \u2014 flame rendering is a later phase, see the import's docstring"
    if suffix == ".fa3d":
        scene = parse_fa3d(path)
        # TODO (Phase 4): the same, plus materials / lights / environment / camera.
        return (f"Scene {scene.name!r} read: {len(scene.fractal.xforms)} transforms, {len(scene.lights)} lights "
                f"\u2014 3D scene rendering is a later phase, see the import's docstring")
    fragment = read_fragment(path)
    # TODO (Phase 5): a live GPU-sampled Iteron object from fragment.glsl / fragment.params / fragment.presets.
    return (f"Fragment read: {len(fragment.params)} parameters, presets: {', '.join(fragment.presets) or 'none'} "
            f"\u2014 fragment rendering is a later phase, see the import's docstring")


def menu_import(self, context) -> None:
    self.layout.operator(ITERON_OT_import_fractalchemy.bl_idname, text="Fractalchemy / Fragmentarium")


classes = (ITERON_OT_import_fractalchemy,)


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_import)


def unregister() -> None:
    bpy.types.TOPBAR_MT_file_import.remove(menu_import)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
