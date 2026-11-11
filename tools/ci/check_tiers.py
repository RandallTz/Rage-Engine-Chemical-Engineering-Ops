#!/usr/bin/env python
"""Check complete, unique test coverage and the slow workflow matrices."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    tiers = json.loads((ROOT / "tools/ci/test_tiers.json").read_text(encoding="utf-8"))
    validators = {p.name for p in (ROOT / "tests").glob("validar_*.py")}
    pytest_files = {p.name for p in (ROOT / "tests").glob("test_*.py")}
    slow = tiers["slow"]
    fast_pytest = tiers["pytest_fast"]
    groups = tiers["pytest_slow_groups"]
    assigned = fast_pytest + [name for group in groups.values() for name in group]
    counts = Counter(assigned)
    errors = []
    if len(slow) != len(set(slow)) or set(slow) - validators:
        errors.append(f"Invalid or repeated slow validators: {slow}")
    if pytest_files - set(assigned):
        errors.append(f"Unassigned pytest files: {sorted(pytest_files - set(assigned))}")
    if set(assigned) - pytest_files:
        errors.append(f"Assigned pytest files absent from tests/: {sorted(set(assigned) - pytest_files)}")
    if any(n != 1 for n in counts.values()):
        errors.append(f"Repeated pytest files: {sorted(k for k, v in counts.items() if v != 1)}")
    known = {k: v for k, v in tiers.get("known_failing", {}).items() if not k.startswith("_")}
    if set(known) - (validators | pytest_files) or any(not isinstance(v, str) or not v.strip() for v in known.values()):
        errors.append("Quarantine entries must name existing suites and give a reason")
    workflow = (ROOT / ".github/workflows/validacion.yml").read_text(encoding="utf-8")
    def matrix(key):
        block = re.search(rf"^\s+{key}:\s*\n((?:\s+-\s+[^\s]+\s*\n)+)", workflow, re.MULTILINE)
        return re.findall(r"-\s*(\S+)", block.group(1)) if block else []
    suites = matrix("suite")
    expected = [name[len("validar_"):-3] for name in slow]
    if Counter(suites) != Counter(expected):
        errors.append("Workflow slow validator matrix differs from the registry")
    for key in suites:
        hits = [s for s in validators | pytest_files if key in s.lower()]
        if hits != [f"validar_{key}.py"]:
            errors.append(f"Validator filter {key} selects {sorted(hits)}")
    if Counter(matrix("group")) != Counter(groups.keys()):
        errors.append("Workflow pytest group matrix differs from the registry")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"OK: {len(validators)} validators and {len(pytest_files)} pytest files assigned exactly once.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
