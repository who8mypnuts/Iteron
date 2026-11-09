#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Build the Iteron extension zip: copy the branding icons in, then ask Blender to package it (PLAN.md §3).
#
#   tools/build.sh [path-to-blender]
#
# Needs a real Blender (4.2+) on PATH or given as the first argument; this script cannot run inside the
# sandbox this project was scaffolded in (see README.md's "what has and hasn't been tested" note).
set -euo pipefail
cd "$(dirname "$0")/.."

BLENDER="${1:-blender}"
cp branding/addon/iteron_icon.png iteron/icons/iteron_icon.png
cp branding/addon/iteron_logo.png iteron/icons/iteron_logo.png

mkdir -p dist
"$BLENDER" --command extension build --source-dir iteron --output-dir dist
echo "Built: $(ls dist/*.zip | tail -1)"
