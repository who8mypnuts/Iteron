#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Iteron's whole check, from scratch: fresh virtual environments, their dependencies, every check, and a summary
# that says EXPECTED or MISMATCH for each. Exits non-zero when anything is a MISMATCH.
#
#   tests/run_tests.sh
#   ITERON_BLENDER_VERSIONS="5.0.1" tests/run_tests.sh          # one Blender version only
#
# Installed: numpy, pytest, pyflakes, moderngl (the GPU tests outside Blender), pillow and scipy (textures, and the
# Fractalchemy code some tests compare against) in a core environment; bpy, numpy, pytest and pillow per Blender
# version.
#
# Environment (all optional):
#   ITERON_PYTHON            Python 3.11+ for the bpy-free checks          (default: python3)
#   ITERON_PYTHON311         Python 3.11 for the bpy wheels                (default: python3.11, else uv's 3.11)
#   ITERON_PY311_LIBS        extra LD_LIBRARY_PATH that Python needs (e.g. one unpacked from .deb packages)
#   ITERON_BLENDER_VERSIONS  bpy versions to test                          (default: "4.2.0 5.0.1")
#   ITERON_WORK              where environments and logs go                (default: ${TMPDIR:-/tmp}/iteron-tests)
#   ITERON_WHEELS            a folder of wheels tried before PyPI (the bpy wheels are ~350 MB each)
#   ITERON_KEEP_ENVS=1       reuse the environments of an earlier run instead of recreating them
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${ITERON_WORK:-${TMPDIR:-/tmp}/iteron-tests}"
LOGS="$WORK/logs"
PYTHON="${ITERON_PYTHON:-python3}"
VERSIONS="${ITERON_BLENDER_VERSIONS:-4.2.0 5.0.1}"
UV="${ITERON_UV:-$(command -v uv || true)}"
[ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ] && UV="$HOME/.local/bin/uv"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
[ -n "${ITERON_PY311_LIBS:-}" ] && export LD_LIBRARY_PATH="$ITERON_PY311_LIBS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

NAMES=(); RESULTS=(); DETAILS=()
record() { NAMES+=("$1"); RESULTS+=("$2"); DETAILS+=("$3"); printf '  %-34s %-9s %s\n' "$1" "$2" "$3"; }
# LAST: the exit code. (The `exit` keeps bash from exec-ing the command, so a crash is reported into the log.)
logged() { local name="$1"; shift; ( "$@"; exit $? ) >"$LOGS/$name.log" 2>&1; LAST=$?; return $LAST; }
pytest_summary() { grep -E '^[=]* ?[0-9]+ (passed|failed|error)' "$1" | tail -n 1 | sed -E 's/=//g; s/^ +| +$//g'; }
pytest_clean() { local s; s="$(pytest_summary "$1")"; [ -n "$s" ] && ! grep -qE '[0-9]+ (failed|error)' <<<"$s"; }

# --- environments ----------------------------------------------------------------------------------------------
make_env() {   # make_env DIR PYTHON PACKAGES…
  local dir="$1" python="$2"; shift 2
  local find=(); [ -n "${ITERON_WHEELS:-}" ] && find=(--find-links "$ITERON_WHEELS")
  if [ -x "$dir/bin/python" ] && [ "${ITERON_KEEP_ENVS:-0}" = 1 ]; then return 0; fi
  rm -rf "$dir"
  if [ -n "$UV" ]; then
    "$UV" venv -q --python "$python" "$dir" && "$UV" pip install -q --python "$dir/bin/python" "${find[@]}" "$@"
  else
    "$python" -m venv "$dir" && "$dir/bin/python" -m pip install -q --upgrade pip && \
      "$dir/bin/python" -m pip install -q "${find[@]}" "$@"
  fi
}

find_python311() {
  if [ -n "${ITERON_PYTHON311:-}" ]; then echo "$ITERON_PYTHON311"; return; fi
  if command -v python3.11 >/dev/null; then command -v python3.11; return; fi
  [ -n "$UV" ] && "$UV" python find 3.11 2>/dev/null
}

echo "Iteron checks — repository $ROOT, work folder $WORK"
[ "${ITERON_KEEP_ENVS:-0}" = 1 ] || rm -rf "$WORK"
mkdir -p "$LOGS"
find "$ROOT/iteron" "$ROOT/tests" "$ROOT/tools" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
cd "$ROOT" || exit 2

echo "Environments"
CORE="$WORK/env-core"
if logged env-core make_env "$CORE" "$PYTHON" numpy pytest pyflakes moderngl pillow scipy; then
  record "environment: core" EXPECTED "$("$CORE/bin/python" -c 'import sys, numpy; print(f"Python {sys.version.split()[0]}, numpy {numpy.__version__}")')"
else
  record "environment: core" MISMATCH "see $LOGS/env-core.log"
fi
PY311="$(find_python311)"
declare -A BPY=()
for v in $VERSIONS; do
  if [ -z "$PY311" ]; then record "environment: bpy $v" MISMATCH "no Python 3.11 (set ITERON_PYTHON311)"; continue; fi
  if logged "env-bpy-$v" make_env "$WORK/env-bpy-$v" "$PY311" "bpy==$v" "numpy==1.26.4" pytest pillow; then
    BPY[$v]="$WORK/env-bpy-$v/bin/python"
    record "environment: bpy $v" EXPECTED "$("${BPY[$v]}" -c 'import bpy; print("Blender", bpy.app.version_string)' 2>/dev/null | tail -n 1)"
  else
    record "environment: bpy $v" MISMATCH "see $LOGS/env-bpy-$v.log"
  fi
done

# bpy 4.2.0 (the module, not Blender itself) crashes at interpreter exit once any class with an update callback has
# been registered — this repro needs nothing from Iteron. Where it crashes too, exit code 139 *after* a clean run is
# that upstream bug and is tolerated (and said so); anywhere else a non-zero exit is a MISMATCH.
declare -A EXIT_BUG=()
for v in "${!BPY[@]}"; do
  ( "${BPY[$v]}" - >/dev/null 2>&1 <<'EOF'
import bpy
class Repro(bpy.types.PropertyGroup):
    value: bpy.props.IntProperty(update=lambda self, context: None)
bpy.utils.register_class(Repro)
bpy.utils.unregister_class(Repro)
EOF
  exit $? ) 2>/dev/null
  if [ $? = 139 ]; then EXIT_BUG[$v]=1; echo "  note: bpy $v crashes at exit after registering an update callback (upstream; repro without Iteron)"; fi
done
exit_ok() { [ "$2" = 0 ] || { [ "$2" = 139 ] && [ "${EXIT_BUG[$1]:-0}" = 1 ]; }; }
exit_note() { [ "$1" = 139 ] && echo "; exit 139 at shutdown: the upstream bpy bug above"; }

# --- static checks ---------------------------------------------------------------------------------------------
echo "Static checks"
if logged lint "$CORE/bin/python" tools/lint.py iteron tests tools; then
  record "lint (pyflakes)" EXPECTED "clean"
else
  record "lint (pyflakes)" MISMATCH "$(grep -c . "$LOGS/lint.log") findings, see $LOGS/lint.log"
fi
LONG="$(find iteron tests tools -name '*.py' -exec awk 'END { if (NR > 400) print FILENAME " (" NR ")" }' {} \;)"
if [ -z "$LONG" ]; then
  record "files <= 400 lines" EXPECTED "largest: $(find iteron tests tools -name '*.py' -exec wc -l {} + | grep -v ' total$' | sort -n | tail -n 1 | awk '{print $2 " (" $1 ")"}')"
else
  record "files <= 400 lines" MISMATCH "$(echo "$LONG" | tr '\n' ' ')"
fi
MISSING="$(find iteron tests tools -name '*.py' -o -name '*.frag' -o -name '*.sh' | while read -r f; do
  head -n 3 "$f" | grep -q 'SPDX-License-Identifier: MIT' || echo "$f"; done)"
if [ -z "$MISSING" ]; then record "SPDX headers" EXPECTED "every .py, .frag and .sh file"
else record "SPDX headers" MISMATCH "$(echo "$MISSING" | tr '\n' ' ')"; fi
if logged catalogue "$CORE/bin/python" tools/check_catalogue.py; then
  record "formula catalogue" EXPECTED "$(tail -n 1 "$LOGS/catalogue.log" | cut -c 12-)"
else
  record "formula catalogue" MISMATCH "$(grep -c . "$LOGS/catalogue.log") problems, see $LOGS/catalogue.log"
fi
if logged bpy-free "$CORE/bin/python" -c '
import sys
import iteron.formulas, iteron.core.glsl, iteron.core.cpu_eval, iteron.jobs.pipeline, iteron.jobs.flame_pipeline
import iteron.flames.chaos, iteron.flames.formats, iteron.fragments.formula, iteron.cli.commands
assert "bpy" not in sys.modules, "bpy was imported"
print("core, formulas, jobs, flames, fragments and cli import without bpy")'; then
  record "bpy-free core" EXPECTED "$(tail -n 1 "$LOGS/bpy-free.log")"
else
  record "bpy-free core" MISMATCH "see $LOGS/bpy-free.log"
fi

# --- tests -----------------------------------------------------------------------------------------------------
echo "Tests"
logged core-tests "$CORE/bin/python" -m pytest -q tests/core -p no:cacheprovider
if pytest_clean "$LOGS/core-tests.log" && [ "$LAST" = 0 ]; then record "core tests" EXPECTED "$(pytest_summary "$LOGS/core-tests.log")"
else record "core tests" MISMATCH "$(pytest_summary "$LOGS/core-tests.log") — see $LOGS/core-tests.log"; fi
if logged cli "$CORE/bin/python" -m iteron.cli mesh mandelbulb -r 32 --refine 0 -o "$WORK/cli.ply" -q && \
   FACES="$("$CORE/bin/python" -c "from iteron.cli.writers import read_ply_header as r; print(r('$WORK/cli.ply')['face'])")" && \
   [ "$FACES" -gt 100 ]; then
  record "command line (mesh -> PLY)" EXPECTED "$FACES faces"
else
  record "command line (mesh -> PLY)" MISMATCH "see $LOGS/cli.log"
fi
cat >"$WORK/two.flame" <<'EOF'
<Flames name="check"><flame name="gasket" size="400 400" center="0 0" scale="100">
  <xform weight="1" color="0" linear="1" coefs="0.5 0 0 0.5 0 0"/>
  <xform weight="1" color="0.5" linear="1" coefs="0.5 0 0 0.5 0.5 0"/>
  <xform weight="1" color="1" spherical="0.1" linear="0.9" coefs="0.5 0 0 0.5 0 0.5"/>
  <palette count="2" format="RGB">ff8000 0080ff</palette></flame></Flames>
EOF
if logged cli-flame "$CORE/bin/python" -m iteron.cli flame "$WORK/two.flame" -n 20000 -o "$WORK/flame.ply" -q && \
   POINTS="$("$CORE/bin/python" -c "from iteron.cli.writers import read_ply_header as r; print(r('$WORK/flame.ply')['vertex'])")" && \
   [ "$POINTS" -gt 15000 ]; then
  record "command line (.flame -> PLY)" EXPECTED "$POINTS points"
else
  record "command line (.flame -> PLY)" MISMATCH "see $LOGS/cli-flame.log"
fi
cat >"$WORK/tinted.frag" <<'EOF'
#define providesColor
#include "DE-Raytracer.frag"
uniform sampler2D bumps; file[bumps.png]
float DE(vec3 p) { return length(p) - 1.2 * texture2D(bumps, vec2(0.5, 0.5)).r; }
vec3 baseColor(vec3 p, vec3 n) { return p.z > 0.0 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 0.0, 1.0); }
EOF
if ! "$CORE/bin/python" -c "import sys; from iteron.cli.gl_sampler import context; sys.exit(context() is None)" \
     >/dev/null 2>&1; then
  record "command line (textured fragment)" EXPECTED "skipped: no OpenGL 3.3 context for moderngl here"
elif logged cli-fragment "$CORE/bin/python" -c "from PIL import Image; Image.new('RGB', (4, 4), (128, 128, 128)).save('$WORK/bumps.png')" && \
   logged cli-fragment "$CORE/bin/python" -m iteron.cli fragment "$WORK/tinted.frag" -r 40 --refine 1 --color base \
     -o "$WORK/tinted.obj" -q && \
   DETAIL="$("$CORE/bin/python" - "$WORK/tinted.obj" <<'EOF'
import sys, numpy as np
rows = np.array([[float(v) for v in line.split()[1:7]] for line in open(sys.argv[1]) if line.startswith("v ")])
radius, red, blue = np.linalg.norm(rows[:, :3], axis=1), rows[:, 3], rows[:, 5]
assert abs(np.median(radius) - 0.6) < 0.05, np.median(radius)              # 1.2 × the texture's 0.5
assert (red[rows[:, 2] > 0.1] == 1).all() and (blue[rows[:, 2] < -0.1] == 1).all()
print(f"{len(rows)} vertices, radius {np.median(radius):.3f}, its own colours")
EOF
)"; then
  record "command line (textured fragment)" EXPECTED "$DETAIL"
else
  record "command line (textured fragment)" MISMATCH "see $LOGS/cli-fragment.log"
fi
if logged fragments "$CORE/bin/python" tools/check_fragments.py --include-folder; then
  record "fragment library" EXPECTED "$(tail -n 1 "$LOGS/fragments.log")"
else
  record "fragment library" MISMATCH "$(tail -n 1 "$LOGS/fragments.log") — see $LOGS/fragments.log"
fi
for v in $VERSIONS; do
  [ -n "${BPY[$v]:-}" ] || { record "Blender $v tests" MISMATCH "no bpy environment"; continue; }
  logged "blender-$v-tests" "${BPY[$v]}" -m pytest -q tests -p no:cacheprovider
  SUMMARY="$(pytest_summary "$LOGS/blender-$v-tests.log")$(exit_note "$LAST")"
  if pytest_clean "$LOGS/blender-$v-tests.log" && exit_ok "$v" "$LAST"; then record "Blender $v tests" EXPECTED "$SUMMARY"
  else record "Blender $v tests" MISMATCH "$SUMMARY (exit $LAST) — see $LOGS/blender-$v-tests.log"; fi
done

# --- packaging -------------------------------------------------------------------------------------------------
echo "Packaging"
for v in $VERSIONS; do
  [ -n "${BPY[$v]:-}" ] || continue
  TOOL="$(ls "$WORK/env-bpy-$v"/lib/python3.11/site-packages/bpy/*/scripts/addons_core/bl_pkg/cli/blender_ext.py 2>/dev/null | head -n 1)"
  if [ -n "$TOOL" ] && logged "validate-$v" "${BPY[$v]}" "$TOOL" validate iteron && grep -q "Success" "$LOGS/validate-$v.log"; then
    record "manifest valid (Blender $v)" EXPECTED "$(grep -m 1 Success "$LOGS/validate-$v.log")"
  else
    record "manifest valid (Blender $v)" MISMATCH "see $LOGS/validate-$v.log"
  fi
done
if logged build "$CORE/bin/python" tools/build.py && ZIP="$(tail -n 1 "$LOGS/build.log")" && [ -f "$ZIP" ] && \
   "$CORE/bin/python" - "$ZIP" >>"$LOGS/build.log" 2>&1 <<'EOF'
import sys, zipfile
names = zipfile.ZipFile(sys.argv[1]).namelist()
assert "blender_manifest.toml" in names and "fragments/shims/DE-Raytracer.frag" in names
assert "flames/library/sierpinski_pyramid.json" in names and "thumbnails/hybrid.png" in names
assert not [n for n in names if "__pycache__" in n or n.startswith("tests/")]
print(f"{len(names)} files")
EOF
then
  record "extension zip" EXPECTED "$(basename "$ZIP"), $(tail -n 1 "$LOGS/build.log")"
else
  record "extension zip" MISMATCH "see $LOGS/build.log"
fi
for v in $VERSIONS; do
  [ -n "${BPY[$v]:-}" ] || continue
  RES="$(mktemp -d "$WORK/resources-XXXX")"
  BLENDER_USER_RESOURCES="$RES" logged "install-$v" "${BPY[$v]}" tools/check_install.py
  if grep -q "^OK:" "$LOGS/install-$v.log" && exit_ok "$v" "$LAST"; then
    record "install check (Blender $v)" EXPECTED "installs; formulas, flame (materials, holons), .flame, hybrid, fragment; re-enables$(exit_note "$LAST")"
  else
    record "install check (Blender $v)" MISMATCH "see $LOGS/install-$v.log"
  fi
done

# --- summary ---------------------------------------------------------------------------------------------------
FAILED=0
echo
echo "Summary"
printf '%-36s %-9s %s\n' "CHECK" "RESULT" "DETAIL"
printf '%-36s %-9s %s\n' "-----" "------" "------"
for i in "${!NAMES[@]}"; do
  printf '%-36s %-9s %s\n' "${NAMES[$i]}" "${RESULTS[$i]}" "${DETAILS[$i]}"
  [ "${RESULTS[$i]}" = EXPECTED ] || FAILED=$((FAILED + 1))
done
echo
if [ "$FAILED" = 0 ]; then echo "All ${#NAMES[@]} checks EXPECTED."; else echo "$FAILED of ${#NAMES[@]} checks MISMATCH (logs in $LOGS)."; fi
exit "$([ "$FAILED" = 0 ] && echo 0 || echo 1)"
