# Repository cleanup and move to English

Status: **phase 3 documentation and final battery regeneration complete** (2026-10-19), with the pre-existing catalog-test failure recorded below. Phase 1 wrote the inventory and the target structure; phase 2 moved the untracked screenshots and logs out of `frontend/`; phase 3 moved and translated the documentation (§6). Phase 4 (tests, scripts, evidence and examples) has not started.

This folder holds the plan for making the repository clean and English. It has three pieces:

- this plan;
- [`inventory.csv`](inventory.csv): one row per file with its proposed destination;
- the script that builds the inventory, [`tools/repo_cleanup/inventory.py`](../../tools/repo_cleanup/inventory.py).

The user decided two things:

1. Folders, documents and files should look professional and tidy.
2. Every document and every file name should be in English.

The constraint is the same as always: **nothing may break**.

## 1. Rules for every later phase

1. **One phase, one branch, small commits.** Each commit moves one coherent group, so it is easy to review and to revert.
2. **Moves are `git mv`, never delete-and-create**, so `git log --follow` keeps each file's history.
3. **Every reference is updated in the same commit** as the move. That covers imports, `package.json` scripts, `run_tests.py`, the CI workflow (`.github/workflows/validacion.yml`), Markdown links, and the paths that verifiers and readers build by prefix.
4. **All suites run before each commit:**
   - `python run_tests.py`;
   - `npm run build` and `npm run test:motor-fundamental` in `frontend/`;
   - the Engine verifiers;
   - a link check over the docs.

   A phase that cannot keep them green stops and reports.
5. **No one else's uncommitted work gets mixed in.** Phases that touch the laboratorio, the flowsheet or the app shell wait until that work is committed and the owner (Codex or the user) agrees. That work is about 630 files at the moment.
6. **External contracts change only with versioning.** These are the HTTP routes, the JSON `formato` names, localStorage keys and the URLs of the pages. See §5.

## 2. What the inventory found

The script lists 1,870 files: tracked, untracked, and ignored files that sit in working folders. It leaves out `node_modules/`, `.next/` and `.tmp/`.

| Category | Files | What it is |
|---|---:|---|
| code | 652 | Python, TypeScript, CSS and scripts |
| example | 589 | `docs/ejemplos/` requests and responses (251 are untracked studies) |
| generated | 178 | screenshots (`preview-*.png`, `verificacion-*.png`) and logs in `frontend/`; the screenshots are already ignored by git |
| test | 172 | `tests/validar_*.py`, `frontend/verificar_*.mjs` |
| evidence | 95 | `frontend/qa_*_2026_10_*` folders of dated QA output |
| doc-current | 72 | documents that describe the system as it is |
| doc-history | 70 | deliveries, integrations, incidents, assignments, hand-offs, audits, plans |
| other | 39 | configs, JSON data, `.gitignore`, … |
| local-reference | 3 | Perry's handbook and the multiphysics PDFs (ignored, local only) |

The main sources of clutter:

- **`frontend/` root** has 378 entries:
  - 93 Markdown documents, nearly all hand-off or history notes (`ENTREGA_*`, `INTEGRACION_*`, `SIGUIENTE_CLAUDE_*`, …);
  - 167 screenshots and 6 logs;
  - 11 `qa_*` folders;
  - 109 verifiers that sit next to `package.json`.
- **`docs/ejemplos/`** has 428 files in a flat list, mixing studies, lab, Engine and nondimensionalization.
- **The repository root** mixes:
  - the current architecture (`ARQUITECTURA_MOTOR.md`, now `ARCHITECTURE.md`);
  - an older one (`ARQUITECTURA_INTEGRACION_MULTIFISICA.md/.pdf`, duplicated in `frontend/`);
  - a 2025 `roadmap.md` (the build log, now `docs/history/build-log.md`);
  - three loose `ejemplo_*.py` scripts and a skeleton `main.py`;
  - `api/` (the first simulator), `archive/` (Yaws ETL) and `books/`.
- **Names are in Spanish** almost everywhere: files, folders, page URLs, HTTP routes, JSON formats, identifiers and UI text.

## 3. Target structure

```
README.md                 what the project is, how to run it, where things are
ARCHITECTURE.md           was ARQUITECTURA_MOTOR.md (the document that rules)
AGENTS.md  CLAUDE.md  GEMINI.md
requirements.txt  run_tests.py
backend/                  FastAPI app (package name kept: `backend.main:app`)
core/                     science: model, balances, compiler, solvers, thermodynamics, nondimensionalization
thermodynamics/           thermo providers (to be merged or renamed; see §6, decision D4)
config/
examples/                 runnable example scripts (was ejemplo_*.py and main.py)
legacy/                   api/ (first simulator) and archive/ (Yaws ETL), kept for reference
packaging/                was empaquetado/ (desktop executable)
tools/                    repository tooling (this inventory, link checker, …)
tests/
  validate_*.py           was validar_*.py
  fixtures/assembly/      was fixtures_ensamblaje/
docs/
  README.md               index of the documentation
  contracts/              common model, thermodynamic layer, units, results format, nondimensionalization core
  engine/                 balance engine, multiphysics battery, engine map, roadmap, checklist, UNIFAC, …
  nondimensionalization/  scope and continuity
  guides/                 the numbered method guides (01-architecture … 15-lab)
  papers/                 the nondimensionalization paper (.md, .tex)
  examples/               was docs/ejemplos/, grouped: engine/, engine-unifac/, studies/, lab/, nondimensionalization/, …
  history/                deliveries, integrations, incidents, audits, QA evidence, archived code; read-only
  repository-cleanup/     this plan
frontend/
  README.md  AGENTS.md  CLAUDE.md  package.json  configs
  app/                    Next.js routes (folder names are URLs; see §5)
  engines/                was motores/ (common-model and results clients)
  shared/                 was componentes/ (shared charts)
  verification/           was verificar_*.mjs at the root
  scripts/                sync, prepare and build helpers
  public/
```

`inventory.csv` gives each file its destination in this tree, plus two counts:

- **references:** how many other files mention it. This is an upper bound, because common stems such as `modelo` match ordinary words.
- **status:** tracked, modified, untracked or ignored.

## 4. Naming conventions

| Kind | Convention | Example |
|---|---|---|
| Documents | `kebab-case.md`; `README.md`, `AGENTS.md`, `ARCHITECTURE.md` in capitals | `docs/contracts/common-model.md` |
| Python modules and packages | `snake_case` | `core/balances/generator.py` |
| React components | `PascalCase.tsx` | `SavedSheet.tsx` |
| Other TypeScript modules | `camelCase.ts` | `equationPlacement.ts` |
| Node scripts and verifiers | `snake_case.mjs` with a verb | `verify_resolver_engine.mjs` |
| Python suites | `validate_<topic>.py` | `validate_balance_engine.py` |
| Examples | `<engine>-<case>-request.json` / `-response.json` | `engine-unifac-heating-2-request.json` |
| Dated history | `<topic>-YYYY-MM-DD` | `history/qa/multiphase-2026-10-15/` |

The script translates names word by word with a reviewed glossary (`GLOSSARY` in the script). It reports any word it does not know, so nothing is translated by guesswork. When word-by-word order reads badly (`hojasMotor` → `sheetsEngine`), an explicit override fixes it (`engineSheets`). The proposals for code files are a draft: each one is reviewed when its package moves.

Some recurring terms are fixed now, so every phase uses the same word:

| Spanish | English |
|---|---|
| motor | engine |
| hoja | sheet |
| supuesto | assumption |
| balance de materia | mass balance (`matter` in code where it already exists) |
| ensamblaje | assembly |
| cierre | closure |
| adimensionalización | nondimensionalization |
| laboratorio | lab |
| mesa | bench |
| estudio | study |
| recorrido | walkthrough or derivation, depending on context |
| corriente | stream |
| volumen de control | control volume |

## 5. What "everything in English" touches, by layer and risk

| Layer | What | Risk | How |
|---|---|---|---|
| L1 | **Document contents and names** | Low: only links break | Translate and rename; a link checker in `tools/` proves no link is dead |
| L2 | **Files nothing imports**: verifiers, Python suites, scripts, examples, QA evidence, history | Medium: `package.json`, `run_tests.py`, CI, readers that walk `docs/ejemplos/` by prefix, tests that open fixtures by path | Move by group; update every caller in the same commit |
| L3 | **Module and file names** in `core/`, `backend/`, `frontend/app`, `frontend/motores` | High: every import, plus Codex's uncommitted work in the same files | Package by package, after the other work is committed; the build and all suites run on each commit |
| L4 | **Identifiers in code** (`hojasMotor()`, `volumenes`, `resolverHoja`) | Very high and very large (thousands of names) | Not part of this cleanup by default; at most, new code in English from now on (decision D2) |
| L5 | **External contracts**: HTTP routes (`/modelo/resolver`, `/api/adimensionalizacion`, 46+ routes), JSON formats and fields (`rage.modelo`, `volumenes`, `adimensionalizacion.solicitud`), localStorage keys (`rage.versiones.*`, `lab-preparacion-v1`), page URLs (`/motor`, `/laboratorio`) | Breaks saved user data, shared links, the desktop executable and the deployed frontend | Only with a new version that keeps the old one readable (aliases, readers for both, redirects); a phase of its own (decision D3) |
| — | **UI text** shown to the user | Product decision, not cleanup | Stays Spanish unless decided otherwise (decision D1) |

## 6. Phases after this one

Each phase lists its prerequisites and its proof that nothing broke.

1. **Phase 2 — remove clutter that git does not track (done 2026-10-19).**
   - Moved, not deleted: 147 screenshots and 6 server logs left `frontend/` for `.tmp/cleanup-2026-10-19/frontend/`. None was tracked by git. `MANIFEST.json` in that folder lists each one, so any file can be put back at its old path.
   - `.gitignore` now ignores `.tmp/` (the root one and `frontend/.tmp/`) and loose `*.log` files at the root and in `frontend/`.
   - Left in place on purpose:
     - `frontend/tsconfig.tsbuildinfo`: TypeScript's build cache, already ignored, and rewritten on every build.
     - `frontend/qa-insercion-mesa.json`: Codex's QA input, cited by `frontend/INTEGRACION_INSERCION_MESA.md`. It moves with the other QA evidence in phase 4.
     - The screenshots inside the `qa_*` and `auditoria_experimentar_*` folders: they are evidence and move in phase 4.
   - Found on the way: nine verifiers (`verificar_incoherencias`, `_menu_fug`, `_ponchon`, `_reactor_termo`, `_redesign`, `_simulaciones`, `_topologia`, `_ui`, `_unidades_y_nombres`) write their screenshots into `frontend/`. Phase 4 points them at `.tmp/screenshots/`, so the clutter does not come back.
   - Some hand-off documents (`INTEGRACION_ENTREGA_22/24/27`, `INTEGRACION_INSERCION_MESA`, `DECISION_COMPONENTES_PUERTOS_Y_FUENTES`) name screenshots that were never in git. Those names were already dead links on any other checkout.
   - Proof: `git status` shows only the `.gitignore` change and the new files of this plan; no tracked file changed.
2. **Phase 3 — documentation (moved, translated and battery regenerated 2026-10-19).**
   - **Moved** with `git mv` (75 documents), by [`tools/repo_cleanup/move_docs.py`](../../tools/repo_cleanup/move_docs.py), which also rewrote every reference to them in the same pass: Markdown links (recomputed from each file's new folder), path mentions and bare file names, in docs, code comments, test headers and the backend's response strings.
     - `ARQUITECTURA_MOTOR.md` → `ARCHITECTURE.md`; `roadmap.md` → `docs/history/build-log.md`.
     - The current documents went to `docs/contracts/`, `docs/engine/`, `docs/nondimensionalization/` and `docs/papers/`; dated hand-off and history documents to `docs/history/` (`frontend/` ones to `docs/history/frontend/`), renamed but in their original Spanish (D5).
     - The backend's UNIFAC evidence text cites `docs/engine/unifac.md`; the example JSON that carries that text was rewritten the same way, so the generated and stored responses still match.
   - **Translated to English:** `ARCHITECTURE.md`, `AGENTS.md`, `README.md`, `docs/README.md` (now the index of the new layout), the five contracts, the 24 engine documents and the two nondimensionalization documents. The generator of `docs/engine/multiphysics-battery.md` writes English now. Sheet names, reasons and published field names stay as the Engine publishes them (D1, D3).
   - **Left for later, on purpose:**
     - The numbered method guides `docs/01-…15-*.md`: the app's method cards (`frontend/app/components/metodos.ts`) and the home page link to them by name, and the home page carries someone else's uncommitted redesign. They move to `docs/guides/` and to English with that page.
     - The papers (`docs/papers/`): moved, not translated; an English paper is a new piece of writing, not a translation pass.
     - `docs/contratos/`: TypeScript copies that verifiers compare byte for byte with the frontend's and that import `../../frontend/app/motor/` by relative path. They move with the code in phase 4/6.
     - `docs/auditoria_motor_2026_10_11/`: evidence written by `tests/auditoria_motor_acoplado.py` (uncommitted work). It moves with the QA evidence in phase 4.
     - Every document that carries someone else's uncommitted work: `docs/ENTREGA_LABORATORIO_CODEX.md`, `docs/PLAN_EJECUTABLE_WINDOWS.md` and the untracked `frontend/*.md`.
   - **Stale references left in other people's uncommitted files** (they are comments and prose; no test reads these documents at run time): `backend/main.py` (2 comments), `backend/trazabilidad.py`, `docs/ENTREGA_LABORATORIO_CODEX.md`, `frontend/INTEGRACION_INSERCION_MESA.md`, `frontend/PENDIENTES_BACKEND_CLAUDE.md`, `frontend/RECORRIDO_EXPERIMENTAR_2026_10_11.md`, `tests/validar_correcciones_auditoria.py`, `tests/validar_topologia_fronteras_fuentes.py`. Their owners should update the paths when they commit; [`tools/repo_cleanup/check_links.py`](../../tools/repo_cleanup/check_links.py) lists them.
   - **Proof:** the link checker finds no new broken reference outside those files and the move table itself; `tsc`, the contract-copy verifiers, `test:motor-fundamental` and the examples' sync checks pass; `python run_tests.py` passes 62 of 63 suites. The one failure is the known check in `validar_motor_catalogo.py` ("capacidades puntuales = las de F1 + la acetona"), whose F1 snapshot was overwritten on 16 October ([docs/engine/engine-map.md](../engine/engine-map.md) §5); it predates the cleanup.
   - **Final regeneration completed by Codex:** Claude's first battery regeneration crashed when it compared the new `campo.aux_*` budget integrals by position against the TS solver, which has no matching columns. On resuming, Codex confirmed the patch was saved, the generated report was still the old Spanish one, and no battery process remained active. A targeted run found that derived `observable.*` series also had no TS state columns, so excluding auxiliaries alone still crashed on the first energy sheet. The generator now selects only physical `campo.*` states, excludes `campo.aux_*`, and checks column counts, lengths and finite values before comparing. The 24 non-network sheets pass 46/46 checks (22 solved, two spatial cases explicitly unsupported).
     - The full `node verificar_bateria_multifisica.mjs` run completed with exit code 0: **79/79 checks**, **38/41 sheets solved**, one expected diagnostic rejection and two unsupported spatial cases. It regenerated [the battery report](../engine/multiphysics-battery.md) in English; all solved sheets match the current Engine within the declared tolerance.
     - Current-document link checks pass (38 files including this plan, zero broken references); all 153 moved screenshots/logs exist at the recovery-manifest destinations; TypeScript passes; `python tests/validar_motor_balances.py` passes 30 checks. Dollar-delimited mathematics is unchanged in all 33 moved current contract, engine and nondimensionalization documents. The refreshed inventory lists 1,720 files.
     - The full Python-suite result above (62/63) is Claude's recorded run; it was not rerun during this resumption. The pre-existing catalog snapshot failure remains explicitly open. Global link checking still reports historical, deferred and move-table references; the zero-broken-link result applies to the current entry/contract/engine/nondimensionalization documents and this plan, not the whole repository.
     - No phase-4 moves, engine-physics changes, commits or pushes were made during this resumption. The user's servers on 3000, 8004 and 8005 were left running; only Codex's incomplete battery run was stopped and restarted.
3. **Phase 4 — tests, scripts, evidence and examples (L2).**
   - `tests/validar_*` → `tests/validate_*`, updating the `run_tests.py` glob.
   - `frontend/verificar_*` → `frontend/verification/verify_*`. Relative imports change from `./app/…` to `../app/…`, and `package.json` and CI are updated.
   - `qa_*` → `docs/history/qa/`.
   - `docs/ejemplos/` → `docs/examples/<group>/`. The readers and generators that build these paths change in the same commit.
4. **Phase 5 — root and peripheral packages (L3, low fan-out).**
   - `ejemplo_*.py` and `main.py` → `examples/`; `api/` and `archive/` → `legacy/`; `empaquetado/` → `packaging/`.
   - Remove the duplicated multiphysics architecture.
   - Update the `/actualizar-ejecutable` skill and `packaging/` paths, then rebuild the executable to prove it.
5. **Phase 6 — module names, package by package (L3).**
   - Order: `core/` (pure science, imported by backend and tests), then `backend/`, then `frontend/motores` and `frontend/app/motor` and `adimensionalizacion`. The laboratorio and the flowsheet come last, with their owner.
   - Each package is one branch-sized step, with the build and every suite green.
6. **Phase 7 — external contracts (L5), only if decided.**
   - Versioned English routes and formats, with the Spanish ones kept as readable aliases.

### Owned-code English cleanup (29 October 2026)

The user assigned Codex the remaining English prose cleanup in `frontend/app/models/`, `core/compilador/`, `core/modelo/` and `core/mathematics/` under `clean-en`. This changes presentation and documentation, not numerical capability, solver admission or the Model → Transform → Solve → Results boundaries. The later module moves and versioned contract migration remain separate work.

- Translated comments, docstrings, reader/compiler diagnostics, structural-relation descriptions, method descriptions and generated result labels in `core/modelo/{__init__,adaptadores,lector,relaciones}.py` and `core/compilador/{__init__,compilador,explicito}.py`. An AST comparison against the pre-edit copies confirms only strings and comments changed in these seven source files.
- The audit found the newer mathematics code and authored Model UI prose already in English. `ModelWorksheet.tsx`, its layout, every frontend file and the mathematics kernel remain byte-identical to the start of this cleanup. `frontend/app/models/english.ts` intentionally retains Spanish lookup inputs for older stored documents; its display outputs are English.
- Existing Python APIs, persisted keys, enum values, route names, relation identities, symbolic formulas and published protocol fields remain unchanged. New identifiers introduced by this cleanup are English. Messages forwarded from services outside the four owned directories and user-authored names are not rewritten here. Claude's thermodynamics files, frozen M1-A/B/C inputs/references and F3 implementations remain untouched.
- Updated the two affected legacy verifiers, `tests/validar_modelo_comun.py` and `tests/validar_compilador_explicito.py`, to assert English diagnostics. The explicit verifier already had three stale Spanish assertions before this change (24/27 baseline); these now assert the existing English messages. The common-model verifier translates the archived relation descriptions in memory and still compares every field and ordering; no archived output is regenerated. The explicit verifier now accepts `--no-write` for read-only regression runs.
- Verification passed: TypeScript (`node node_modules/typescript/bin/tsc --noEmit` in `frontend`); scoped ESLint (`node node_modules/eslint/bin/eslint.js app/models`); `node frontend/verificar_physical_journals.mjs` (1,391 checks, 42 templates); `node frontend/verificar_equation_workbench.mjs` (11,655 rendered formulas); `python tests/validar_modelo_comun.py` (102 checks); `python tests/validar_compilador_explicito.py --no-write` (27 checks); `python tests/validar_corte_vertical.py --no-write` (71 checks).
- Python regressions: all **171 tests** in `test_explicit_initialization`, `test_workspace_handoffs`, `test_transformed_execution`, `test_equation_workbench`, `test_equation_manipulation`, `test_mathematical_kernel`, `test_mathematical_domains`, `test_hydraulic_execution`, `test_dynamic_definition`, `test_common_network_results` and `test_v2_initialization` passed. The local runner loads those modules with `unittest`; `check_completed_suites.py` compares their discovered test identities with the log and confirms each passed exactly once. All **26** `test_derived_execution` tests also passed, including frozen M1-A/B/C with RK45/BDF. All **31** tests from `test_common_admission`, `test_model_assessment` and `test_v2_route_switch.RouteSwitchTests.test_selection_capabilities_rejections_and_no_fallback` passed outside the Windows sandbox because its socket restriction stalled ASGI/asyncio tests. The initial elevated retry was blocked by an approval-service usage limit; after the user continued, approval succeeded. Supplemental full 25-request native/adapter thermodynamic replays were stopped by verified test PID and are not claimed as passing in this cleanup; the scoped tests above completed first. No user server was stopped.
- Preservation audit: dictionary keys, index expressions and admission comparisons are unchanged in the seven source files; hashes confirm no edits in the Model frontend, mathematics kernel, thermodynamics or frozen reference directory. The only repository changes from this cleanup are those seven sources, the two verifiers, this plan and the project board. The `clean-en` claim is released for review; phases 4–7 remain unfinished. Project board registries updated; board refresh pending.
- No numerical capability changed, so the Checklist registry and generated capability snapshot require no change. No commit or push is authorized. Local validation logs and pre-edit copies are under `.tmp/codex-clean-en/`; test-generated publications are redirected there to preserve shared and frozen artifacts.
- **Independent review (Claude, 29 October 2026): accepted.** Own AST comparison of the seven sources against Codex's pre-edit copies in `.tmp/codex-clean-en/`, with every string constant masked: `core/modelo/{__init__,adaptadores,relaciones}.py` and `core/compilador/{__init__,explicito}.py` are structurally identical, and so is the multiset of string constants in identity positions (dict keys, subscripts, comparisons, `.get/.pop/.setdefault` arguments), so no persisted key, enum value or protocol field changed. `core/modelo/lector.py` and `core/compilador/compilador.py` differ only by additions (`steady`, `damped_newton`, `derivedExecution`, `metodoSolicitado`, `version`, `motores`, `tipo`), which belong to Codex's later F3 fourth-slice work under its `f3` claim; no identity string was lost. Rerun here: `python tests/validar_modelo_comun.py` 102, `python tests/validar_compilador_explicito.py --no-write` 27, `python tests/validar_corte_vertical.py --no-write` 71; each of the eleven named modules run as `python tests/<module>.py`, 168 tests passing (5, 8, 9, 38, 6, 27, 33, 14, 13, 9, 6; Codex's log counts 171, a three-test difference from the later F3 working tree that does not affect the verdict) and `test_derived_execution` 26; `docs/ejemplos/` status unchanged. The ASGI tests and the frontend checks were not rerun, since no frontend file and no route changed. The owned-code prose slice is accepted; the `clean-en` milestone returns to planned because phases 4-7 remain unfinished.

## 7. Decisions

On 2026-10-19 the user accepted the proposals and left the open choice (D4) to the best option for the project.

- **D1. UI language: the original 19 October scope kept interface text in Spanish.** The 29 October user request supersedes that restriction for Codex-owned `frontend/app/models/`, `core/compilador/`, `core/modelo/` and `core/mathematics/`: authored user-visible text and comments are English. Existing contract identifiers and compatibility lookup inputs remain unchanged under D2/D3; this request does not authorize another Model layout.
- **D2. Identifiers in code (L4): existing identifiers stay; new code is written in English.** Renaming the existing ones would touch thousands of names for no change in behavior.
- **D3. External contracts (L5): the routes, JSON formats, localStorage keys and page URLs stay** until a versioned migration is planned on its own. Changing them now would break saved sheets and notebooks, shared links and the desktop executable.
- **D4. Two thermodynamics packages: merge them.** In phase 6, the old providers in `thermodynamics/` (`elv`, `ell`, `entalpia`, `proveedor`, `reaccion`) move into the layer as `core/thermodynamics/providers/`, and `core/termodinamica/` becomes `core/thermodynamics/`. All the imports change in the same commit, with no compatibility shim left behind.
  - Why: the architecture has one thermodynamic layer that is always present (ARCHITECTURE §2). Two top-level packages with the same English name would invite imports from the wrong one.
- **D5. History language: dated hand-off documents keep their original Spanish text.** They are only renamed and moved to `docs/history/`; translating them adds little value.
- **D6. Remove the old Process Simulation side (user decision, 2026-10-22).** The equipment-oriented simulators will eventually be deleted, so no operation-specific equation black boxes remain. These are the column, FUG, McCabe–Thiele, Ponchon–Savarit, absorber, CSTR/PFR, sizing, flowsheet/diagram and orchestrator code, with their `nucleo*.py` backends, `/columna`, `/flowsheet`, `/termodinamica` pages and routes. The Model Engines side stays. That includes `/motor`, which is the frontend implementation used by `/models`, and the `motor_*.py` thermodynamic services. The laboratory was deleted on 2026-10-22 (user decision; see the laboratory deletion status below).
  - **Rescue before deletion:**
    - validated legacy results, kept as data that serves as independent references;
    - the stoichiometry, balancing, kinetics and chemical-equilibrium tools, re-entering as declared constitutive relations in F5 after verification;
    - residue-map/azeotrope/reactive-transform analysis, reconnected to the common thermodynamic layer;
    - `vapor_if97`, as an IAPWS-95 reference.
  - **Effect on earlier decisions:** D4 and the phase-5 move of `api/` to `legacy/` are superseded where the code is deleted instead.
  - **Order:**
    1. Dead code and shared components.
    2. Freeze reference results.
    3. Split `backend/main.py` routers.
    4. Delete the legacy side with the engine suites green.
    5. Rescue tools in F5.
  - **Phase 1 status (2026-10-22, Claude):**
    - A full working-tree backup is stored in the local ref `refs/backups/pre-cleanup-phase1-2026-10-22`. It is not on a branch and was not pushed.
    - `FormulaLatex` moved from `frontend/app/flowsheet/` to `frontend/app/components/`, with 49 imports and `verificar_expansion.mjs` updated. Each changed by one line, and line endings were preserved.
    - Checks: TypeScript, scoped ESLint, `verificar_expansion`, `verificar_physical_journals`, the workbench readers (11,149 formulas), workspace handoffs and `test:motor-fundamental` pass.
  - **Findings that narrowed phase 1:**
    - Routes without a frontend caller are not dead. `/modelo/validar`, `/unidades/capacidades` and `/motor/termodinamica/capacidades` are published engine contracts with verifiers. The `/laboratorio/*` routes are covered by about 20 laboratory suites.
    - The deprecated `/flowsheet/*` routes are a cross-check for `tests/validar_api.py`, so they go with the legacy side in step 4.
    - **First-commit prototype deleted (user approval, 2026-10-22).** The removed files are `api/` (`simulador.py`, `simulador_destilacion.py`), root `main.py` ("skeleton pending review"), `ejemplo_orquestador.py` and `core/mesh_solver.py`, which was an unimported stub mentioned only in prototype comments.
      - Nothing imported the prototype. Only comments in `backend/nucleo_unidades.py` and `core/orquestador.py` and the planned-move mapping in `tools/repo_cleanup/inventory.py` mention it; they go with the legacy side.
      - `config/` and `thermodynamics/` stay because the legacy backends and the executable build still use them.
      - Verification: `backend.main` imports with 68 routes. These pass: `validar_api` (TODO OK), vertical slice 71, thermodynamic layer 179, balances 30, explicit compiler 27, common model 102, plus the mathematical-kernel and workspace-handoff tests.
  - **Phase 2 status (2026-10-22, Claude, user-approved format): legacy reference results frozen.** No legacy code was deleted.
    - **Location.** Data in `tests/reference_data/legacy-distillation/`: one JSON per method plus `manifest.json` with each file's SHA-256. The generator `tools/legacy_reference/freeze_legacy_distillation.py` imports the legacy code, so it runs only before step 4 and is deleted with that code. `python tests/test_legacy_reference_data.py` checks the frozen data without legacy imports and stays after the deletion.
    - **Format `rage.legacy-reference` v1.** Each file holds:
      - `legacy`: the module, classes or routes and the validation script it reproduces;
      - `inputs`, `outputs` and `rejections`, the last with the exception type and message of every call the legacy code must refuse;
      - `assumptions`: CMO, linear q-line, ideal mixing enthalpy, F = 1 basis in FUG, and so on;
      - `thermodynamics`: the `thermo` 0.6.1 provider and the tables actually used (bubble-point sweep T–x–y with activity coefficients, pure P_sat, H_vap and Cp, Ponchon–Savarit H_L/H_V, FUG top/feed/bottom K and α), so that a later comparison can separate the method from the thermodynamic model;
      - `validation`: a `grade` (`cross-checked` or `legacy-output-only`) and checks typed `independent`, `cross-method`, `self-consistency` or `none`, each evaluated on the frozen numbers (`holdsInFrozenData`);
      - `comparison` tolerances, `units` (flows in mol/s, as the HTTP schema states) and `provenance` (commit, SHA-256 of the 14 legacy sources, the flag that some had uncommitted comment/path edits, and the Python, NumPy, SciPy and `thermo` versions).
    - **Cases.** McCabe–Thiele and Ponchon–Savarit for benzene/toluene at 1 atm, FUG for C3–C6 alkanes at 5 atm, the FUG column chained to a pump through `DiagramaFlujo`, and the three `/columna/resolver` presets as HTTP request/response pairs. Two runs produced byte-identical files.
    - **Finding.** The build log reports Ponchon–Savarit within 0.6–2.5 % of McCabe–Thiele. That figure came from an earlier fixed-duty sweep. The current sweep, scaled with `Qc_D_min`, ranges from 0.2 % to 3.25 % (largest at 1.5 × `Qc_D_min`, q = 1). It is recorded as found, with a 3.5 % check; it reflects the constant-molar-overflow gap, not a defect. The other build-log figures reproduce: two- versus three-point Fenske differ by 0.20 %, `Qc_D_min` is 80,960 (q = 1) and 166,650 (q = −0.5) J/mol, and the column N is 9.434906966491038.
    - **Scope.** Legacy outputs are not independent truth. Only the closed-form material balances, the no-subcooling condenser duty and the pump state are `independent`; the rest are cross-method or self-consistency evidence.
  - **Phase 3 status (2026-10-22, Claude, user-authorized move of the `/motor` and `/laboratorio` routes): `backend/main.py` routers split.**
    - `backend/main.py` now only creates the app, adds CORS, defines `/salud` and registers the routers. The existing `api_adimensionalizacion`, `api_unidades` and `api_modelo` routers are unchanged.
    - New modules, with route code moved verbatim (only `@app.` became `@router.`):
      - `backend/routes_process_simulation.py`: the 16 legacy routes deleted in step 4 (`/componentes`, `/modelos-termodinamicos`, `/ejemplos*`, `/columna`, `/flowsheet/*`, `/diagrama/*`, `/unidades`, `/elv/binario`, `/termodinamica/*`). `/elv/binario` and `/termodinamica/*` are marked as rescue items;
      - `backend/routes_laboratory.py`: the 20 `/laboratorio/*` routes, kept apart while the laboratory decision is open;
      - `backend/routes_engine.py`: the 9 `/motor/*` routes.
    - The routers are registered in the original order. Before and after, the 68 routes (path, methods, name, response model, status, summary, description, deprecation) and the generated OpenAPI document are identical; the moved code matches the original text line by line.
    - The uncommitted `/laboratorio/estudios/*` routes from another session moved into `routes_laboratory.py` unchanged, so commit them together with that file.
    - Verification: all 27 suites that import `backend.main` pass (`validar_api`, `validar_api_especificaciones`, `validar_correcciones_auditoria`, `validar_laboratorio`, 17 `validar_estudios*`, `validar_topologia_fronteras_fuentes`, and engine thermodynamics 585, catalog 126, diagrams 78, assembly 245, assembly v2 114). The backend on 8004 runs without `--reload` and keeps the previous code until an authorized restart; routes and responses are unchanged.
  - **Laboratory deletion (2026-10-22, Claude, user decision: delete, not rebuild).** This settles the open question in ARCHITECTURE §9.2 for the laboratory and unblocks step 4.
    - **Backup.** Before deleting, the full working tree, including untracked files, was stored in the local ref `refs/backups/pre-lab-deletion-2026-10-22` (commit `0cbea46`, parent `HEAD`). It was built with a temporary index, so the real index and branch are unchanged, and it was not pushed. Most of the deleted code was untracked, so this ref is its only copy. Restore a file with `git checkout refs/backups/pre-lab-deletion-2026-10-22 -- <path>`.
    - **Deleted.**
      - Backend: `routes_laboratory.py` (20 routes), `nucleo_laboratorio.py`, `nucleo_sustancias.py`, `nucleo_reacciones.py`, `nucleo_estudios.py`, `schemas_laboratorio.py`, `schemas_estudios.py`, `ejemplos_laboratorio.py` and `ejemplos_estudios.py`.
      - Core modules used only by the laboratory: `core/laboratorio.py`, `core/dinamica.py`, `core/unidades_estudios.py` and `core/base_materia.py`.
      - Frontend: `app/laboratorio/` (183 files) and 21 verifiers that only exercised it. The Laboratory link was removed from `NavBar.tsx`, the laboratory route from the `BarraSimulacion.tsx` exclusion list, and the deleted verifiers from `package.json` (`test` narrowed; 11 `test:*` scripts removed).
      - Python: `validar_laboratorio.py`, the 17 `validar_estudios*.py`, `validar_topologia_fronteras_fuentes.py`, the 2026-10-11 coupled-engine audit `auditoria_motor_acoplado.py`, its regressions `validar_correcciones_auditoria.py`, and `generar_ejemplos_estudios.py`.
    - **Trimmed.** In `verificar_ecuaciones.mjs`, `verificar_orientacion.mjs` and `verificar_api_motor.mjs`, only the trailing laboratory checks were removed; their legacy flowsheet checks remain until step 4.
    - **Kept on purpose.**
      - The rescue items of step 5: `core/estequiometria.py`, `balanceo.py`, `cinetica.py`, `equilibrio.py` and `lote.py`.
      - The `LAB_*` codes in the shared `core/errores.py`.
      - The laboratory styles in `globals.css`.
      - Historical documents and request/response examples (`docs/ENTREGA_LABORATORIO_CODEX.md`, the lab guide, and `docs/ejemplos/laboratorio-*` and `estudio-*`). No remaining test reads them.
    - **Verification.**
      - The remaining 48 routes and their OpenAPI paths are identical to those before the deletion; the 50 removed schemas were used only by the laboratory.
      - Python: 41 suites pass, including every `tests/test_*.py`, the API, model, compiler, engine thermodynamics, catalog, diagrams, assembly v1/v2, n-components, consolidation, H3, results, units and traceability suites, plus the legacy column suites and the frozen reference data.
      - Frontend: TypeScript (0 errors outside the dev server's generated `.next/types`, which still list the deleted pages until Next regenerates them), scoped ESLint, the narrowed `npm test`, `verificar_physical_journals`, `verificar_equation_workbench`, `verificar_workspace_handoffs` and `test:motor-fundamental` pass.
      - The dev server on 3000 and the backend on 8004 were not touched; 8004 keeps serving the old laboratory routes until an authorized restart.
  - **Steps 4 and 5 done (2026-10-29, Claude, user decision dec-delete-process-side): tools rescued (clean-5), then the Process Simulation side and `thermodynamics/` deleted (clean-4).** This supersedes D4: the legacy providers are deleted, not merged.
    - **Backup.** `refs/backups/pre-clean-4-2026-10-29` (HEAD `3aa86cc`) and `refs/backups/pre-clean-4-2026-10-29-worktree` (HEAD plus the working-tree state of every deleted or edited path, including the untracked `frontend/app/flowsheet/*` files, `core/fluidos.py`, seven untracked verifiers and `AvisoAlmacen.tsx`; built with a temporary index, real index untouched, not pushed). Restore with `git checkout refs/backups/pre-clean-4-2026-10-29-worktree -- <path>`.
    - **Rescued (clean-5).** `core/estequiometria.py`, `balanceo.py`, `cinetica.py`, `equilibrio.py` and `lote.py` moved by `git mv` to `core/reactions/{stoichiometry,balancing,kinetics,equilibrium,batch}.py` (identifiers unchanged, D2). `core.reactions.RELATIONS` declares nine relations; `python tests/test_reaction_relations.py` (7 tests) checks them against closed forms. F5 still declares them to the common model. `thermodynamics/reaccion.py` was not rescued: `core/reactions/equilibrium.py` covers K(T) by both Kirchhoff and van 't Hoff.
    - **Deleted (106 tracked files, `git rm`, plus untracked ones).** `thermodynamics/`; `config/settings.py`; root `ejemplo_*.py`; backend `routes_process_simulation.py` (16 routes), the `nucleo*.py` backends, `schemas.py`, `trazabilidad.py`, `diagnosticos.py`, `ejemplos.py`, `ejemplos_flowsheet.py`; core `absorbedor`, `balance_materia`, `columna_destilacion`, `corriente`, `diagrama_corrientes`, `diagrama_flujo`, `dimensionado`, `especificaciones`, `flash`, `fluidos`, `fug`, `mccabe_thiele`, `orquestador`, `ponchon_savarit`, `reactor_cstr`, `reactor_pfr`; `tools/legacy_reference/`; 20 legacy `tests/validar_*.py` (including `validar_api.py`); frontend pages `/columna`, `/flowsheet`, `/termodinamica`, `/simulaciones`, `/configuracion`, 15 components used only by them (`SimulacionProvider`, `BarraSimulacion`, `plantillas`, the column diagrams, …) and 25 legacy verifiers. A static import graph from `backend.main` confirmed that no Engine module reached any of them.
    - **Edited.** `backend/main.py` (router and docstring), `frontend/app/layout.tsx` (provider, bar and storage warning removed), `frontend/app/page.tsx` and `NavBar.tsx` (links to the deleted pages replaced by Models and Checklist), `frontend/package.json` (`test` now runs `verificar_physical_journals.mjs`), `verificar_todo.mjs`, `empaquetado/construir.ps1` (no `thermodynamics`/`api` submodules) and ARCHITECTURE §6/§8.
    - **Kept on purpose.** `core/errores.py` (used by the reaction tools), `core/dimensiones.py` (`validar_unidades`), `core/vapor_if97.py` (IAPWS reference), the residue-map/azeotrope/reactive-transform analysis `core/topology.py`, `core/analisis_nodos.py`, `core/transformaciones.py` with `config/graficos.py` (D6 rescue item; its only suite `validar_termodinamica.py` used the deleted provider, so it is untested until it is reconnected to the common layer), and the frozen `tests/reference_data/legacy-distillation/` with `test_legacy_reference_data.py`.
    - **Verification.** `backend.main` imports with 37 routes. TypeScript (0 errors outside `.next/types`), scoped ESLint and `verificar_physical_journals` (1,391) pass. Python: every remaining `tests/validar_*.py` passes except `validar_motor_balances` 29/30, a pre-existing message-prefix check (`motor de balances:` versus the English `Balance engine:` from the Codex-owned compiler translation), unrelated to the deletion. `tests/test_*.py`: 52 of 53 suites pass (497 tests); `test_material_derivation` fails 2 assertions for the same reason (it expects the earlier `Transform`/`algebraic` messages; the Codex-owned uncommitted `core/compilador/compilador.py` emits the English admission messages), and it imports no deleted module. The layer validators rewrote three `docs/ejemplos/modelo-comun/` examples; they were restored. Servers on 3000, 8004 and 8005 were not touched.

### Audited Codex checkpoints (24 October 2026)

The user authorized commits of Codex work only, with no push and no shared-document commit. Each path was added separately; every commit used `git commit --only -- <paths>`. The non-target Git index entries were compared before and after each commit and preserved, including the already staged roadmap rename. These checkpoints cover **207 distinct files** (208 file entries because the historical hydraulic fixture was restored in a separate follow-up). Tests ran on the shared working tree, not a clean isolated checkout.

| Commit | Message | Files |
|---|---|---|
| `8394c971e7e8d8cb6acdf72eca68a4452a3bc252` | Engine: preserve typed equation kernel and recorded physical deductions | 31 |
| `20b47ce9f06c1ca488abc7e556ef0f9e22c180c1` | Frontend: preserve the shared Model Transform Solve Results workspaces | 155 |
| `0cf4ad5cb1bab02a7a280af4b53bb83aac34e361` | Tests: preserve the frozen M1-B source method during execution checks | 1 |
| `e392e4dcd09df959953d4c34323471908e8429e8` | Engine: commit M1 lowering acceptance and common solver event margins | 21 |

<details>
<summary>8394c97 — exact files and verification</summary>

173 tests: 135 passed initially; the 38-test workbench suite passed after selecting BDF explicitly in its fixture.

- `core/balances/energy_derivation.py`
- `core/balances/energy_equations.py`
- `core/balances/hydraulic_definition.py`
- `core/balances/material_derivation.py`
- `core/balances/material_equations.py`
- `core/balances/momentum_derivation.py`
- `core/balances/momentum_reductions.py`
- `core/balances/momentum_transport.py`
- `core/mathematics/__init__.py`
- `core/mathematics/constants.py`
- `core/mathematics/contract.py`
- `core/mathematics/dimensions.py`
- `core/mathematics/domains.py`
- `core/mathematics/errors.py`
- `core/mathematics/graph.py`
- `core/mathematics/operators.py`
- `core/mathematics/provenance.py`
- `core/mathematics/validity.py`
- `core/modelo/adaptadores.py`
- `core/modelo/dynamic_definition.py`
- `core/modelo/equation_manipulation.py`
- `core/modelo/operation_journal.py`
- `tests/test_dynamic_definition.py`
- `tests/test_energy_derivation.py`
- `tests/test_equation_manipulation.py`
- `tests/test_equation_workbench.py`
- `tests/test_material_derivation.py`
- `tests/test_mathematical_domains.py`
- `tests/test_mathematical_kernel.py`
- `tests/test_momentum_derivation.py`
- `tests/test_physical_equation_graphs.py`

</details>

<details>
<summary>20b47ce — exact files and verification</summary>

TypeScript and scoped ESLint pass; physical journals, model and material derivations, hydraulic references, phase discovery, transformed execution (60), workspace handoffs, LLE (504), workbench readers (11655 formulas), derived lifecycle (78) pass.

- `frontend/app/adimensionalizacion/contratoNucleo.ts`
- `frontend/app/adimensionalizacion/exportar.ts`
- `frontend/app/adimensionalizacion/lecturaNucleo.ts`
- `frontend/app/models/CommonModelContent.tsx`
- `frontend/app/models/CompilationPanel.tsx`
- `frontend/app/models/CompilationSummary.tsx`
- `frontend/app/models/DeducedModelSummary.tsx`
- `frontend/app/models/DerivedExecution.tsx`
- `frontend/app/models/DerivedSolve.tsx`
- `frontend/app/models/DynamicModelDefinition.tsx`
- `frontend/app/models/EnergyJournalEditor.tsx`
- `frontend/app/models/EquationRows.tsx`
- `frontend/app/models/EquationWorkbenchPanel.tsx`
- `frontend/app/models/FormulationExecution.tsx`
- `frontend/app/models/HydraulicSolve.tsx`
- `frontend/app/models/MaterialJournalEditor.tsx`
- `frontend/app/models/ModelDefinition.tsx`
- `frontend/app/models/ModelDerivationStatus.tsx`
- `frontend/app/models/ModelDomainControls.tsx`
- `frontend/app/models/ModelLibrary.tsx`
- `frontend/app/models/ModelReadiness.tsx`
- `frontend/app/models/ModelWorksheet.tsx`
- `frontend/app/models/ModelWorkspace.tsx`
- `frontend/app/models/MomentumCoupling.tsx`
- `frontend/app/models/MomentumJournalEditor.tsx`
- `frontend/app/models/NetworkModelDerivation.tsx`
- `frontend/app/models/RecordedDerivation.tsx`
- `frontend/app/models/ThermodynamicJournalEditor.tsx`
- `frontend/app/models/TransformWorkspace.tsx`
- `frontend/app/models/WorkspaceVisual.tsx`
- `frontend/app/models/[id]/[[...workspace]]/page.tsx`
- `frontend/app/models/[id]/layout.tsx`
- `frontend/app/models/chartLayout.ts`
- `frontend/app/models/derivedSelection.ts`
- `frontend/app/models/dynamicDefinition.ts`
- `frontend/app/models/english.ts`
- `frontend/app/models/equationWorkbench.module.css`
- `frontend/app/models/equationWorkbench.ts`
- `frontend/app/models/error.tsx`
- `frontend/app/models/formulationRequests.ts`
- `frontend/app/models/hydraulicDefinition.ts`
- `frontend/app/models/layout.tsx`
- `frontend/app/models/modelDerivationAudit.ts`
- `frontend/app/models/modelDiagnostics.ts`
- `frontend/app/models/modelImport.ts`
- `frontend/app/models/modelRequest.ts`
- `frontend/app/models/modelTopology.ts`
- `frontend/app/models/momentumDerivation.ts`
- `frontend/app/models/page.tsx`
- `frontend/app/models/transformationSelection.ts`
- `frontend/app/models/useBrowserReady.ts`
- `frontend/app/models/useChartDrag.ts`
- `frontend/app/models/workflow.ts`
- `frontend/app/models/workspace.module.css`
- `frontend/app/motor/AlcancePaqueteRed.tsx`
- `frontend/app/motor/AvisoCertificacionRed.tsx`
- `frontend/app/motor/BarraHojaMotor.tsx`
- `frontend/app/motor/BibliotecaHojas.tsx`
- `frontend/app/motor/CoberturaGruposPaquete.tsx`
- `frontend/app/motor/DefinirVolumen.tsx`
- `frontend/app/motor/DerivacionVolumenRed.tsx`
- `frontend/app/motor/DetallesEnsamblaje.tsx`
- `frontend/app/motor/DetallesRedTermodinamica.tsx`
- `frontend/app/motor/EcuacionesFinales.tsx`
- `frontend/app/motor/EditorBalanceModular.tsx`
- `frontend/app/motor/EditorComponentesRed.tsx`
- `frontend/app/motor/EditorDatosPuros.tsx`
- `frontend/app/motor/EditorEnsamblajeMateria.tsx`
- `frontend/app/motor/EditorEstadoTermodinamico.tsx`
- `frontend/app/motor/ElegirCierreEnergia.tsx`
- `frontend/app/motor/EnergiaFundamental.tsx`
- `frontend/app/motor/EquilibrioHoja.tsx`
- `frontend/app/motor/EspacioRedTermodinamica.tsx`
- `frontend/app/motor/EstadoSistema.tsx`
- `frontend/app/motor/FundamentoBalance.tsx`
- `frontend/app/motor/FundamentoCierreEnsamblado.tsx`
- `frontend/app/motor/GestorComponentesMateria.tsx`
- `frontend/app/motor/GraficaCorteEquilibrio.tsx`
- `frontend/app/motor/HojaGuardada.tsx`
- `frontend/app/motor/MateriaFundamental.tsx`
- `frontend/app/motor/ModelAssumptions.tsx`
- `frontend/app/motor/NavegacionHoja.tsx`
- `frontend/app/motor/PanelesBalances.tsx`
- `frontend/app/motor/PaquetesEjecutadosRed.tsx`
- `frontend/app/motor/ProgresoMateria.tsx`
- `frontend/app/motor/ReconstruccionMateriaRed.tsx`
- `frontend/app/motor/ResolverEnsamblaje.tsx`
- `frontend/app/motor/ResolverHoja.tsx`
- `frontend/app/motor/ResultadosHoja.tsx`
- `frontend/app/motor/SelectorSustanciaCatalogo.tsx`
- `frontend/app/motor/TableroMotor.tsx`
- `frontend/app/motor/VariablesDelVolumen.tsx`
- `frontend/app/motor/VariablesMateria.tsx`
- `frontend/app/motor/datosDiagramaEquilibrio.ts`
- `frontend/app/motor/datosGraficasMotor.ts`
- `frontend/app/motor/ecuacionesFinales.module.css`
- `frontend/app/motor/energia/page.tsx`
- `frontend/app/motor/ensamblajeMateria.ts`
- `frontend/app/motor/estadoResolucionRed.ts`
- `frontend/app/motor/hojas/[id]/estado/page.tsx`
- `frontend/app/motor/hojas/[id]/page.tsx`
- `frontend/app/motor/hojas/[id]/resolver/page.tsx`
- `frontend/app/motor/hojas/[id]/resultados/page.tsx`
- `frontend/app/motor/hojas/page.tsx`
- `frontend/app/motor/hojasDemostracion.ts`
- `frontend/app/motor/hojasMotor.ts`
- `frontend/app/motor/hojasPruebaAcoplamiento.ts`
- `frontend/app/motor/hojasPruebaEnergia.ts`
- `frontend/app/motor/hojasPruebaMateria.ts`
- `frontend/app/motor/hojasPruebaMultifasico.ts`
- `frontend/app/motor/hojasPruebaNComponentes.ts`
- `frontend/app/motor/hojasPruebaUNIFAC.ts`
- `frontend/app/motor/lectorDiagramasEquilibrio.ts`
- `frontend/app/motor/materia/page.tsx`
- `frontend/app/motor/materialDerivation.ts`
- `frontend/app/motor/materialNetworkTemplates.ts`
- `frontend/app/motor/metadatosRed.ts`
- `frontend/app/motor/modeloHojaMotor.ts`
- `frontend/app/motor/modeloNumerico.ts`
- `frontend/app/motor/momento/page.tsx`
- `frontend/app/motor/motor.module.css`
- `frontend/app/motor/networkEnergyJournal.ts`
- `frontend/app/motor/networkMaterialJournal.ts`
- `frontend/app/motor/networkThermodynamicJournal.ts`
- `frontend/app/motor/page.tsx`
- `frontend/app/motor/phaseDiscoveryExample.ts`
- `frontend/app/motor/physicalDerivation.ts`
- `frontend/app/motor/prepararEnsamblajeTermodinamico.ts`
- `frontend/app/motor/recorridoEnergia.ts`
- `frontend/app/motor/recorridoMateria.ts`
- `frontend/app/motor/redTermodinamica.ts`
- `frontend/app/motor/resolverEngine.ts`
- `frontend/app/motor/resultadosMotor.ts`
- `frontend/app/motor/seleccionBalances.ts`
- `frontend/app/motor/topologiaRed.ts`
- `frontend/app/motor/trabajoMotor.module.css`
- `frontend/app/motor/useHojasMotor.ts`
- `frontend/motores/modelo/compilation.ts`
- `frontend/motores/modelo/desdeHojaBalances.ts`
- `frontend/motores/modelo/desdeHojaMotor.ts`
- `frontend/motores/modelo/servicioModelo.ts`
- `frontend/motores/resultados/lector.ts`
- `frontend/next.config.ts`
- `frontend/testing/modelFixtures.ts`
- `frontend/testing/pressureExamples.ts`
- `frontend/verificar_derived_lifecycle.mjs`
- `frontend/verificar_equation_workbench.mjs`
- `frontend/verificar_hydraulics.mjs`
- `frontend/verificar_liquido_liquido.mjs`
- `frontend/verificar_material_journals.mjs`
- `frontend/verificar_model_derivations.mjs`
- `frontend/verificar_phase_discovery.mjs`
- `frontend/verificar_physical_journals.mjs`
- `frontend/verificar_transform_execution.mjs`
- `frontend/verificar_workspace_handoffs.mjs`

</details>

<details>
<summary>0cf4ad5 — exact files and verification</summary>

Fresh shared authoring reproduces frozen M1-A/B exactly; hydraulic execution references and TypeScript pass. Execution tests select BDF explicitly while the historical source remains unchanged.

- `frontend/testing/pressureExamples.ts`

</details>

<details>
<summary>e392e4d — exact files and verification</summary>

73 acceptance/compiler tests: 72 passed initially and the frozen A/B reproduction test passed after restoring the historical fixture; 8 common-phase/margin tests and 6 stage-stop/margin tests passed. Frozen A/B/C files unchanged.

- `core/compilador/compilador.py`
- `core/compilador/derived.py`
- `core/compilador/explicito.py`
- `core/compilador/hydraulics.py`
- `core/compilador/presentation.py`
- `core/compilador/transformed.py`
- `core/solvers/integrador.py`
- `tests/m1_acceptance.py`
- `tests/matter_lowering_inputs.py`
- `tests/reference_data/m1-a.json`
- `tests/reference_data/m1-b.json`
- `tests/reference_data/m1-c.json`
- `tests/test_common_phase_window.py`
- `tests/test_derived_execution.py`
- `tests/test_hydraulic_execution.py`
- `tests/test_m1_coupled_acceptance.py`
- `tests/test_m1_thermal_acceptance.py`
- `tests/test_m1_u1_acceptance.py`
- `tests/test_solver_stability_margins.py`
- `tests/test_transformed_execution.py`
- `tests/test_workspace_handoffs.py`

</details>

**Ownership exceptions retained locally.** `backend/api_modelo.py`, `core/balances/generador.py`, `frontend/app/motor/TermodinamicaHoja.tsx`, `familiasBalance.ts`, `recorridoTermodinamico.ts`, `ubicacionEcuaciones.ts`, `frontend/motores/resultados/contrato.ts`, `frontend/app/motor/resultadoEnsamblajeV2.ts` and `frontend/package.json` include both Codex work and Claude documentation/retirement/cleanup hunks. They were not committed wholesale or temporarily rewritten to remove another author's work. The remaining legacy application shell, laboratory/history artifacts and unrelated changes were also excluded: this checkpoint does not assert authorship of the whole dirty tree. Shared roadmap/board/Checklist/workspace/architecture/agent documents remain for the user-requested joint commit later. `core/solvers/integrador.py` was initially mixed; after Claude committed stage-stop retry in `5c18fe1`, its remaining Codex margin diff was verified and included in `e392e4d`.

**Verification repair.** Workbench execution tests now request BDF explicitly. The shared historical hydraulic source retains `euler_implicito` so fresh M1-B authoring remains byte-for-byte consistent with the frozen document; execution tests select a supported method independently. An attempted fixture change caused one frozen-source comparison failure, was restored in `0cf4ad5`, and the fresh A/B authoring comparison passed. A/B/C remain 43/31/25 operations, with their original SHA-256 values recorded in the M1 acceptance source. Five verifier-local module bindings were renamed to satisfy scoped ESLint; the affected verifiers were rerun. No frozen fixture was regenerated.

**Risk status.** `risk-uncommitted` remains high and open because mixed/shared and other unreviewed files still exist only locally. The immediate post-checkpoint status had 448 entries; that is a live working-tree count and can change with concurrent Claude work. No push was performed. The next separate decision concerns [v2 parity and retirement](../engine/dynamic-assembly.md#12-v2-retirement-parity-audit), not deletion authorized by these commits.

### 29 October 2026: accepted Codex checkpoints

The user authorized selective commits of accepted work. Each complete file was audited for ownership; files containing review work or another author's hunks were excluded. Every commit used explicit `git add -- <paths>` followed by `git commit --only -- <paths>`. Six commits preserve 46 distinct files. MD-1 was already committed in `30e5eb4` and was not duplicated. No push was performed.

Tests ran against the shared working tree, including excluded local dependencies; these are selective preservation commits, not a claim that a clean checkout of this HEAD is a complete runnable delivery. Frozen M1-A/B/C and thermodynamics sources were not changed.

#### Checkpoint 0a8431a

Engine: checkpoint accepted R7 admission and v2 common publication

12 admission tests and 27 initialization, network-results, workspace-handoff and stage-stop tests passed.

- `backend/assembly_results.py`
- `core/compilador/admission.py`
- `core/compilador/compilador.py`
- `core/compilador/datum_bounds.py`
- `core/compilador/initialization.py`
- `core/compilador/network_results.py`
- `core/compilador/report.py`
- `tests/test_common_admission.py`
- `tests/test_common_network_results.py`
- `tests/test_solver_stage_stop.py`
- `tests/test_v2_initialization.py`
- `tests/test_workspace_handoffs.py`

#### Checkpoint bf1b6ff

Engine: checkpoint accepted F0 initialization and assessment clients

23 initialization/assessment tests, the live assessment client/SSR/storage/lifecycle verifier and TypeScript checking passed. The verifier negative control was pinned to pre-checkpoint d5b9a120916732727b22a078b1bed6dd5c167848 so committing the client does not invalidate that control.

- `core/compilador/explicito.py`
- `core/modelo/lector.py`
- `frontend/app/models/AssessmentText.tsx`
- `frontend/app/models/DerivedSolve.tsx`
- `frontend/app/models/HydraulicSolve.tsx`
- `frontend/app/models/ModelWorksheet.tsx`
- `frontend/app/motor/ResolverHoja.tsx`
- `frontend/app/motor/ResultadosHoja.tsx`
- `frontend/app/motor/modeloNumerico.ts`
- `frontend/app/motor/resolverEngine.ts`
- `frontend/app/motor/resultadosMotor.ts`
- `frontend/motores/modelo/assessment.ts`
- `frontend/motores/modelo/servicioModelo.ts`
- `frontend/verificar_model_assessment.mjs`
- `tests/test_explicit_initialization.py`
- `tests/test_model_assessment.py`

#### Checkpoint ea5e578

Tests: preserve accepted MD-2 validity-boundary regressions

10 MatterLoweringTests passed, including the four new MD-2 validity-boundary regressions. The implementation files remain local because they also contain F3 work in review.

- `tests/test_derived_execution.py`

#### Checkpoint 81e513f

Engine: checkpoint accepted v2 adapter and HTTP route switch

8 Python tests passed with fresh physical adjuncts and HTTP controls; the 25-request matrix used V2_PARITY_REPLAY=1, explicitly replaying stored evidence rather than claiming a fresh full integration matrix. Stored source digests differ from current sources. Readers passed 25 pairs, 7 adjuncts, 197 states and 19 corruptions, plus 50 stored HTTP publications and 9 malformed provenance cases.

- `backend/routes_engine.py`
- `backend/v2_compatibility.py`
- `backend/v2_dispatch.py`
- `frontend/app/motor/contratoEnsamblajeV2.ts`
- `frontend/app/motor/lectorEnsamblajeV2.ts`
- `tests/reference_data/v2-parity-adjunct.json`
- `tests/test_v2_compatibility.py`
- `tests/test_v2_route_switch.py`
- `tests/v2_parity_cases.py`
- `tests/verificar_v2_compatibility.mjs`
- `tests/verificar_v2_route_switch.mjs`

#### Checkpoint 7a6e6be

Engine: checkpoint accepted F3 constant affine block and regressions

7 fresh law-derived affine tests passed (465.214 s), with RK45/BDF worst scaled error 3.8494e-9 and conservation error 6.0633e-16; the live reader rejected 11 malformed payloads and passed compatibility/lifecycle controls.

- `core/mathematics/linear_system.py`
- `frontend/verificar_affine_algebraic.mjs`
- `tests/test_f3_affine_algebraic.py`

#### Checkpoint 3aa86cc

Tests: checkpoint accepted common-publication certification checks

82 independent-reference UNIFAC checks, 71 vertical-slice checks with --no-write, and the certification reader with 2 live results and 6 rejected corruptions passed.

- `frontend/verificar_common_certification.mjs`
- `tests/validar_capa_unifac.py`
- `tests/validar_corte_vertical.py`

#### Excluded from the 29 October checkpoints

- F3 second/third-slice implementation, shared integration and reader files remain in review: `core/compilador/derived.py`, `presentation.py`, `assessment.py`, `dae.py`, `nonlinear_block.py`; `core/solvers/integrador.py`, `nonlinear.py`; `core/modelo/derived_execution.py`; `core/resultados/formato.py`; `frontend/app/models/CompilationPanel.tsx`, `DerivedExecution.tsx`; `frontend/motores/modelo/compilation.ts`, `derivedExecution.ts`; `frontend/motores/resultados/contrato.ts`, `lector.ts`. Accepted earlier hunks in these files were not split out.
- Review regressions remain local: `tests/test_f3_nonlinear_algebraic.py`, `tests/test_f3_index1_dae.py`, `tests/test_nonlinear_solver.py`, `frontend/verificar_nonlinear_algebraic.mjs`, `frontend/verificar_index1_dae.mjs`.
- Mixed-author files remain local: `backend/api_modelo.py`, `backend/motor_ensamblaje_v2.py`, `core/balances/generador.py`, `frontend/app/motor/TermodinamicaHoja.tsx`, `familiasBalance.ts`, `recorridoTermodinamico.ts`, `ubicacionEcuaciones.ts`, `resultadoEnsamblajeV2.ts`, `frontend/motores/resultados/contrato.ts` and `frontend/package.json`.
- Formatting-only diffs of unverified ownership remain local: `core/modelo/equation_workbench.py`, `frontend/motores/modelo/contrato.ts`, `frontend/motores/modelo/lector.ts`.
- Shared documents and registries remain uncommitted, including this cleanup record, the roadmap, project board, Checklist, workspace specification, contracts and dynamic-assembly evidence. Thermodynamics, legacy application shell/flowsheet/laboratory/history/example artifacts and other files outside this accepted ownership audit remain excluded.

`risk-uncommitted` stays high and open. F3 stays in review. Test output is retained in ignored `.tmp/codex-accepted-commits/`. The temporary F0 claim is released; F0 returns to its previous `next` state. Project board refresh pending.


#### Demo 0.2 proposed commit groups (2 November 2026; no commit authorized)

Snapshot of `git status --porcelain` before this proposal: **70 entries**, each assigned once below; collapsed untracked directories count as one entry. This README is the one additional plan file and belongs only to shared docs. Groups are disjoint **whole-file ownership buckets**, not a claim that each can land independently. Several files contain multiple deliveries; do not manufacture intermediate commits by staging another agent's hunks. Review a combined dependency batch or agree a separate split before committing. New work after this snapshot must be classified before approval.

| Group | Entries | Exact status entries | Proposed message | Checks to rerun |
|---|---:|---|---|---|
| Template record, ports and RC repairs | 6 | `core/modelo/lector.py`, `frontend/app/models/modelDerivationAudit.ts`, `frontend/motores/modelo/contrato.ts`, `frontend/motores/modelo/lector.ts`, `frontend/verificar_template_record.mjs`, `tests/test_template_record.py` | `Model: add versioned equipment recipes and strict typed ports` | test_template_record; verificar_template_record; verificar_model_derivations |
| Events | 4 | `frontend/app/models/CompilationSummary.tsx`, `frontend/app/motor/TableroMotor.tsx`, `frontend/verificar_demo01_models.mjs`, `frontend/app/motor/ResultEvents.tsx` | `Results: display derived phase events and package closures` | verificar_demo01_models; TypeScript |
| Steady Transform and RT repairs | 9 | `frontend/app/models/DerivedExecution.tsx`, `frontend/app/models/derivedSelection.ts`, `frontend/motores/modelo/compilation.ts`, `frontend/motores/modelo/steadyContract.ts`, `core/modelo/steady_transform.py`, `frontend/motores/modelo/steadyTransform.ts`, `frontend/motores/modelo/thermodynamicClosureContract.ts`, `frontend/verificar_steady_transform.mjs`, `tests/test_steady_transform.py` | `Transform: prepare zero-accumulation selections with model-scaled defaults` | test_steady_transform; verificar_steady_transform; verificar_steady_state; TypeScript |
| Template instances | 6 | `frontend/app/models/ModelLibrary.tsx`, `core/modelo/template_instance.py`, `frontend/app/models/templateInstance.ts`, `frontend/motores/modelo/templateInstance.ts`, `frontend/verificar_template_instance.mjs`, `tests/test_template_instance.py` | `Model: replay template instances with fresh identity provenance` | test_template_instance; verificar_template_instance |
| F3-5 HTTP/UI and shared API integration | 9 | `backend/api_modelo.py`, `frontend/app/models/AssessmentText.tsx`, `frontend/app/models/DerivedSolve.tsx`, `frontend/app/models/modelRequest.ts`, `frontend/app/motor/ResultadosHoja.tsx`, `frontend/motores/modelo/servicioModelo.ts`, `frontend/motores/modelo/inverseSpecification.ts`, `frontend/verificar_inverse_steady.mjs`, `tests/test_inverse_steady_http.py` | `Solve: expose inverse steady specifications and strict publication` | test_inverse_steady_http; verificar_inverse_steady; TypeScript |
| Index sets | 7 | `frontend/app/models/ModelWorksheet.tsx`, `frontend/app/motor/ModelAssumptions.tsx`, `core/modelo/index_sets.py`, `frontend/motores/modelo/indexSetContract.ts`, `frontend/motores/modelo/indexSets.ts`, `frontend/verificar_index_sets.mjs`, `tests/test_index_sets.py` | `Model: declare and replay indexed stage topology` | test_index_sets; verificar_index_sets; physical journals; TypeScript |
| App-flow verifier | 1 | `frontend/verificar_demo02_app_flow.mjs` | `Tests: exercise imported drums through production HTTP clients` | verificar_demo02_app_flow against own backend |
| Claude momentum (confirm) | 3 | `core/compilador/derived.py`, `tests/derived_momentum_inputs.py`, `tests/test_derived_momentum_outlet.py` | `Physics: admit derived momentum outlet states` | test_derived_momentum_outlet; momentum reference suites |
| Claude steady backend (confirm) | 3 | `core/compilador/derived_closure.py`, `core/compilador/steady.py`, `tests/test_steady_package_closure.py` | `Physics: close steady package volumes and reduced momentum` | test_steady_package_closure; test_f3_steady_state |
| Claude F3 readers (confirm) | 2 | `core/solvers/inverse_steady.py`, `tests/test_f3_inverse_publication.py` | `Solve: validate inverse steady publication evidence` | test_f3_inverse_publication; inverse steady suites |
| Claude drum (confirm) | 5 | `frontend/testing/modelFixtures.ts`, `docs/ejemplos/demo-0.2/`, `frontend/testing/demo02/`, `tests/demo02_drum.py`, `tests/test_demo02_drum.py` | `Examples: record the dynamic equipment drum and export its fixture` | test_demo02_drum; template/physical/derivation verifiers |
| Shared docs and board tooling (joint confirmation) | 10 | `docs/contracts/common-model.md`, `docs/contracts/results-format.md`, `docs/engine/codex-queue.md`, `docs/engine/engine-checklist.md`, `docs/engine/model-workspaces.md`, `docs/engine/multiphysics-roadmap.md`, `docs/engine/project-board.json`, `frontend/app/checklist/datos.ts`, `tools/roadmap_board/README.md`, `tools/roadmap_board/build_board.mjs` | `Docs: synchronize Demo 0.2 contracts, evidence and board` | board --check; physical snapshot; documentation link checker |
| Hold: local/generated or unresolved retention | 5 | `.claude/launch.json`, `frontend/.next-demo02-rt/`, `frontend/auditoria_experimentar_2026_10_12/`, `frontend/examples/`, `frontend/qa-insercion-mesa.json` | No commit proposed | Confirm authorship/retention; do not delete |

**Mixed delivery / authorship flags.** `backend/api_modelo.py` contains Codex template/steady/index-set/inverse routes alongside earlier common API integration; historical mixed Codex/Claude authorship must be confirmed. `core/compilador/derived.py`, `derived_closure.py` and `steady.py` belong to Claude for this split, but contain several momentum/steady/reader repair deliveries; Claude must confirm complete-file ownership and their grouping. `core/modelo/lector.py`, frontend `contrato.ts`/`lector.ts`, `ModelWorksheet.tsx` and `ModelAssumptions.tsx` span template and index-set work; `ModelLibrary.tsx` spans badges/instances; `derivedSelection.ts` spans steady/inverse lifecycle; `steadyContract.ts` spans RT/inverse publication; `ResultadosHoja.tsx` spans events/inverse rendering. These are known mixed **feature** files, not evidence that Claude edited each. Authorship of every current hunk cannot be proven from git status. Shared documents and board tooling require both agents' confirmation. Do not attribute unresolved hunks to one agent by directory alone.

**Same-session additions (after the 70-entry snapshot).** Current status has 78 entries. The shared-docs bucket gains this README (already specified above); the index-set bucket gains `frontend/app/models/IndexedStageSolve.tsx` and `frontend/app/models/indexSetSolve.ts`. A new, disjoint Results-chart bucket contains `core/modelo/result_charts.py`, `frontend/motores/resultados/chartSpecification.ts`, `frontend/app/motor/ResultCharts.tsx`, `frontend/app/motor/hojasMotor.ts` and `frontend/verificar_result_charts.mjs`; proposed message: `Results: add versioned nonspatial chart specifications and shared-unit display`. Rerun TypeScript, `verificar_result_charts`, the extended app-flow verifier and fundamental suite. Chart integration also adds hunks to the already assigned `backend/api_modelo.py`, `TableroMotor.tsx`, `ResultadosHoja.tsx` and `results-format.md`; do not list or commit those files twice. The app-flow bucket now includes stage and reactor publication checks. All eight newly changed/untracked entries are assigned once; the original five holds remain. No staging or commits.

**Landing dependencies.** Template records precede instances and index sets; RT closure readers depend on Claude steady publication; F3-5 UI depends on Claude inverse readers. Common API/readers and shared presentation files make the first six groups mutually dependent as whole-file commits: validate the combined batch on a clean temporary checkout before proposing actual commit commands. The app-flow verifier follows the physics, fixture and client groups. Shared docs/snapshot land with the final accepted capability set. No staging, commit, push, deletion or physics edit is performed by this plan.

#### Closure plan phase 4: uncommitted-entry classification (29 October 2026)

Read-only preparation at HEAD `3aa86cc`; the only authorized write is this table in the existing commit section. No staging, commits, deletion, test execution or board-state change was performed. This snapshot supplements the historical checkpoint exclusions above; its categories govern this preparation.

The board currently records Claude acceptance of F3 slices 1-4, while the latest user instruction explicitly holds slices 2-4 for review. Category 2 follows that instruction, including the double-root repair and integration files. Three F3 files with unresolved earlier hunks are instead in category 4; their review hold also remains. Category 1 means accepted scope, not fresh test evidence or authorization to commit now.

Counts use exactly one row per entry from `git status --porcelain`, including collapsed untracked directories. Of 533 entries, 354 are classified: **1 ready: 7; 2 waiting for review: 36; 3 generated/scratch to discard: 0; 4 unclear authorship, for the user: 311**. Category 4 conservatively retains 257 archived data entries whose authorship is unresolved, plus 54 other entries; it does not assert that Codex authored them.

Excluded from the table and category totals: 113 paths in Claude's active `closure-phase-3a` claim (deletions and edits); 4 additional Claude thermodynamics paths; 53 shared/current or historical documentation entries, including this README and the board/Checklist; and 9 other established Claude entries (the reaction-module rescue, its test, baseline tool and Claude launch configuration). These disjoint exclusions total 179. No frozen M1 file has an uncommitted entry in this snapshot.

Reasons: **Accepted English cleanup** = `clean-en` independently accepted on the board on 29 October, with the matching assertion updates. **F3 review hold** = latest user instruction. **Mixed/unverified hunks** = prior ownership audit prevents a whole-file commit. **Archived evidence** = retain requests, reference outputs and QA data until authorship/retention is resolved; generated does not mean disposable. **Unverified integration** / **Unverified ownership** = no evidence establishing exclusive authorship and acceptance of the complete current entry. Ignored `.tmp/` outputs are outside this porcelain snapshot and are not counted as discard candidates.

| Git XY | Exact entry | Category | Reason |
|---|---|---:|---|
| ` M` | `core/compilador/__init__.py` | 1 | Accepted English cleanup |
| ` M` | `core/compilador/explicito.py` | 1 | Accepted English cleanup |
| ` M` | `core/modelo/__init__.py` | 1 | Accepted English cleanup |
| ` M` | `core/modelo/adaptadores.py` | 1 | Accepted English cleanup |
| ` M` | `core/modelo/relaciones.py` | 1 | Accepted English cleanup |
| ` M` | `tests/validar_compilador_explicito.py` | 1 | Accepted English cleanup |
| ` M` | `tests/validar_modelo_comun.py` | 1 | Accepted English cleanup |
| `??` | `core/compilador/assessment.py` | 2 | F3 review hold |
| ` M` | `core/compilador/compilador.py` | 2 | F3 review hold |
| `??` | `core/compilador/dae.py` | 2 | F3 review hold |
| ` M` | `core/compilador/derived.py` | 2 | F3 review hold |
| `??` | `core/compilador/derived_graph.py` | 2 | F3 review hold |
| `??` | `core/compilador/nonlinear_block.py` | 2 | F3 review hold |
| ` M` | `core/compilador/presentation.py` | 2 | F3 review hold |
| ` M` | `core/compilador/report.py` | 2 | F3 review hold |
| `??` | `core/compilador/steady.py` | 2 | F3 review hold |
| ` M` | `core/modelo/derived_execution.py` | 2 | F3 review hold |
| ` M` | `core/modelo/lector.py` | 2 | F3 review hold |
| ` M` | `core/resultados/formato.py` | 2 | F3 review hold |
| ` M` | `core/solvers/integrador.py` | 2 | F3 review hold |
| `??` | `core/solvers/nonlinear.py` | 2 | F3 review hold |
| ` M` | `frontend/app/models/CompilationPanel.tsx` | 2 | F3 review hold |
| ` M` | `frontend/app/models/CompilationSummary.tsx` | 2 | F3 review hold |
| ` M` | `frontend/app/models/DerivedExecution.tsx` | 2 | F3 review hold |
| ` M` | `frontend/app/models/DerivedSolve.tsx` | 2 | F3 review hold |
| ` M` | `frontend/app/models/derivedSelection.ts` | 2 | F3 review hold |
| ` M` | `frontend/app/motor/ResultadosHoja.tsx` | 2 | F3 review hold |
| ` M` | `frontend/app/motor/modeloNumerico.ts` | 2 | F3 review hold |
| ` M` | `frontend/app/motor/resolverEngine.ts` | 2 | F3 review hold |
| ` M` | `frontend/app/motor/resultadosMotor.ts` | 2 | F3 review hold |
| ` M` | `frontend/motores/modelo/assessment.ts` | 2 | F3 review hold |
| ` M` | `frontend/motores/modelo/compilation.ts` | 2 | F3 review hold |
| ` M` | `frontend/motores/modelo/derivedExecution.ts` | 2 | F3 review hold |
| ` M` | `frontend/motores/modelo/desdeHojaMotor.ts` | 2 | F3 review hold |
| `??` | `frontend/motores/modelo/steadyContract.ts` | 2 | F3 review hold |
| ` M` | `frontend/motores/resultados/lector.ts` | 2 | F3 review hold |
| `??` | `frontend/verificar_index1_dae.mjs` | 2 | F3 review hold |
| `??` | `frontend/verificar_nonlinear_algebraic.mjs` | 2 | F3 review hold |
| `??` | `frontend/verificar_steady_state.mjs` | 2 | F3 review hold |
| `??` | `tests/test_f3_index1_dae.py` | 2 | F3 review hold |
| `??` | `tests/test_f3_nonlinear_algebraic.py` | 2 | F3 review hold |
| `??` | `tests/test_f3_steady_state.py` | 2 | F3 review hold |
| `??` | `tests/test_nonlinear_solver.py` | 2 | F3 review hold |
| ` M` | `backend/api_modelo.py` | 4 | Mixed/unverified hunks |
| ` M` | `backend/motor_ensamblaje_v2.py` | 4 | Mixed/unverified hunks |
| ` M` | `core/balances/generador.py` | 4 | Mixed/unverified hunks |
| ` M` | `core/modelo/equation_workbench.py` | 4 | Mixed/unverified hunks |
| `??` | `docs/ejemplos/estudio-agua-dos-tanques-energia-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-agua-dos-tanques-energia-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-agua-dos-tanques-estacionario-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-agua-dos-tanques-estacionario-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-agua-dos-tanques-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-agua-dos-tanques-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-agua-x-distinta-de-uno-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-agua-x-distinta-de-uno-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-con-densidad-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-con-densidad-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-contradictorio-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-contradictorio-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-directo-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-directo-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-directo-validar-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-indeterminado-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-indeterminado-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-inverso-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-inverso-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-redundante-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-redundante-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-temporal-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-temporal-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-temporal-sin-frontera-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-temporal-sin-frontera-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-vaciado-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balance-general-vaciado-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balances-energia-solo-primero-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balances-energia-solo-primero-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balances-energia-solo-segundo-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balances-energia-solo-segundo-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balances-momento-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-balances-momento-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-base-masica-mezcla-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-base-masica-mezcla-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-base-masica-reaccion-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-base-masica-reaccion-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-base-masica-sin-composicion-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-base-masica-sin-composicion-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-base-masica-tanque-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-base-masica-tanque-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-capacidades.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-circuitos-serpentin-estacionario-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-circuitos-serpentin-estacionario-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-circuitos-serpentin-llenado-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-circuitos-serpentin-llenado-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-circuitos-serpentin-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-circuitos-serpentin-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-escalon-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-escalon-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-estacionario-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-estacionario-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-inicial-inconsistente-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-inicial-inconsistente-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-limite-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-limite-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-salida-lineal-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-salida-lineal-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-tau-distintas-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-tau-distintas-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-tau-distintas-validar-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-tau-iguales-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-tau-iguales-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-vaciado-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-dos-volumenes-vaciado-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-energia-ebullicion-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-energia-ebullicion-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-energia-estacionario-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-energia-estacionario-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-energia-proveedor-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-energia-proveedor-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-energia-sobreespecificada-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-energia-sobreespecificada-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-energia-tau-distintas-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-energia-tau-distintas-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-energia-tau-distintas-validar-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-energia-tau-iguales-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-energia-tau-iguales-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-energia-temperatura-impuesta-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-energia-temperatura-impuesta-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-formato-antiguo-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-formato-antiguo-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-frontera-abierta-pendiente-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-frontera-abierta-pendiente-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-frontera-cerrados-declarados-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-frontera-cerrados-declarados-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-frontera-contradictoria-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-frontera-contradictoria-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-frontera-pendiente-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-frontera-pendiente-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-fuente-q-pendiente-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-fuente-q-pendiente-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-fuente-tanque-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-fuente-tanque-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-insercion-antes-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-insercion-antes-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-insercion-completa-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-insercion-completa-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-insercion-con-rama-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-insercion-con-rama-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-insercion-estacionario-inverso-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-insercion-estacionario-inverso-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-insercion-incompleta-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-insercion-incompleta-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-dos-cerrados-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-dos-cerrados-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-en-cadena-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-en-cadena-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-estacionario-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-estacionario-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-con-energia-calor-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-con-energia-calor-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-con-energia-e-interfaz-termica-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-con-energia-e-interfaz-termica-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-con-energia-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-con-energia-proveedor-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-con-energia-proveedor-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-con-energia-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-con-energia-temperatura-comun-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-con-energia-temperatura-comun-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-energia-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-energia-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-estacionario-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-estacionario-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-inventario-constante-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-inventario-constante-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-reparto-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-reparto-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-rigida-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-rigida-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-sin-unidad-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-material-sin-unidad-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-rigida-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-rigida-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-sin-conductancia-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-interfaz-sin-conductancia-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-modelo-parcial-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-modelo-parcial-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-pared-masa-calor-especifico-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-pared-masa-calor-especifico-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-pared-serpentin-estacionario-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-pared-serpentin-estacionario-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-pared-serpentin-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-pared-serpentin-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-pared-sin-almacenamiento-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-pared-sin-almacenamiento-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-pared-sin-temperatura-inicial-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-pared-sin-temperatura-inicial-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-pared-tres-capacidades-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-pared-tres-capacidades-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-a-dos-b-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-a-dos-b-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-adiabatica-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-adiabatica-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-agotamiento-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-agotamiento-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-desde-equilibrio-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-desde-equilibrio-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-dos-reactores-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-dos-reactores-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-interfaz-cerrado-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-interfaz-cerrado-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-interfaz-craqueo-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-interfaz-craqueo-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-interfaz-estacionario-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-interfaz-estacionario-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-interfaz-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-interfaz-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-isoterma-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-isoterma-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-reversible-xilenos-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-reversible-xilenos-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-tasa-fija-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-reaccion-tasa-fija-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-contradictorio-validar-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-contradictorio-validar-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-incompleto-sin-caudal-validar-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-incompleto-sin-caudal-validar-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-incompleto-sin-inicial-validar-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-incompleto-sin-inicial-validar-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-inicial-incompatible-validar-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-inicial-incompatible-validar-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-listo-validar-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-listo-validar-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-no-evaluable-validar-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-no-evaluable-validar-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-propiedad-faltante-validar-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-propiedad-faltante-validar-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-redundante-validar-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-recuento-redundante-validar-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-tanque-termico-capacidad-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-tanque-termico-capacidad-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-tanque-termico-estacionario-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-tanque-termico-estacionario-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-tanque-termico-llenado-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-tanque-termico-llenado-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-tanque-termico-sin-presion-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-tanque-termico-sin-presion-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-tanque-termico-vaciado-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-tanque-termico-vaciado-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-agua-temporal-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-agua-temporal-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-agua-transferir-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-agua-transferir-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-cerrados-transferir-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-cerrados-transferir-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-energia-solo-primero-temporal-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-energia-solo-primero-temporal-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-energia-solo-primero-transferir-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-energia-solo-primero-transferir-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-energia-temporal-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-energia-temporal-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-energia-transferir-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-energia-transferir-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-escalon-temporal-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-escalon-temporal-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-escalon-transferir-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-escalon-transferir-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-interfaz-material-transferir-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-interfaz-material-transferir-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-rama-encendida-temporal-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-rama-encendida-temporal-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-rama-encendida-transferir-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-rama-encendida-transferir-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-reaccion-interfaz-temporal-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-reaccion-interfaz-temporal-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-reaccion-interfaz-transferir-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-reaccion-interfaz-transferir-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-reaccion-temporal-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-reaccion-temporal-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-reaccion-transferir-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-reaccion-transferir-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-sin-rama-transferir-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-transferencia-sin-rama-transferir-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-unidades-tiempo-en-minutos-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-unidades-tiempo-en-minutos-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-unidades.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-vapor-con-pared-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-vapor-con-pared-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-vapor-deja-de-condensar-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-vapor-deja-de-condensar-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-vapor-suministro-agotado-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-vapor-suministro-agotado-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-vapor-tanque-abierto-estacionario-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-vapor-tanque-abierto-estacionario-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-vapor-tanque-abierto-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-vapor-tanque-abierto-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-vapor-tanque-cerrado-peticion.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/estudio-vapor-tanque-cerrado-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/heated-filling-vessel.model.json` | 4 | Archived evidence |
| ` M` | `docs/ejemplos/laboratorio-cinetica-desde-equilibrio-respuesta.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/matter-momentum-pressure-v1.model.json` | 4 | Archived evidence |
| ` M` | `docs/ejemplos/modelo-comun/corte-vertical-benceno-tolueno-resultados.json` | 4 | Archived evidence |
| ` M` | `docs/ejemplos/modelo-comun/modelo-comun-hoja-motor.json` | 4 | Archived evidence |
| `??` | `docs/ejemplos/momentum-pressure-v1.model.json` | 4 | Archived evidence |
| ` M` | `frontend/app/checklist/checklist.module.css` | 4 | Unverified ownership |
| ` M` | `frontend/app/checklist/documento/route.ts` | 4 | Unverified ownership |
| ` M` | `frontend/app/checklist/page.tsx` | 4 | Unverified ownership |
| `??` | `frontend/app/components/ConexionProvider.tsx` | 4 | Unverified ownership |
| `??` | `frontend/app/components/MateriaFluida.tsx` | 4 | Unverified ownership |
| ` M` | `frontend/app/globals.css` | 4 | Unverified ownership |
| ` M` | `frontend/app/motor/TermodinamicaHoja.tsx` | 4 | Mixed/unverified hunks |
| ` M` | `frontend/app/motor/familiasBalance.ts` | 4 | Mixed/unverified hunks |
| ` M` | `frontend/app/motor/recorridoTermodinamico.ts` | 4 | Mixed/unverified hunks |
| ` M` | `frontend/app/motor/resultadoEnsamblajeV2.ts` | 4 | Mixed/unverified hunks |
| ` M` | `frontend/app/motor/ubicacionEcuaciones.ts` | 4 | Mixed/unverified hunks |
| `??` | `frontend/auditoria_experimentar_2026_10_12/` | 4 | Archived evidence |
| `??` | `frontend/examples/` | 4 | Unverified ownership |
| ` M` | `frontend/motores/modelo/contrato.ts` | 4 | Mixed/unverified hunks; F3 review hold also applies |
| ` M` | `frontend/motores/modelo/lector.ts` | 4 | Mixed/unverified hunks; F3 review hold also applies |
| ` M` | `frontend/motores/resultados/contrato.ts` | 4 | Mixed/unverified hunks; F3 review hold also applies |
| `??` | `frontend/qa-insercion-mesa.json` | 4 | Archived evidence |
| ` M` | `frontend/verificar_acoplamiento_materia.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_aviso_certificacion.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_bateria_multifisica.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_catalogo_motor.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_cobertura_grupos.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_consolidacion_multifasica.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_contrato_termodinamica.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_destinos_diagnosticos_red.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_diagramas_equilibrio.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_edicion_componentes_red.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_edicion_y_operaciones_red.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_energia_motor.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_entrega_h0_h1_motor.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_entrega_h3_motor.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_entrega_n_componentes.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_estructura_termodinamica.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_hojas_prueba_materia.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_integracion_ensamblaje.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_integracion_multifasica.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_integracion_unifac.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_multicomponente_materia.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_paquetes_entregados.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_preparacion_diagramas_equilibrio.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_preparacion_ensamblaje_termodinamico.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_preparacion_estado_materia.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_preparacion_paquetes.mjs` | 4 | Unverified integration |
| `??` | `frontend/verificar_recorrido_ui.mjs` | 4 | Unverified integration |
| `??` | `frontend/verificar_redesign.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_relaciones_energia.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_reparto_componentes.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_seleccion_balances.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_solver_motor.mjs` | 4 | Unverified integration |
| ` M` | `frontend/verificar_volumen_control.mjs` | 4 | Unverified integration |

##### Codex hunk-authorship resolution for the four exclusions from 5882a02 (30 October 2026)

This supplements the historical 29 October snapshot above; its 354-entry totals are not a current inventory. Read-only audit at HEAD `5882a02`, using `git diff -- <four paths>` and `git diff --ignore-space-at-eol -- <four paths>`; none of these four paths has staged hunks. Raw diff: four integrator hunks and one whole-file hunk in each TypeScript file (LF-to-CRLF). Ignoring line-ending differences yields eight semantic hunks. The table partitions those hunks where purpose or authorship differs; it does not hide the formatting changes. New-side line numbers below are this snapshot's coordinates. **18 attribution rows: 14 Codex (mine), 0 established Claude, 4 unknown.** No production/test file was edited and no tests were run for this authorship audit; test names below identify coverage, not fresh passing evidence.

Evidence: **C24** = the actual Codex patch in chat `01a16c5d-8913-7e52-b925-10746032c856`, 24 October, 21:16:13 UTC (integrator) / 21:27:35 UTC (Results physical publication), corroborated by the roadmap's F9-R7 / v2 step-(c) delivery and independent review. **F0** = that chat's F0 step-3 patch, 28 October, 06:29:39 UTC. **F3** = this chat's slice-2/3/4 implementation history, the saved `.tmp/f3-index1/before/` and `.tmp/f3-steady/before/` baselines, and Claude's 29 October acceptance of slices 2-4 and the double-root repair in the F3 roadmap. Claude explicitly records no source/test changes in that review. Roadmap ownership and acceptance alone do not establish who wrote an earlier hunk.

| File / exact diff hunk or partition | Change | Author | Evidence / disposition | Tests that exercise it |
|---|---|---|---|---|
| `core/solvers/integrador.py`, `@@ -102,6 +102,7 @@`, L105 | `Trayectoria.event_contexts` storage | Codex | C24 exact patch; v2 step-(c) publication support. | `tests/test_common_network_results.py::CommonNetworkResults::test_supercritical_event_preserves_identity_and_first_law`; v2 parity tests exercise publication consumers. |
| `core/solvers/integrador.py`, `@@ -135,10 +136,29 @@`, L139-158 | `integrar` wrapper, shared trajectory, `_integrar` extraction, classified-stop prefix retention and event trimming | Codex | C24 exact patch; R7 accepted-prefix handling, later reused by F3. | `tests/test_solver_stage_stop.py::StageStopTests::test_expected_probe_failure_retains_the_accepted_prefix` and `test_unclassified_programming_failure_is_not_certified`; `tests/test_f3_affine_algebraic.py::AffineRuntimeStopTests::test_classified_block_failure_retains_accepted_prefix`; common-network mid-run/initial probe-failure tests. |
| `core/solvers/integrador.py`, same hunk, L160-161 | Opt-in `validate_accepted(t, y)` at t0 | Codex | F3 slice-3 exact insertion in this chat; third-slice acceptance. | `tests/test_f3_index1_dae.py`, especially `test_thermal_bdf_reference_and_refinement` and `test_nonthermal_nested_bdf_reference`, traverse initial validation; no isolated t0-hook rejection assertion identified. |
| `core/solvers/integrador.py`, `@@ -184,17 +204,20 @@`, L207-208, L214 | Generic exception retry handles `step_size is None` via `h_abs`, supplies `first_step=paso_max` | Codex | C24 exact patch, not Claude's earlier `except Detencion` repair already in HEAD. | Related regression: `tests/test_solver_stage_stop.py` (RK45/BDF stage stops) and `tests/test_common_network_results.py`; no dedicated test forcing this generic-exception/None-step-size branch was established by source inspection. |
| `core/solvers/integrador.py`, same hunk, L219-220 | Validate accepted solver endpoint before retaining it | Codex | F3 slice-3 exact insertion; third-slice acceptance. | `tests/test_f3_index1_dae.py::DAEAcceptance::test_drift_and_conservation_retain_checked_prefix` injects endpoint residual/conservation failures. |
| `core/solvers/integrador.py`, `@@ -274,6 +297,8 @@`, L300-301 | Capture event state at the located signature-change time | Codex | C24 exact patch, matching `network_results.capture_event_context`. | `tests/test_common_network_results.py::CommonNetworkResults::test_supercritical_event_preserves_identity_and_first_law`; `tests/test_v2_compatibility.py` checks event/phase parity. |
| `frontend/motores/modelo/contrato.ts`, raw `@@ -1,93 +1,94 @@`, semantic `@@ -55,7 +55,8 @@`, L58-59 | `Estudio` discriminated steady variant and `TemporalStudy` alias | Codex | F3 slice-4 exact replacement in this chat; fourth-slice acceptance. | `npx tsc --noEmit` from `frontend/` checks the type; `node frontend/verificar_steady_state.mjs` exercises consumers, not erased TypeScript types. |
| `frontend/motores/modelo/contrato.ts`, remainder of raw whole-file hunk | 93 pre-existing lines LF-to-CRLF | Unknown | Already CRLF in `.tmp/f3-steady/before/frontend/motores/modelo/contrato.ts`; no origin-changing patch established. Whole-file commit remains held. | No behavioral test establishes formatting authorship; TypeScript parses either convention. |
| `frontend/motores/modelo/lector.ts`, raw `@@ -1,141 +1,147 @@`, semantic `@@ -76,7 +76,13 @@`, L79-85 | Strict version-1/damped-Newton steady study without temporal `tiempoId` | Codex | F3 slice-4 exact replacement in this chat; fourth-slice acceptance. | `node frontend/verificar_steady_state.mjs` directly calls `leerModeloComun(live.model)` and shared save/reload; `node frontend/verificar_derived_lifecycle.mjs` covers temporal compatibility. |
| `frontend/motores/modelo/lector.ts`, remainder of raw whole-file hunk | 141 pre-existing lines LF-to-CRLF | Unknown | Already CRLF in the saved pre-steady baseline; no origin-changing patch established. Whole-file commit remains held. | No behavioral test establishes formatting authorship. |
| `frontend/motores/resultados/contrato.ts`, raw `@@ -1,19 +1,26 @@`, semantic `@@ -1,4 +1,4 @@`, L1 | Documentation pointer `docs/FORMATO_RESULTADOS.md` to `docs/contracts/results-format.md` | Unknown | Predates the identified F3 changes; the canonical relocation alone does not prove who changed this comment. | No runtime coverage needed for the comment; verify the target exists. |
| `frontend/motores/resultados/contrato.ts`, semantic `@@ -13,7 +13,14 @@`, L16 | Optional `procedencia.compilation` type | Unknown | Already present as context in C24; its original author was not established from retrieved patches. Acceptance of the compiler does not settle that authorship. | TypeScript; `node frontend/verificar_derived_execution.mjs` and `node frontend/verificar_derived_lifecycle.mjs` exercise common compilation/Results publication. |
| `frontend/motores/resultados/contrato.ts`, same hunk, L17 | `steadyDiagnostics` type | Codex | F3 slice-4 edit and acceptance. | TypeScript; `node frontend/verificar_steady_state.mjs` checks publication and corrupted scalar/conditioning evidence; producer suite `tests/test_f3_steady_state.py`. |
| `frontend/motores/resultados/contrato.ts`, same hunk, L18 | `daeDiagnostics` type | Codex | F3 slice-3 exact insertion and acceptance. | TypeScript; `node frontend/verificar_index1_dae.mjs` checks live publication and malformed drift evidence; producer suite `tests/test_f3_index1_dae.py`. |
| `frontend/motores/resultados/contrato.ts`, same hunk, L19 | `nonlinearDiagnostics` type | Codex | F3 slice-2 implementation and acceptance. | TypeScript; `node frontend/verificar_nonlinear_algebraic.mjs`; producer suite `tests/test_f3_nonlinear_algebraic.py`. |
| `frontend/motores/resultados/contrato.ts`, same hunk, L20 | Optional `assessment` type | Codex | F0 exact patch and accepted step-3 scope. | TypeScript; `node frontend/verificar_model_assessment.mjs` checks typed transport, malformed evidence and persistence; producer suite `tests/test_model_assessment.py`. |
| `frontend/motores/resultados/contrato.ts`, same hunk, L21-23 | `physicalCertification`, full `equilibrium`, located `diagnostics` | Codex | C24 exact patch; accepted v2 step-(c) publication. | TypeScript; `node frontend/verificar_common_certification.mjs` directly checks certificate/equilibrium integrity; `tests/test_common_network_results.py` checks producers. No standalone generic `diagnostics` type-runtime assertion identified. |
| `frontend/motores/resultados/contrato.ts`, remainder of raw whole-file hunk | LF-to-CRLF | Codex | Saved pre-steady file has 25 LF lines and no CRLF; this chat's steady `Path.write_text` rewrite produces the current 26 CRLF lines. This resolves formatting only, not the two earlier unknown semantic additions above. | Formatting-only; TypeScript parses either convention. |

Disposition for these four entries supersedes their earlier blanket holds: the integrator's current hunks are all Codex-authored and belong to accepted R7/v2/F3 scope (category 1, subject to the required tests before any future commit). The three TypeScript files still contain unresolved earlier hunks (category 4); their identified Codex F0/v2/F3 additions are accepted scope, not currently awaiting F3 review. No current hunk was established as Claude-authored. Do not infer that the whole Results contract is Codex-only. The four unknown rows remain for the user/joint-commit decision; nothing is discarded, staged or committed by this audit.

No category-3 candidate was established in the historical snapshot. No claim was created: this audit edits only the explicitly requested shared README section, which must not be claimed. Registries are unchanged.

##### Claude entries (29 October 2026)

Covers the 66 entries the table above excludes outside the `closure-phase-3a` claim (113 entries, left to that session). Classes: **1** accepted Claude work, committed; **2** shared document or co-dependent file held for a joint commit; **3** local/generated, leave alone; **3a** phase-3a work outside its claim; **4** unclear authorship, for the user. Counts: **1: 1; 2: 16; 3: 1; 3a: 7; 4: 41**. User decision (30 October 2026) on class 4: archive all 41 in `docs/history/delivery-notes/`; the rows give the new path and commit. Links repointed in `docs/15-laboratorio.md` and `docs/engine/decision-components-ports-sources.md`; prose mentions in `docs/history/build-log.md`, earlier sections of this README and `tools/repo_cleanup/inventory.py` (a planned-destination map, not a reader) are historical and unchanged. The two repointed links are in commit `1d84705`. Only `git add -- <path>` and `git commit --only -- <path>` were used; nothing was pushed. `core/mezclas.py`, `core/mezclas_datos.py`, `core/unifac.py` and `core/ensamblaje_red.py` have no uncommitted change. The four `core/termodinamica/` entries were tested on a clean `git archive HEAD` copy plus those files: `tests/test_transient_phase_window.py` passes there, but the two derivation/event suites fail without the Codex hunks, so they are not committed alone.

| Git XY | Exact entry | Class | Owner | Commit or reason |
|---|---|---:|---|---|
| `??` | `tools/baseline_versions.py` | 1 | Claude | `66f2940`; `python tools/baseline_versions.py` exits 0 |
| ` M` | `ARCHITECTURE.md` | 2 | shared | Shared canonical document; joint shared-docs commit |
| `RM` | `core/balanceo.py -> core/reactions/balancing.py` | 3a | Claude (closure-phase-3a, clean-5) | Reaction-module rescue; the legacy modules still in HEAD import the old paths, so commit it in the same commit as the clean-4 deletions |
| `RM` | `core/lote.py -> core/reactions/batch.py` | 3a | Claude (closure-phase-3a, clean-5) | Reaction-module rescue; the legacy modules still in HEAD import the old paths, so commit it in the same commit as the clean-4 deletions |
| `RM` | `core/equilibrio.py -> core/reactions/equilibrium.py` | 3a | Claude (closure-phase-3a, clean-5) | Reaction-module rescue; the legacy modules still in HEAD import the old paths, so commit it in the same commit as the clean-4 deletions |
| `R ` | `core/cinetica.py -> core/reactions/kinetics.py` | 3a | Claude (closure-phase-3a, clean-5) | Reaction-module rescue; the legacy modules still in HEAD import the old paths, so commit it in the same commit as the clean-4 deletions |
| `R ` | `core/estequiometria.py -> core/reactions/stoichiometry.py` | 3a | Claude (closure-phase-3a, clean-5) | Reaction-module rescue; the legacy modules still in HEAD import the old paths, so commit it in the same commit as the clean-4 deletions |
| ` M` | `docs/ENTREGA_LABORATORIO_CODEX.md` -> `docs/history/delivery-notes/ENTREGA_LABORATORIO_CODEX.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| ` M` | `docs/contracts/common-model.md` | 2 | shared | Shared canonical document; joint shared-docs commit |
| ` M` | `docs/contracts/results-format.md` | 2 | shared | Shared canonical document; joint shared-docs commit |
| ` M` | `docs/engine/dynamic-assembly.md` | 2 | shared | Shared canonical document; joint shared-docs commit |
| ` M` | `docs/engine/engine-checklist.md` | 2 | shared | Shared canonical document; joint shared-docs commit |
| ` M` | `docs/engine/model-workspaces.md` | 2 | shared | Shared canonical document; joint shared-docs commit |
| ` M` | `docs/engine/multiphysics-roadmap.md` | 2 | shared | Shared canonical document; joint shared-docs commit |
| ` M` | `docs/engine/project-board.json` | 2 | shared | Shared canonical document; joint shared-docs commit |
| ` M` | `docs/engine/vertical-slice.md` | 2 | shared | Shared canonical document; joint shared-docs commit |
| ` M` | `docs/repository-cleanup/README.md` | 2 | shared | Shared canonical document; joint shared-docs commit |
| ` M` | `frontend/CLAUDE.md` | 2 | shared | Shared canonical document; joint shared-docs commit |
| ` M` | `frontend/app/checklist/datos.ts` | 2 | shared | Shared canonical document; joint shared-docs commit |
| `??` | `.claude/launch.json` | 3 | Claude | Local preview configuration; leave uncommitted |
| `??` | `core/reactions/__init__.py` | 3a | Claude (closure-phase-3a, clean-5) | Reaction-module rescue; the legacy modules still in HEAD import the old paths, so commit it in the same commit as the clean-4 deletions |
| `??` | `core/termodinamica/derivation.py` | 2 | Claude path, Codex-authored | Imported by HEAD, but HEAD plus this file fails `tests/test_thermodynamic_derivation.py` (1 failure, 1 error) and `tests/test_thermodynamic_events.py` (4 failures): needs the uncommitted `backend/api_modelo.py` and compiler hunks. Commit together with Codex's F3/Model commit, not alone |
| `??` | `core/termodinamica/equations.py` | 2 | Claude path, Codex-authored | Imported by HEAD, but HEAD plus this file fails `tests/test_thermodynamic_derivation.py` (1 failure, 1 error) and `tests/test_thermodynamic_events.py` (4 failures): needs the uncommitted `backend/api_modelo.py` and compiler hunks. Commit together with Codex's F3/Model commit, not alone |
| `??` | `frontend/AUDITORIA_EXPERIMENTAR_2026_10_12.md` -> `docs/history/delivery-notes/AUDITORIA_EXPERIMENTAR_2026_10_12.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/AUDITORIA_FRONTEND_LABORATORIO.md` -> `docs/history/delivery-notes/AUDITORIA_FRONTEND_LABORATORIO.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/AUDITORIA_FUNDAMENTOS.md` -> `docs/history/delivery-notes/AUDITORIA_FUNDAMENTOS.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/CONSOLIDACION_FUNDAMENTOS_CLAUDE.md` -> `docs/history/delivery-notes/CONSOLIDACION_FUNDAMENTOS_CLAUDE.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/CONTRATO_BACKEND_TRAZABILIDAD.md` -> `docs/history/delivery-notes/CONTRATO_BACKEND_TRAZABILIDAD.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/CONTRATO_ESTUDIOS_DINAMICOS_CLAUDE.md` -> `docs/history/delivery-notes/CONTRATO_ESTUDIOS_DINAMICOS_CLAUDE.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/CONTRATO_LABORATORIO_TERMODINAMICA.md` -> `docs/history/delivery-notes/CONTRATO_LABORATORIO_TERMODINAMICA.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/CORRECCION_EDICION_MESA.md` -> `docs/history/delivery-notes/CORRECCION_EDICION_MESA.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/ENTREGA_CLAUDE_ESPECIFICACIONES_UNIDADES.md` -> `docs/history/delivery-notes/ENTREGA_CLAUDE_ESPECIFICACIONES_UNIDADES.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/ENTREGA_CLAUDE_TRAZABILIDAD_REUTILIZACION.md` -> `docs/history/delivery-notes/ENTREGA_CLAUDE_TRAZABILIDAD_REUTILIZACION.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/ENTREGA_ENERGIA_REACTIVA_CLAUDE.md` -> `docs/history/delivery-notes/ENTREGA_ENERGIA_REACTIVA_CLAUDE.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/ENTREGA_FRONTEND_INTERFAZ_TERMICA.md` -> `docs/history/delivery-notes/ENTREGA_FRONTEND_INTERFAZ_TERMICA.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/ENTREGA_FUNDAMENTOS_CLAUDE.md` -> `docs/history/delivery-notes/ENTREGA_FUNDAMENTOS_CLAUDE.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/ESCENARIOS_AGUA_VALIDACION.md` -> `docs/history/delivery-notes/ESCENARIOS_AGUA_VALIDACION.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/ESTADO_MODELO_EXPERIMENTAR.md` -> `docs/history/delivery-notes/ESTADO_MODELO_EXPERIMENTAR.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/INCIDENCIA_TRANSFERENCIA_JSON_CLAUDE.md` -> `docs/history/delivery-notes/INCIDENCIA_TRANSFERENCIA_JSON_CLAUDE.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/INICIO_CLAUDE_MOTOR_ACOPLADO.md` -> `docs/history/delivery-notes/INICIO_CLAUDE_MOTOR_ACOPLADO.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/INTEGRACION_ENTREGAS_20_21.md` -> `docs/history/delivery-notes/INTEGRACION_ENTREGAS_20_21.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/INTEGRACION_ENTREGA_22.md` -> `docs/history/delivery-notes/INTEGRACION_ENTREGA_22.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/INTEGRACION_ENTREGA_23.md` -> `docs/history/delivery-notes/INTEGRACION_ENTREGA_23.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/INTEGRACION_ENTREGA_24.md` -> `docs/history/delivery-notes/INTEGRACION_ENTREGA_24.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/INTEGRACION_ENTREGA_25.md` -> `docs/history/delivery-notes/INTEGRACION_ENTREGA_25.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/INTEGRACION_ENTREGA_26.md` -> `docs/history/delivery-notes/INTEGRACION_ENTREGA_26.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/INTEGRACION_ENTREGA_27.md` -> `docs/history/delivery-notes/INTEGRACION_ENTREGA_27.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/INTEGRACION_ESTUDIOS_ACOPLADOS.md` -> `docs/history/delivery-notes/INTEGRACION_ESTUDIOS_ACOPLADOS.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/INTEGRACION_INSERCION_MESA.md` -> `docs/history/delivery-notes/INTEGRACION_INSERCION_MESA.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/INTEGRACION_TABLERO_UNIDADES.md` -> `docs/history/delivery-notes/INTEGRACION_TABLERO_UNIDADES.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/PASAR_A_CLAUDE_LABORATORIO.md` -> `docs/history/delivery-notes/PASAR_A_CLAUDE_LABORATORIO.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/PENDIENTES_BACKEND_CLAUDE.md` -> `docs/history/delivery-notes/PENDIENTES_BACKEND_CLAUDE.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/PLAN_CAPACIDADES_LABORATORIO.md` -> `docs/history/delivery-notes/PLAN_CAPACIDADES_LABORATORIO.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/RECORRIDO_EXPERIMENTAR_2026_10_11.md` -> `docs/history/delivery-notes/RECORRIDO_EXPERIMENTAR_2026_10_11.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/RECORRIDO_MESAS_EXPERIMENTOS.md` -> `docs/history/delivery-notes/RECORRIDO_MESAS_EXPERIMENTOS.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/RECORRIDO_TANQUE_AGUA.md` -> `docs/history/delivery-notes/RECORRIDO_TANQUE_AGUA.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/SIGUIENTE_CLAUDE_BASES_DIMENSIONES.md` -> `docs/history/delivery-notes/SIGUIENTE_CLAUDE_BASES_DIMENSIONES.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/SIGUIENTE_CLAUDE_CIERRES_TRANSFERENCIA.md` -> `docs/history/delivery-notes/SIGUIENTE_CLAUDE_CIERRES_TRANSFERENCIA.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/SIGUIENTE_CLAUDE_REACCION_INTERFAZ.md` -> `docs/history/delivery-notes/SIGUIENTE_CLAUDE_REACCION_INTERFAZ.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/SIGUIENTE_CLAUDE_TANQUES_CIRCUITOS_TERMICOS.md` -> `docs/history/delivery-notes/SIGUIENTE_CLAUDE_TANQUES_CIRCUITOS_TERMICOS.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/SIGUIENTE_CLAUDE_TRANSFERENCIA_MATERIA.md` -> `docs/history/delivery-notes/SIGUIENTE_CLAUDE_TRANSFERENCIA_MATERIA.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/SIGUIENTE_CLAUDE_TRANSFERENCIA_MATERIA_ENERGIA.md` -> `docs/history/delivery-notes/SIGUIENTE_CLAUDE_TRANSFERENCIA_MATERIA_ENERGIA.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `frontend/SUPUESTOS_POR_VOLUMEN_CLAUDE.md` -> `docs/history/delivery-notes/SUPUESTOS_POR_VOLUMEN_CLAUDE.md` | 4 | unclear | Archived by user decision; commit `5ffd765` |
| `??` | `tests/test_reaction_relations.py` | 3a | Claude (closure-phase-3a, clean-5) | Reaction-module rescue; the legacy modules still in HEAD import the old paths, so commit it in the same commit as the clean-4 deletions |
| `??` | `tests/test_thermodynamic_derivation.py` | 2 | Claude path, Codex-authored | Imported by HEAD, but HEAD plus this file fails `tests/test_thermodynamic_derivation.py` (1 failure, 1 error) and `tests/test_thermodynamic_events.py` (4 failures): needs the uncommitted `backend/api_modelo.py` and compiler hunks. Commit together with Codex's F3/Model commit, not alone |
| `??` | `tests/test_thermodynamic_events.py` | 2 | Claude path, Codex-authored | Imported by HEAD, but HEAD plus this file fails `tests/test_thermodynamic_derivation.py` (1 failure, 1 error) and `tests/test_thermodynamic_events.py` (4 failures): needs the uncommitted `backend/api_modelo.py` and compiler hunks. Commit together with Codex's F3/Model commit, not alone |

#### Closure plan phase 4b: clean-HEAD check and joint-commit plan (30 October 2026)

Read-only for the main checkout; this subsection is the only edit. Checked on a temporary `git worktree` of HEAD `5882a02` (removed afterwards), adding uncommitted files one at a time from the main checkout. Logs are in the ignored `.tmp/claude-phase-4b/`.

**Clean HEAD.** All six packages import (`core.compilador`, `core.modelo`, `core.mezclas`, `core.termodinamica`, `backend.main`, `backend.api_modelo`), because their `__init__` files do not load the missing module. `core.compilador.presentation` and every F3 acceptance suite fail on `from core.termodinamica import derivation`. `test_nonlinear_solver` (17) and `test_transient_phase_window` (2) pass on clean HEAD.

| Failure on clean HEAD | Fixed by (verified by single-file overlay) |
|---|---|
| `test_f3_affine_algebraic`, `test_f3_index1_dae`, `test_f3_nonlinear_algebraic`, `test_f3_steady_state`, `test_material_derivation`: `ImportError` for `core.termodinamica.derivation` | untracked `core/termodinamica/derivation.py` + `equations.py`; affine then passes 7/7 |
| `test_f3_nonlinear_algebraic`: 6 errors, `FileNotFoundError .tmp/f3-nonlinear/model.json` | No file is missing: the test writes into `.tmp/f3-nonlinear/` without creating it, and a fresh checkout has no such ignored directory. With the directory created it passes 8/8 on HEAD + thermodynamics alone. Needs a `mkdir(parents=True, exist_ok=True)` in the committed test (Codex) |
| `test_f3_index1_dae`: 3 failures (`'resuelto' != 'parcial'`, empty failed publication) | uncommitted `core/solvers/integrador.py` (13/13 with it) |
| `test_f3_steady_state::test_common_http_and_compilation`: no `describe_compilation` | uncommitted `backend/api_modelo.py` |
| `test_thermodynamic_derivation::test_route_response_and_invalid_owner`: no `thermodynamic_derivation` | uncommitted `backend/api_modelo.py` |
| `test_thermodynamic_derivation::test_native_api_rejects_forged_closure`, `test_material_derivation::test_v2_api_rejects_forged_journal_before_thermodynamics` | uncommitted `backend/motor_ensamblaje_v2.py` |
| `test_thermodynamic_events`: 3 failures (`aparicion_fase` with empty `faseIds`) | `core/solvers/integrador.py` + `backend/motor_ensamblaje_v2.py` together (6/6); integrador alone still fails 3 |
| `test_material_derivation`: 2 failures (`"Transform"`, `"algebraic"` do not match the English admission messages) | No uncommitted file fixes it: committed `core/compilador/admission.py` (`0a8431a`) emits the English text and the committed test still expects the old words. Same 2 failures on the dirty tree. Needs an assertion update in the test (Codex) |

With derivation/equations, their two tests, the ten group-b Python files and the created directory, all target suites pass except those 2 stale assertions.

**Joint-commit plan.** 461 porcelain entries at the time of writing (459 plus two new f8b three-liquid files). Groups are disjoint and cover every entry. Every commit uses `git add -- <path>` and `git commit --only -- <paths>`; nothing is pushed until the user confirms the final state.

| Order | Group | Entries | Paths | Proposed message | Tests before committing |
|---:|---|---:|---|---|---|
| 1 | c. Thermodynamics modules | 4 | `core/termodinamica/derivation.py`, `equations.py`, `tests/test_thermodynamic_derivation.py`, `tests/test_thermodynamic_events.py` | `Thermodynamics: add the derivation and equation-graph modules HEAD already imports` | Import of `core.compilador.presentation`; `test_f3_affine_algebraic`. The two thermodynamic suites pass only after group b, so commit b right after c, or fold them into one commit |
| 2 | b. Mixed engine code | 15 | `backend/api_modelo.py`, `backend/motor_ensamblaje_v2.py`, `core/solvers/integrador.py`, `core/balances/generador.py`, `core/modelo/{__init__,adaptadores,equation_workbench,relaciones}.py`, `core/compilador/{__init__,explicito}.py`, `tests/validar_compilador_explicito.py`, `tests/validar_modelo_comun.py`, `frontend/motores/modelo/{contrato,lector}.ts`, `frontend/motores/resultados/contrato.ts` | `Engine: commit the common API, v2 route and integrator hunks the F3 slices depend on` | F3 suites, `test_thermodynamic_derivation`, `test_thermodynamic_events`, `test_material_derivation` (after the two Codex test fixes above), the two `validar_*` suites, TypeScript check |
| 3 | a. Clean-4 deletions and reaction rescue | 115 | The 106 `D` entries (Process Simulation backend, legacy `core/` operations, `thermodynamics/`, `config/settings.py`, legacy `tests/validar_*`, `/flowsheet`, `/termodinamica` and their components and verifiers, `tools/legacy_reference/freeze_legacy_distillation.py`, root examples), the 5 `core/reactions/` renames, `core/reactions/__init__.py`, `tests/test_reaction_relations.py`, `backend/main.py`, `empaquetado/construir.ps1` | `Cleanup: delete Process Simulation and thermodynamics/, and move the reaction modules to core/reactions` | `backend.main` import, `test_reaction_relations`, every remaining `tests/validar_*.py` and `tests/test_*.py`, `frontend` TypeScript check |
| 4 | d1. Engine frontend and verifiers | 42 | the 32 modified `frontend/verificar_*.mjs`; `frontend/verificar_recorrido_ui.mjs`; `frontend/app/motor/{TermodinamicaHoja.tsx,familiasBalance.ts,recorridoTermodinamico.ts,resultadoEnsamblajeV2.ts,ubicacionEcuaciones.ts}`; `frontend/package.json`; `frontend/app/checklist/{page.tsx,checklist.module.css,documento/route.ts}` | `Frontend: update the engine sheets and verifiers for the English engine and the deleted routes` | `node verificar_todo.mjs`, `verificar_physical_journals.mjs`, TypeScript check |
| 5 | d2. Home redesign | 7 | `frontend/app/{page.tsx,layout.tsx,globals.css}`, `frontend/app/components/{NavBar.tsx,ConexionProvider.tsx,MateriaFluida.tsx}`, `frontend/verificar_redesign.mjs` | `Frontend: home and navigation redesign` | `verificar_redesign.mjs`, TypeScript check, a production build |
| 6 | e. Regenerated examples | 257 | `docs/ejemplos/` (254 untracked studies, 3 modified examples) | `Examples: add the regenerated study and engine reference outputs` | The v1 readers and verifiers that walk `docs/ejemplos/` by prefix; `npm run test:motor-fundamental` |
| 7 | f. Shared documents and registries | 12 | `ARCHITECTURE.md`, `docs/contracts/{common-model,results-format}.md`, `docs/engine/{dynamic-assembly,engine-checklist,model-workspaces,multiphysics-roadmap,vertical-slice}.md`, `docs/engine/project-board.json`, this README, `frontend/CLAUDE.md`, `frontend/app/checklist/datos.ts` | `Docs: joint update of the canonical documents, board and Checklist` | `node tools/roadmap_board/build_board.mjs --check`, `python tools/repo_cleanup/check_links.py`, Checklist snapshot generation |
| — | Not committed | 9 | f8b in progress: `core/mezclas.py` (its only hunk is `lv_ln_k`), `core/termodinamica/{lv_continuation,three_liquid}.py`, `tests/test_{lv_arclength_continuation,three_liquid_ternary}.py`. Local: `.claude/launch.json`. Archived evidence with unresolved retention: `frontend/auditoria_experimentar_2026_10_12/`, `frontend/qa-insercion-mesa.json`, `frontend/examples/` | — | — |

Group a goes after b because `backend/main.py` and `empaquetado/construir.ps1` only make sense with the deletions, and nothing in b imports a deleted module; its order relative to b is otherwise free. Group f goes last and waits for the f8b session, which is editing the roadmap, board and Checklist (`datos.ts`); the f8b files themselves are excluded entirely, since `core/mezclas.py` has no non-f8b hunk.

**Authorship not resolved.**

- Group b: `api_modelo.py`, `motor_ensamblaje_v2.py`, `generador.py`, `equation_workbench.py` and the three `frontend/motores/` contracts mix Codex engine work with Claude retirement and cleanup hunks (24 and 29 October checkpoints). The tests prove what HEAD needs, not who wrote each hunk; commit them as one joint, co-authored commit after both agents confirm.
- The two committed-test defects (`.tmp/f3-nonlinear/` creation and the 2 stale assertions) are Codex-owned F3/M1 test files and are not in the working tree; they need an edit before group b can pass on a clean checkout.
- Group d2: the redesign (Spanish UI text, 847-line `globals.css`) has no recorded owner, and `NavBar.tsx`, `layout.tsx` and `page.tsx` also hold the clean-4 removal of the old navigation, so they cannot be split from it without rewriting another author's hunks. User decision (30 October 2026): commit d2 as is, as a checkpoint. **Pending under `clean-en`:** translate the Spanish interface text in `frontend/app/page.tsx`, `layout.tsx`, `components/NavBar.tsx`, `ConexionProvider.tsx` and `MateriaFluida.tsx` to English.
- Group d1: `frontend/package.json` mixes Codex test scripts with Claude's removal of laboratory scripts; the Checklist page, CSS and document route have no recorded owner.
- Group e: 257 archived data entries remain unresolved, as in the phase-4 table.
- `frontend/examples/heatedFillingVessel.ts` is untracked with no recorded owner, and the library must not import examples; it stays out until the user decides.

**Result (30 October 2026).** The user approved groups 1–6. Each was committed with `git add -- <paths>` and `git commit --only -- <paths>`, after checking that its diff held no f8b hunk. Nothing was pushed.

| Order | Group | Commit | Entries |
|---:|---|---|---:|
| 1 | c | `703a732` | 4 |
| 2 | b | `b35929a` | 15 |
| 3 | a | `ad8c90a` | 115 |
| 4 | d1 | `e3fdde9` | 42 |
| 5 | d2 | `9dc231c` | 7 |
| 6 | e | `4805eed` | 257 |

Codex's `42abf4a` (the `.tmp/f3-nonlinear/` creation and the current admission assertions) landed between b and a. Group b's message credits Claude hunks, but Codex's later hunk-by-hunk table establishes none as Claude's; the commit was left as it is.

- **Clean HEAD `4805eed`** (fresh worktree, removed afterwards). Every module in the import smoke imports, including `core.compilador.presentation` and `core.reactions`. The ten target suites pass 94/94: material and thermodynamic derivation, reaction relations, nonlinear solver, the four F3 suites, thermodynamic events and the transient phase window.
- **Main tree, `validar_*.py`:** 20 of 22 pass. `validar_motor_balances` passes 29/30 because it still expects the earlier `motor de balances:` message prefix. `validar_capa_unifac` exceeded the 15-minute limit.
- **Main tree, `test_*.py`:** every suite that finished passed. `test_v2_compatibility` and `test_v2_route_switch` exceeded the 25-minute limit after collection; they are not import failures.
- **Frontend verifiers** (run one by one against a local API on 8001, without a frontend server): 59 of 65 pass. Six do not pass, and each reflects current content rather than the commit split:
  - `verificar_cobertura_grupos` and `verificar_consolidacion_multifasica` find a stale contract copy;
  - `verificar_compilador_explicito` and `verificar_corte_vertical` still expect implicit Euler, which the compiler now rejects;
  - `verificar_paquetes_entregados` requires CLI arguments, so it is not a standalone suite;
  - `verificar_bateria_multifisica` timed out;
  - `verificar_redesign` cannot run, because `puppeteer-core` is not installed.
- **Validator rewrites.** The runs rewrote five `docs/ejemplos/modelo-comun/` files; they are still uncommitted:
  - `balances-llenado-entrada-caliente.json` and `explicito-agotamiento.json` change only the English labels;
  - `corte-vertical-benceno-tolueno-resultados.json` has substantive changes (8 checks instead of 3, 20 series instead of 15, new `procedencia` keys);
  - `capa-calentamiento-benceno-tolueno.json` and `capa-ebullicion-agua.json` differ only by numerical noise near the phase transitions (relative event-time differences up to 2.4e-8).

  They were not restored, because `git checkout` was denied in this session. The two `capa-*` files can be restored; the other three show that the committed examples are stale relative to the committed code.
- **Group f** (shared documents and registries) was committed on 31 October 2026 as the commit tagged `f0-baseline`, after the f8b, F5 and F3-5 sessions finished. It also carries `docs/engine/multiphysics-battery.md` and the new `docs/engine/codex-queue.md`. The three stale examples were committed as 2f19456; the two noise-only `capa-*` rewrites were restored. Details are in the roadmap's "F0 baseline frozen in git" paragraph. Nothing is pushed.

## 8. Regenerating the inventory

```bash
python tools/repo_cleanup/inventory.py --summary
```

The script only reads the repository (git listings and file contents) and writes `docs/repository-cleanup/inventory.csv`. Rerun it after each phase: the `changes` column should shrink until only reviewed exceptions remain.
