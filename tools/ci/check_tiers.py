#!/usr/bin/env python
"""Check complete, unique test coverage and the slow workflow matrices."""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def collected(file, *arguments):
    """Node ids pytest collects from one test file, optionally restricted by -k."""
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", str(ROOT / "tests" / file), *arguments],
                         capture_output=True, text=True, cwd=ROOT)
    return {line.strip() for line in out.stdout.splitlines() if "::" in line}


def shard_errors(tiers, groups, workflow_groups):
    """A sharded test must run exactly once over its shard groups, and the file's other tests exactly once in the
    group that lists the file: every collected test id, and every archive index, is covered once."""
    errors = []
    shards = {k: v for k, v in tiers.get("pytest_shards", {}).items() if not k.startswith("_")}
    names = [n for spec in shards.values() for n in spec["groups"]]
    if len(names) != len(set(names)) or set(names) & set(groups):
        errors.append(f"Shard group names must be unique and distinct from the plain groups: {names}")
    if Counter(workflow_groups) != Counter([*groups, *names]):
        errors.append("Workflow pytest group matrix differs from the registry groups plus the shard groups")
    sys.path.insert(0, str(ROOT / "tests"))
    sys.path.insert(0, str(ROOT))
    from v2_parity_cases import archives, shard_selected
    total = len(archives())
    for file, spec in shards.items():
        if sum(file in members for members in groups.values()) != 1:
            errors.append(f"Sharded file {file} must be listed in exactly one plain group (it runs the other tests)")
        count = len(spec["groups"])
        if count < 2:
            errors.append(f"{file}: a shard list needs at least two groups")
        source = (ROOT / "tests" / file).read_text(encoding="utf-8")
        if not all(token in source for token in (spec["shard_var"], spec["count_var"], "shard_selected", spec["test"])):
            errors.append(f"{file} does not read {spec['shard_var']}/{spec['count_var']} in {spec['test']}")
        for index in range(total):
            hits = [s for s in range(count) if shard_selected(index, s, count)]
            if len(hits) != 1:
                errors.append(f"{file}: archive {index} runs in shards {hits}, not exactly once")
        whole = collected(file)
        only = collected(file, "-k", spec["test"])
        rest = collected(file, "-k", f"not {spec['test']}")
        if not only or only & rest or only | rest != whole:
            errors.append(f"{file}: -k split of {spec['test']} does not partition the collected tests "
                          f"({len(only)} + {len(rest)} against {len(whole)})")
    return errors


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
    errors.extend(shard_errors(tiers, groups, matrix("group")))
    if errors:
        print("\n".join(errors))
        return 1
    shards = [k for k in tiers.get("pytest_shards", {}) if not k.startswith("_")]
    print(f"OK: {len(validators)} validators and {len(pytest_files)} pytest files assigned exactly once; "
          f"{len(shards)} sharded files cover every test and archive exactly once.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
