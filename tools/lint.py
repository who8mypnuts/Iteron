# SPDX-License-Identifier: MIT
"""pyflakes over the given folders, minus one false alarm: Blender properties are declared as annotations
(`power: FloatProperty(name="Power")`), and pyflakes reads the strings inside them as type annotations. Messages
inside an annotation that is a call are dropped, and so are lines marked `# noqa` (imports made for their side
effect); everything else is reported.

    python tools/lint.py iteron tests tools
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from pyflakes import api, reporter


class Collect(reporter.Reporter):
    def __init__(self):
        super().__init__(sys.stdout, sys.stderr)
        self.messages = []

    def flake(self, message):
        self.messages.append(message)

    def syntaxError(self, filename, msg, lineno, offset, text):      # noqa: N802 - pyflakes' API
        self.messages.append(f"{filename}:{lineno}: syntax error: {msg}")

    def unexpectedError(self, filename, msg):                       # noqa: N802
        self.messages.append(f"{filename}: {msg}")


def property_lines(source: str) -> set[int]:
    """Lines inside annotations that are calls (Blender property declarations)."""
    lines = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.AnnAssign) and isinstance(node.annotation, ast.Call):
            lines.update(range(node.annotation.lineno, node.annotation.end_lineno + 1))
    return lines


def lint(paths: list[Path]) -> list[str]:
    found = []
    for path in sorted(p for root in paths for p in (root.rglob("*.py") if root.is_dir() else [root])):
        source = path.read_text(encoding="utf-8")
        collect = Collect()
        api.check(source, str(path), collect)
        lines = source.splitlines()
        skip = property_lines(source) | {i + 1 for i, line in enumerate(lines) if "# noqa" in line}
        for message in collect.messages:
            if isinstance(message, str):
                found.append(message)
            elif message.lineno not in skip:
                found.append(str(message))
    return found


def main() -> int:
    found = lint([Path(p) for p in sys.argv[1:] or ["iteron", "tests", "tools"]])
    print("\n".join(found) if found else "pyflakes: clean")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
