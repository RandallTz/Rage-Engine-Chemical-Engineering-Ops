#!/usr/bin/env python
"""Run validation scripts and pytest files, including documented quarantines.

Use --tier fast or --tier slow, optionally --group NAME for a slow pytest
group, --list to inspect the selection, and -v for full output. Positional
filters match suite filenames. Tier membership is checked by check_tiers.py.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TESTS = ROOT / "tests"
REGISTRY = ROOT / "tools/ci/test_tiers.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filters", nargs="*")
    parser.add_argument("--tier", choices=("fast", "slow"))
    parser.add_argument("--group", help="Select one slow pytest group")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    tiers = json.loads(REGISTRY.read_text(encoding="utf-8"))
    slow = set(tiers["slow"])
    groups = tiers["pytest_slow_groups"]
    if args.group and (args.tier != "slow" or args.group not in groups):
        parser.error("--group requires --tier slow and a registered group")
    all_suites = sorted([*TESTS.glob("validar_*.py"), *TESTS.glob("test_*.py")])
    pytest_slow = {name for group in groups.values() for name in group}
    if args.group:
        selected = set(groups[args.group])
        all_suites = [s for s in all_suites if s.name in selected]
    elif args.tier == "fast":
        all_suites = [s for s in all_suites if s.name not in slow | pytest_slow]
    elif args.tier == "slow":
        all_suites = [s for s in all_suites if s.name in slow | pytest_slow]
    if args.filters:
        all_suites = [s for s in all_suites if any(f.lower() in s.name.lower() for f in args.filters)]
    if not all_suites:
        print("No suites selected.")
        return 1
    if args.list:
        for suite in all_suites:
            print(f"{'slow' if suite.name in slow | pytest_slow else 'fast'}  {suite.name}")
        return 0
    known = {k: v for k, v in tiers.get("known_failing", {}).items() if not k.startswith("_")}
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    failures, quarantined = [], []
    started = time.monotonic()
    print(f"Running {len(all_suites)} suites ({args.tier or 'all'})", flush=True)
    for suite in all_suites:
        start = time.monotonic()
        command = [sys.executable, "-m", "pytest", "-q", str(suite)] if suite.name.startswith("test_") else [sys.executable, str(suite)]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT, env=env)
        ok = result.returncode == 0
        status = "PASS" if ok else ("QUARANTINED" if suite.name in known else "FAIL")
        print(f"[{status}] {suite.name} {time.monotonic() - start:.1f}s", flush=True)
        if suite.name in known:
            if ok:
                print("    Quarantined suite passed; review its quarantine.", flush=True)
            else:
                quarantined.append(suite.name)
                print(f"    Reason: {known[suite.name]}", flush=True)
        elif not ok:
            failures.append(suite.name)
        if args.verbose or not ok:
            output = (result.stdout + "\n" + result.stderr).strip().splitlines()
            print("\n".join("    | " + line for line in (output if args.verbose else output[-40:])), flush=True)
    print(f"Finished in {time.monotonic() - started:.1f}s: {len(failures)} blocking failures, {len(quarantined)} quarantined failures.")
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
