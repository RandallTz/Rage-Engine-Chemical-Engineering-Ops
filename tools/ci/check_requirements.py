#!/usr/bin/env python
"""Fail if a third-party module imported under core/, backend/ or tests/ is
missing from requirements.txt.

Usage: python tools/ci/check_requirements.py

The import name of a package often differs from its distribution name
(ternary -> python-ternary, yaml -> PyYAML), so the mapping below is explicit.
Distributions that are only transitive dependencies of a pinned package are
still reported, because an unpinned import breaks the exact-value regressions.
"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN = ["core", "backend", "tests"]

# import name -> distribution name (lower case, normalised with '-')
IMPORT_TO_DIST = {
    "ternary": "python-ternary",
    "yaml": "pyyaml",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
}


def requirement_names():
    names = set()
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        names.add(re.split(r"[=<>!~\[ ]", line, 1)[0].lower().replace("_", "-"))
    return names


def local_modules():
    local = {d.name for d in ROOT.iterdir() if d.is_dir()}
    for sub in SCAN:
        base = ROOT / sub
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.suffix == ".py":
                local.add(path.stem)
            elif path.is_dir():
                local.add(path.name)
    return local


def imported_top_levels():
    found = {}
    for sub in SCAN:
        for path in (ROOT / sub).rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    mods = [node.module]
                else:
                    continue
                for mod in mods:
                    found.setdefault(mod.split(".")[0], set()).add(str(path.relative_to(ROOT)))
    return found


def main():
    stdlib = set(sys.stdlib_module_names)
    local = local_modules()
    reqs = requirement_names()
    missing = {}
    for top, files in sorted(imported_top_levels().items()):
        if top in stdlib or top in local or top == "__future__":
            continue
        dist = IMPORT_TO_DIST.get(top, top).lower().replace("_", "-")
        if dist not in reqs:
            missing[top] = sorted(files)
    if missing:
        print("Imported but not pinned in requirements.txt:")
        for top, files in missing.items():
            print(f"  {top}: {', '.join(files[:4])}{' ...' if len(files) > 4 else ''}")
        return 1
    print("OK: every third-party import under core/, backend/ and tests/ is pinned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
