# SPDX-License-Identifier: MIT
"""Check that the formula catalogue and its documentation agree: every formula has a thumbnail (and no thumbnail is
an orphan), is in the README's table with its presets, and is credited in THIRD_PARTY.md; every family has a
picker entry. Plain Python (numpy), no Blender.

    python tools/check_catalogue.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def problems() -> list[str]:
    import iteron.formulas  # noqa: F401  (registers the formulas)
    from iteron.core.formula import REGISTRY, by_family
    found = []
    thumbnails = {p.stem for p in (ROOT / "iteron" / "thumbnails").glob("*.png")}
    found += [f"no thumbnail for {fid}" for fid in REGISTRY if fid not in thumbnails]
    found += [f"thumbnail of no formula: {name}.png" for name in thumbnails - set(REGISTRY)]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    third_party = (ROOT / "THIRD_PARTY.md").read_text(encoding="utf-8")
    for family, entries in by_family():
        for entry in entries:
            row = f"| {family} | {entry.name} | {', '.join(entry.presets)} |"
            if row not in readme:
                found.append(f"README's formula table lacks or misstates: {row}")
            if entry.name not in third_party:
                found.append(f"THIRD_PARTY.md does not credit {entry.name}")
    return found


def main() -> int:
    import iteron.formulas  # noqa: F401
    from iteron.core.formula import REGISTRY, by_family
    found = problems()
    print("\n".join(found) if found else f"catalogue: {len(REGISTRY)} formulas in {len(by_family())} families, "
          "all with thumbnails, README rows and credits")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
