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

## 7. Decisions

On 2026-10-19 the user accepted the proposals and left the open choice (D4) to the best option for the project.

- **D1. UI language: the interface text stays in Spanish.** File names, documents and new code are English; what the end user reads on screen is not part of this cleanup.
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

## 8. Regenerating the inventory

```bash
python tools/repo_cleanup/inventory.py --summary
```

The script only reads the repository (git listings and file contents) and writes `docs/repository-cleanup/inventory.csv`. Rerun it after each phase: the `changes` column should shrink until only reviewed exceptions remain.
