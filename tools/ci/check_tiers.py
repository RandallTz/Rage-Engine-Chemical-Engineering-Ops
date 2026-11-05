#!/usr/bin/env python
"""Fail unless every tests/validar_*.py suite is in exactly one CI tier.

Fast = every suite not listed under "slow" in tools/ci/test_tiers.json.
The slow tier runs as one GitHub job per suite (the matrix in
.github/workflows/validacion.yml); this check makes sure that matrix and the
"slow" list are the same set, so a suite can neither be dropped nor run twice.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    tiers = json.loads((ROOT / "tools/ci/test_tiers.json").read_text(encoding="utf-8"))
    suites = {p.name for p in (ROOT / "tests").glob("validar_*.py")}
    slow = set(tiers["slow"])
    known = {k for k in tiers.get("known_failing", {}) if not k.startswith("_")}
    errors = []
    if slow - suites:
        errors.append(f"'slow' names missing suites: {sorted(slow - suites)}")
    if known - suites:
        errors.append(f"'known_failing' names missing suites: {sorted(known - suites)}")
    if slow & known:
        errors.append(f"in both 'slow' and 'known_failing': {sorted(slow & known)}")

    workflow = (ROOT / ".github/workflows/validacion.yml").read_text(encoding="utf-8")
    block = re.search(r"matrix:\s*\n(?:\s*#.*\n)*\s*suite:\s*\n((?:\s*-\s*\S+\s*\n)+)", workflow)
    matrix = {f"validar_{m}.py" for m in re.findall(r"-\s*(\S+)", block.group(1))} if block else set()
    if not block:
        errors.append("could not find the core-slow matrix in validacion.yml")
    elif matrix != slow:
        errors.append(f"workflow matrix != 'slow' list: only in workflow {sorted(matrix - slow)}, only in list {sorted(slow - matrix)}")
    # a matrix filter is a substring: it must select exactly its own suite
    for name in matrix:
        key = name[len("validar_"):-3]
        hit = [s for s in suites if key in s.lower()]
        if hit != [name]:
            errors.append(f"matrix filter '{key}' selects {sorted(hit)} instead of only {name}")

    if errors:
        print("\n".join(errors))
        return 1
    print(f"OK: {len(suites)} suites = {len(suites) - len(slow)} fast + {len(slow)} slow (one job each).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
