"""Phase 3 of the repository cleanup: move the documents to their English paths.

Applied on 2026-10-19 (75 documents). Kept as the record of the move table; rerunning it finds nothing to move.

Moves each document with `git mv` and rewrites every reference to it in the
same pass, so that no link breaks:

- Markdown links `[text](target)`: resolved from the linking file's old
  folder, mapped through the move table, and written again relative to the
  file's new folder (this also fixes the links *inside* the moved files).
- Path mentions (`docs/CAPA_TERMODINAMICA.md`, `../frontend/MAPA_MOTOR.md`):
  kept in the same style, relative or from the repository root.
- Bare file names (`ARQUITECTURA_MOTOR.md §2`): replaced by the new path from
  the root, but only for names that are unique among the moved files.

Only files that are safe to edit are rewritten: tracked files with no
uncommitted changes, plus the cleanup's own files. Files that carry someone
else's uncommitted work, and the examples and fixtures whose bytes the tests
compare, are left alone; their references are reported instead.

Usage:
    python tools/repo_cleanup/move_docs.py            dry run: prints the table and every change outside .md files
    python tools/repo_cleanup/move_docs.py --apply    performs the moves and the rewrites
    python tools/repo_cleanup/move_docs.py --rewrite-only DIR   rewrites references in DIR (e.g. agent memory) without moving
"""

from __future__ import annotations

import os
import posixpath
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import inventory  # noqa: E402  (glossary and name translation)

EXPLICIT = {
    "ARQUITECTURA_MOTOR.md": "ARCHITECTURE.md",
    "ARQUITECTURA_INTEGRACION_MULTIFISICA.md": "docs/history/multiphysics-integration-architecture.md",
    "frontend/ARQUITECTURA_INTEGRACION_MULTIFISICA.md": "docs/history/frontend/multiphysics-integration-architecture.md",
    "roadmap.md": "docs/history/build-log.md",
    # The numbered guides (docs/01-…15-*.md) stay for now: the app's method cards and the home page link to them
    # by name (frontend/app/components/metodos.ts, frontend/app/page.tsx), and the home page carries someone
    # else's uncommitted redesign. They move with that page once it is committed.
    "frontend/PRUEBAS_OLLAS_SIN_RESULTADO_IMPUESTO.md": "docs/history/frontend/pot-tests-without-imposed-result.md",
    "docs/ARTICULO_CIENTIFICO_ADIMENSIONALIZACION.md": "docs/papers/nondimensionalization-paper.md",
    "docs/ARTICULO_CIENTIFICO_ADIMENSIONALIZACION.tex": "docs/papers/nondimensionalization-paper.tex",
    "docs/AUDITORIA_MOTOR_2026_10_11.md": "docs/history/audits/engine-audit-2026-10-11.md",
    "docs/BATERIA_MULTIFISICA.md": "docs/engine/multiphysics-battery.md",
    "docs/CAPA_TERMODINAMICA.md": "docs/contracts/thermodynamic-layer.md",
    "docs/CONSOLIDACION_MULTIFASICA.md": "docs/engine/multiphase-consolidation.md",
    "docs/CONTRATO_MODELO_COMUN.md": "docs/contracts/common-model.md",
    "docs/CORTE_VERTICAL.md": "docs/engine/vertical-slice.md",
    "docs/DISENO_FRONTERA_ABIERTA_AGUA_AIRE.md": "docs/engine/open-boundary-water-air-design.md",
    "docs/FORMATO_RESULTADOS.md": "docs/contracts/results-format.md",
    "docs/MOTOR_BALANCES.md": "docs/engine/balance-engine.md",
    "docs/MOTOR_CATALOGO_PROPIEDADES.md": "docs/engine/property-catalog.md",
    "docs/MOTOR_DIAGRAMAS_EQUILIBRIO.md": "docs/engine/equilibrium-diagrams.md",
    "docs/MOTOR_ENSAMBLAJE_DINAMICO.md": "docs/engine/dynamic-assembly.md",
    "docs/MOTOR_EQUILIBRIO_MULTIFASICO.md": "docs/engine/multiphase-equilibrium.md",
    "docs/MOTOR_TERMODINAMICA_H0_H1.md": "docs/engine/thermodynamics-h0-h1.md",
    "docs/MOTOR_TERMODINAMICA_H3.md": "docs/engine/thermodynamics-h3.md",
    "docs/MOTOR_TERMODINAMICA_N_COMPONENTES.md": "docs/engine/thermodynamics-n-components.md",
    "docs/MOTOR_UNIFAC.md": "docs/engine/unifac.md",
    "docs/SERVICIO_UNIDADES.md": "docs/contracts/units-service.md",
    "docs/archivo/adimensionalizacion-2026-10-18/LEEME.md": "docs/history/archive/nondimensionalization-2026-10-18/README.md",
    "docs/archivo/adimensionalizacion-gemini-2026-10-17/LEEME.md": "docs/history/archive/nondimensionalization-gemini-2026-10-17/README.md",
    "frontend/ACOPLAMIENTO_MATERIA_MOTOR.md": "docs/engine/matter-coupling.md",
    "frontend/ADIMENSIONALIZACION_ALCANCE.md": "docs/nondimensionalization/scope.md",
    "frontend/CHECKLIST_MOTOR.md": "docs/engine/engine-checklist.md",
    "frontend/CONTINUIDAD_CLAUDE_ADIMENSIONALIZACION.md": "docs/nondimensionalization/continuity.md",
    "frontend/CONTRATO_NUCLEO_ADIMENSIONALIZACION.md": "docs/contracts/nondimensionalization-core.md",
    "frontend/DECISION_COMPONENTES_PUERTOS_Y_FUENTES.md": "docs/engine/decision-components-ports-sources.md",
    "frontend/DEFINICION_VOLUMEN_CONTROL.md": "docs/engine/control-volume-definition.md",
    "frontend/FUNDAMENTO_ENERGIA_MOTOR.md": "docs/engine/energy-foundation.md",
    "frontend/HOJAS_PRUEBA_MATERIA.md": "docs/engine/matter-test-sheets.md",
    "frontend/HOJAS_PRUEBA_MULTICOMPONENTE.md": "docs/engine/multicomponent-test-sheets.md",
    "frontend/MAPA_MOTOR.md": "docs/engine/engine-map.md",
    "frontend/MOTOR_ECUACIONES_FUNDAMENTALES.md": "docs/engine/fundamental-equations.md",
    "frontend/REFINAMIENTO_ECUACIONES_ENERGIA.md": "docs/engine/energy-equations-refinement.md",
    "frontend/ROADMAP_MOTOR_MULTIFISICO.md": "docs/engine/multiphysics-roadmap.md",
    "frontend/SOLVER_HOJAS_MOTOR.md": "docs/engine/sheet-solver.md",
    "frontend/UI_BALANCES_MOTOR.md": "docs/engine/balances-ui.md",
}
# Dated hand-off and history documents in frontend/: renamed word by word, moved to docs/history/frontend/.
HISTORY_FRONTEND = re.compile(r"^frontend/(AUDITORIA|CONTRATO_CLAUDE|COORDINACION|CORRECCIONES|ENCARGO|ENTREGA|INCIDENCIA|"
                              r"INTEGRACION|PLAN|PREPARACION|PRUEBAS|REVISION)_[A-Z0-9_]+\.md$")
STAY = {"README.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md", "docs/README.md", "frontend/README.md",
        "frontend/AGENTS.md", "frontend/CLAUDE.md"}
OWN_UNTRACKED = ("tools/repo_cleanup/", "docs/repository-cleanup/")
# Fixtures are compared byte for byte. The checklist download keeps a file name, not a path (set by hand).
NO_REWRITE = re.compile(r"^(tests/fixtures|frontend/app/checklist/(page\.tsx|documento/route\.ts))")
TEXT_EXT = {".md", ".tex", ".py", ".ts", ".tsx", ".mjs", ".js", ".yml", ".yaml", ".ps1", ".css", ".txt", ".json"}
LINK = re.compile(r"(\]\()([^)\s]+)((?:\s+\"[^\"]*\")?\))")
MENTION = re.compile(r"(?<![\w/.\-\]\[:])((?:\.{1,2}/)*(?:[\w.\-][\w.\-\[\]]*/)+[\w.\-]+\.(?:md|tex))\b")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.splitlines()


def history_name(path: str) -> str:
    name = Path(path).stem
    unknown = inventory.Counter()
    new = inventory.restyle(name, inventory.translate_words(inventory.words(name), unknown))
    assert not unknown, (path, unknown)
    return f"docs/history/frontend/{new}.md"


def move_table():
    tracked = set(git("ls-files"))
    dirty = {l[3:] for l in git("status", "--porcelain=v1") if not l.startswith("??")}
    table = {}
    for f in sorted(tracked):
        if f in STAY or f in dirty:
            continue
        if f in EXPLICIT:
            table[f] = EXPLICIT[f]
        elif HISTORY_FRONTEND.match(f):
            table[f] = history_name(f)
    for old, new in table.items():
        assert not (ROOT / new).exists(), f"target exists: {new}"
    assert len(set(table.values())) == len(table), "two files map to the same target"
    return table, tracked, dirty


def rel(from_dir: str, to: str) -> str:
    r = posixpath.relpath(to, from_dir or ".")
    return r


def norm(p: str) -> str:
    return posixpath.normpath(p).lstrip("./") if not p.startswith("../") else posixpath.normpath(p)


class Rewriter:
    def __init__(self, table):
        self.table = table
        names = {}
        for old in table:
            names.setdefault(Path(old).name, []).append(old)
        self.bare = {n: v[0] for n, v in names.items() if len(v) == 1 and n not in ("README.md", "LEEME.md")}
        self.bare_re = re.compile(r"(?<![\w/.\-])(" + "|".join(re.escape(n) for n in sorted(self.bare, key=len, reverse=True)) + r")(?![\w\-])")

    def target(self, old_dir: str, t: str):
        """Resolve a reference; returns (repo path, style) or None when it is not a repo file."""
        path = t.split("#", 1)[0]
        if not path or re.match(r"^[a-z][a-z0-9+.\-]*:", path) or path.startswith("/"):
            return None
        a = posixpath.normpath(posixpath.join(old_dir, path)) if old_dir else posixpath.normpath(path)
        if (ROOT / a).exists() or a in self.table:
            return a, "relative"
        b = posixpath.normpath(path)
        if (ROOT / b).exists() or b in self.table:
            return b, "root"
        return None

    def new_ref(self, old_dir, new_dir, t):
        r = self.target(old_dir, t)
        if r is None:
            return t
        a, style = r
        anchor = t[len(t.split("#", 1)[0]):]
        dest = self.table.get(a, a)
        if style == "relative":
            out = rel(new_dir, dest)
        else:
            if dest == a:
                return t
            out = dest
        if out == t.split("#", 1)[0] and not anchor:
            return t
        return out + anchor

    def rewrite(self, f_old: str, f_new: str, text: str, markdown: bool):
        old_dir, new_dir = posixpath.dirname(f_old), posixpath.dirname(f_new)
        changes = []

        def link(m):
            t = m.group(2)
            n = self.new_ref(old_dir, new_dir, t)
            if n != t:
                changes.append((t, n))
            return m.group(1) + n + m.group(3)

        def mention(m):
            t = m.group(1)
            n = self.new_ref(old_dir, new_dir, t)
            if n != t:
                changes.append((t, n))
            return n

        def bare(m):
            n = self.table[self.bare[m.group(1)]]
            changes.append((m.group(1), n))
            return n

        out = []
        for line in text.split("\n"):
            if markdown:
                parts = re.split(r"(\]\([^)\s]+(?:\s+\"[^\"]*\")?\))", line)
                for i, p in enumerate(parts):
                    if i % 2:
                        parts[i] = LINK.sub(link, p)
                    else:
                        p = MENTION.sub(mention, p)
                        parts[i] = self.bare_re.sub(bare, p) if self.bare else p
                line = "".join(parts)
            else:
                line = MENTION.sub(mention, line)
                if self.bare:
                    line = self.bare_re.sub(bare, line)
            out.append(line)
        return "\n".join(out), changes


def editable(f, tracked, dirty):
    if NO_REWRITE.match(f):
        return False
    if f in tracked:
        return f not in dirty
    return f.startswith(OWN_UNTRACKED)


def main():
    apply = "--apply" in sys.argv
    table, tracked, dirty = move_table()
    rw = Rewriter(table)

    if "--rewrite-only" in sys.argv:
        d = Path(sys.argv[sys.argv.index("--rewrite-only") + 1])
        for p in sorted(d.glob("*.md")):
            text = p.read_text(encoding="utf-8")
            new, ch = rw.rewrite("", "", text, True)
            # Outside the repository, every reference is written from the repository root.
            if ch:
                print(f"{p.name}: {len(ch)} references")
                if apply:
                    p.write_text(new, encoding="utf-8", newline="")
        return

    files = sorted(set(git("ls-files")) | set(git("ls-files", "-o", "--exclude-standard")))
    files = [f for f in files if Path(f).suffix in TEXT_EXT and not re.search(r"(^|/)(node_modules|\.next|\.tmp)/", f)
             and (ROOT / f).exists()]
    rewrites, skipped = {}, {}
    for f in files:
        text = (ROOT / f).read_text(encoding="utf-8", errors="strict") if (ROOT / f).stat().st_size < 4_000_000 else ""
        new, ch = rw.rewrite(f, table.get(f, f), text, f.endswith(".md"))
        if not ch and f not in table:
            continue
        if editable(f, tracked, dirty) or f in table:
            rewrites[f] = (new, ch)
        else:
            skipped[f] = ch

    print(f"{len(table)} documents to move:")
    for o, n in table.items():
        print(f"  {o} -> {n}")
    print(f"\n{sum(1 for v in rewrites.values() if v[1])} files get rewritten references "
          f"({sum(len(v[1]) for v in rewrites.values())} references).")
    print("\nChanges outside Markdown (review these):")
    for f, (_, ch) in rewrites.items():
        if not f.endswith(".md"):
            for a, b in ch:
                print(f"  {f}: {a} -> {b}")
    print(f"\nNot rewritten ({len(skipped)} files with someone else's uncommitted work, examples or fixtures):")
    for f, ch in skipped.items():
        print(f"  {f}: " + ", ".join(sorted({a for a, _ in ch})))

    if not apply:
        return
    for o, n in table.items():
        (ROOT / n).parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["git", "mv", o, n], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    for f, (new, ch) in rewrites.items():
        dest = ROOT / table.get(f, f)
        raw = dest.read_bytes().decode("utf-8")
        if new != raw.replace("\r\n", "\n") and "\r\n" in raw:
            new = new.replace("\r\n", "\n").replace("\n", "\r\n")
        if new != raw:
            with open(dest, "w", encoding="utf-8", newline="") as fh:
                fh.write(new)
    print("\napplied")


if __name__ == "__main__":
    main()
