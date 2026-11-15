#!/usr/bin/env python
"""Run validation scripts and pytest files, including documented quarantines.

Use --tier fast or --tier slow, optionally --group NAME for a slow pytest
group, --list to inspect the selection, and -v for full output. Positional
filters match suite filenames. Tier membership is checked by check_tiers.py.

A heavy test split over several CI groups is registered under pytest_shards: the
group that lists its file runs the file's other tests, and each shard group runs
only that test as shard i of n (environment variables read by the test). Runs
without --group, and local full runs, are not sharded.
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
    parser.add_argument("--stream", action="store_true",
                        help="Print each suite's output while it runs (pytest -s), so a job cancelled at its time "
                             "limit still shows the case it was in")
    args = parser.parse_args()
    tiers = json.loads(REGISTRY.read_text(encoding="utf-8"))
    slow = set(tiers["slow"])
    groups = tiers["pytest_slow_groups"]
    shards = {k: v for k, v in tiers.get("pytest_shards", {}).items() if not k.startswith("_")}
    shard_groups = {name: (file, spec, i) for file, spec in shards.items() for i, name in enumerate(spec["groups"])}
    if args.group and (args.tier != "slow" or args.group not in {*groups, *shard_groups}):
        parser.error("--group requires --tier slow and a registered group")
    all_suites = sorted([*TESTS.glob("validar_*.py"), *TESTS.glob("test_*.py")])
    pytest_slow = {name for group in groups.values() for name in group}
    extra = {}                           # suite name -> (pytest arguments, environment) of this group only
    if args.group:
        if args.group in shard_groups:
            file, spec, index = shard_groups[args.group]
            selected = {file}
            extra[file] = (["-k", spec["test"]],
                           {spec["shard_var"]: str(index), spec["count_var"]: str(len(spec["groups"]))})
        else:
            selected = set(groups[args.group])
            for file, spec in shards.items():
                if file in selected:
                    extra[file] = (["-k", f"not {spec['test']}"], {})
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
            note = f"  {' '.join(extra[suite.name][0])} {extra[suite.name][1] or ''}".rstrip() if suite.name in extra else ""
            print(f"{'slow' if suite.name in slow | pytest_slow else 'fast'}  {suite.name}{note}")
        return 0
    known = {k: v for k, v in tiers.get("known_failing", {}).items() if not k.startswith("_")}
    # Several suites write under the git-ignored .tmp/ folder, absent from a clean clone.
    (ROOT / ".tmp").mkdir(exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    failures, quarantined = [], []
    started = time.monotonic()
    print(f"Running {len(all_suites)} suites ({args.tier or 'all'})", flush=True)
    for suite in all_suites:
        start = time.monotonic()
        arguments, suite_env = extra.get(suite.name, ([], {}))
        command = ([sys.executable, "-m", "pytest", "-q", str(suite), *arguments] if suite.name.startswith("test_")
                   else [sys.executable, str(suite)])
        if args.stream:
            if suite.name.startswith("test_"):
                command.insert(command.index("-q") + 1, "-s")
            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                    errors="replace", cwd=ROOT, env={**env, **suite_env})
            lines = []
            for line in proc.stdout:
                lines.append(line)
                print("    . " + line.rstrip(), flush=True)
            result = subprocess.CompletedProcess(command, proc.wait(), "".join(lines), "")
        else:
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT,
                                    env={**env, **suite_env})
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
        if (args.verbose or not ok) and not args.stream:
            output = (result.stdout + "\n" + result.stderr).strip().splitlines()
            print("\n".join("    | " + line for line in (output if args.verbose else output[-40:])), flush=True)
    print(f"Finished in {time.monotonic() - started:.1f}s: {len(failures)} blocking failures, {len(quarantined)} quarantined failures.")
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
