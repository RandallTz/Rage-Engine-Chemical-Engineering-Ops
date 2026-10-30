# Shared code graph (Graphify)

[Graphify](https://github.com/Graphify-Labs/graphify) builds a structural graph of this repository's source code: modules, classes, functions and the `imports`, `calls`, `inherits` and `references` edges between them, each with its file and line. Claude, Codex and Gemini query the same graph, so every agent starts from one map of who depends on what instead of re-deriving it with broad searches. User decision `dec-graphify` (29 October 2026) in `docs/engine/project-board.json`.

The graph is a navigation aid. It never replaces the project board, the Checklist, `docs/engine/engine-map.md` or any canonical document, and it never stands in for reading the code an agent is about to change.

## Configuration

| Choice | Value | Why |
|---|---|---|
| Version | `graphifyy==0.9.90`, installed with pipx | Pinned; upgrade deliberately and re-run the checks below. The PyPI name has two `y`; other `graphify*` packages are unrelated |
| Scope | Code only (`--code-only`), no LLM backend | Parsing is local and deterministic; no code or documentation leaves the machine and no API key is needed |
| Exclusions | `.graphifyignore` plus `.gitignore` | JSON data, frozen examples, QA captures, `archive/`, packaging and build outputs add noise, not structure |
| Output | `graphify-out/`, git-ignored | Each agent rebuilds it locally; it is a cache, not a document, and its `GRAPH_REPORT.md` is not a canonical report |
| Hooks | None | No Claude/Gemini tool hooks and no git hooks. Agents query the graph deliberately; the deduction rules require reading the real expressions |

## Install (once per machine)

```bash
python -m pip install --user pipx
```

```bash
PIPX_HOME="$HOME/.local/pipx" PIPX_BIN_DIR="$HOME/.local/bin" python -m pipx install "graphifyy==0.9.90"
```

`$HOME/.local/bin` must be on the user `PATH`. On Windows, keep `PIPX_HOME` outside `AppData`: the Claude desktop app virtualizes `AppData`, so a venv created there from Claude is invisible to Codex and Gemini.

Register the assistant skills (user-level, nothing is written to the repository):

```bash
graphify install --platform claude
```

```bash
graphify install --platform codex
```

```bash
graphify install --platform gemini
```

Do not run `graphify claude install`, `graphify codex install`, `graphify gemini install` or `graphify hook install`: they rewrite `CLAUDE.md`, `AGENTS.md` or `GEMINI.md` and register hooks. The project's agent instructions live only in `AGENTS.md`, by exact edit.

## Build and refresh

From the repository root:

```bash
GRAPHIFY_BACKEND=none graphify extract . --code-only
```

```bash
GRAPHIFY_BACKEND=none graphify cluster-only . --no-label
```

After code changes, `graphify update .` re-extracts only the changed files (no LLM). Add `--force` after deleting or moving modules, because a rebuild with fewer nodes is otherwise refused. The other agent may have edited files since your last build: refresh before relying on the graph.

## Use

| Question | Command |
|---|---|
| What depends on this file or symbol (before claiming or changing it) | `graphify affected "core/compilador/derived.py" --depth 1` |
| What a symbol calls and who calls it, with file and line | `graphify explain "leer_modelo_comun()"` |
| How two symbols connect | `graphify path "A" "B"` (add `--undirected` if no directed path) |
| Architectural hubs | `graphify god-nodes --top 10` |
| Keyword exploration | `graphify query "…" --budget 1500` |

Set `GRAPHIFY_QUERY_LOG_DISABLE=1` to keep queries out of `~/.cache/graphify-queries.log`.

## Verified behavior and limits (29 October 2026, version 0.9.90)

- The build covers 602 code files: 7,924 nodes, 22,053 edges and 242 communities, in under a minute.
- `affected` on `core/compilador/derived.py` lists its real importers (`backend/api_modelo.py`, `core/compilador/compilador.py`, `core/compilador/report.py`, the F3 and U1 tests) with line numbers. A plain `grep` returns mostly copies under git-ignored `.tmp/`.
- `explain` returns `EXTRACTED` edges with file and line. Treat `INFERRED` edges as hints to verify.
- There are no edges across the HTTP boundary. Frontend `fetch` calls do not link to the FastAPI routes in `backend/`; for those, search the route path.
- `query` matches keywords, not meaning. A conceptual question ("how is the UNIFAC activity computed") returns test helpers first. Prefer `affected`, `explain` and `path` once you know a symbol name.
- The graph sees only what is on disk when it was built. Deleted or renamed modules disappear only after `graphify update . --force`.
