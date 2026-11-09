# SPDX-License-Identifier: MIT
"""Install the built zip the way a user does and exercise it: Blender's extension installer, enable, build a
fractal, disable, enable again. Uses a throw-away user-resources folder, so your own Blender setup is untouched.

    python tools/build.py
    BLENDER_USER_RESOURCES=$(mktemp -d) blender -b --factory-startup --python tools/check_install.py
    (or, with the `bpy` module:  BLENDER_USER_RESOURCES=$(mktemp -d) python tools/check_install.py)
"""

import os
import sys
from pathlib import Path

import bpy  # first: with the `bpy` module, Blender's own modules (addon_utils) become importable after it

import addon_utils  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NAME = "bl_ext.user_default.iteron"


def main() -> int:
    if not os.environ.get("BLENDER_USER_RESOURCES"):
        print("Set BLENDER_USER_RESOURCES to a temporary folder first (this installs an extension).")
        return 2
    archive = max((ROOT / "dist").glob("iteron-*.zip"), key=lambda p: p.stat().st_mtime)
    assert bpy.ops.extensions.package_install_files(filepath=str(archive), repo="user_default",
                                                    enable_on_install=True) == {"FINISHED"}
    assert NAME in bpy.context.preferences.addons, "not enabled after installing"
    assert bpy.context.preferences.addons[NAME].preferences.device == "AUTO"
    bpy.ops.iteron.add_fractal(formula="menger_sponge")
    obj = bpy.context.active_object
    assert obj.iteron.built_faces > 1000 and not obj.iteron.message, obj.iteron.message
    addon_utils.disable(NAME, default_set=True)
    assert not hasattr(bpy.types.Object, "iteron"), "properties left behind after disabling"
    addon_utils.enable(NAME, default_set=True)
    bpy.ops.iteron.add_fractal(formula="mandelbulb")
    assert bpy.context.active_object.iteron.built_faces > 1000
    addon_utils.disable(NAME, default_set=True)
    print(f"OK: {archive.name} installs, builds, disables and re-enables on Blender {bpy.app.version_string}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
