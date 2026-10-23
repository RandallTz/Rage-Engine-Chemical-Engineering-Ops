"""Link checker for the repository's documents.

Checks two kinds of reference in every Markdown file (and, with --code, in
code comments and strings too):

- Markdown links `[text](target)` whose target is a relative path: the file
  (or folder) must exist, resolved from the linking file's folder.
- Plain mentions of a document path such as `docs/contracts/common-model.md`
  or `docs/engine/engine-map.md`: resolved from the repository root or from the
  file's folder; one of the two must exist.

Usage:
    python tools/repo_cleanup/check_links.py               report broken references
    python tools/repo_cleanup/check_links.py --code        also scan .py/.ts/.tsx/.mjs files
    python tools/repo_cleanup/check_links.py --baseline F  write the broken list to F (one per line)
    python tools/repo_cleanup/check_links.py --against F   fail only on references not already in F

The exit code is 1 when there are broken references (new ones, with --against).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
SKIP = re.compile(r"(^|/)(node_modules|\.next|\.tmp)/")
LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# A path-looking token that ends in a document extension.
MENTION = re.compile(r"(?<![\w/.\-\]\[:])((?:\.{1,2}/)*(?:[\w.\-][\w.\-\[\]]*/)+[\w.\-]+\.(?:md|tex))\b")
CODE_EXT = {".py", ".ts", ".tsx", ".mjs", ".js"}


def files(code: bool):
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8").stdout.splitlines()
    for f in sorted(set(out)):
        if SKIP.search(f):
            continue
        p = Path(f)
        if p.suffix == ".md" or (code and p.suffix in CODE_EXT):
            if (ROOT / f).exists():
                yield f


def exists(base: Path, target: str) -> bool:
    target = unquote(target.split("#", 1)[0].split("?", 1)[0])
    if not target:
        return True
    if target.startswith("/"):
        return (ROOT / target.lstrip("/")).exists()
    return (base / target).exists()


def broken_in(f: str):
    path = ROOT / f
    text = path.read_text(encoding="utf-8", errors="ignore")
    base = path.parent
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        if path.suffix == ".md":
            for m in LINK.finditer(line):
                t = m.group(1)
                if re.match(r"^[a-z][a-z0-9+.\-]*:", t) or t.startswith("#") or t.startswith("<"):
                    continue
                if not exists(base, t):
                    found.append((n, t))
        for m in MENTION.finditer(line):
            t = m.group(1)
            if "://" in line[max(0, m.start() - 12):m.start()]:
                continue
            if not (exists(base, t) or exists(ROOT, t)):
                found.append((n, t))
    return sorted(set(found))


def main():
    code = "--code" in sys.argv
    baseline = None
    against = None
    if "--baseline" in sys.argv:
        baseline = Path(sys.argv[sys.argv.index("--baseline") + 1])
    if "--against" in sys.argv:
        against = set(Path(sys.argv[sys.argv.index("--against") + 1]).read_text(encoding="utf-8").splitlines())
    keys = []
    for f in files(code):
        for n, t in broken_in(f):
            keys.append((f, n, t))
    lines = [f"{f} -> {t}" for f, _, t in keys]
    if baseline:
        baseline.write_text("\n".join(sorted(set(lines))) + "\n", encoding="utf-8")
    new = [(f, n, t) for f, n, t in keys if against is None or f"{f} -> {t}" not in against]
    for f, n, t in new:
        print(f"{f}:{n}: {t}")
    label = "new broken references" if against is not None else "broken references"
    print(f"{len(new)} {label} ({len(keys)} in total)")
    sys.exit(1 if new else 0)


if __name__ == "__main__":
    main()
