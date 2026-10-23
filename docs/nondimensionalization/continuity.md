# Continuity: nondimensionalization core (Claude)

Date: 17 October 2026 (translated to English on 19 October 2026). It is for picking the work back up in a new Claude Code session without the chat history. It does not replace the plan ([docs/history/frontend/plan-nondimensionalization-equations.md](../history/frontend/plan-nondimensionalization-equations.md), the only plan and record) or the contract ([docs/contracts/nondimensionalization-core.md](../contracts/nondimensionalization-core.md)).

## Start-up message

> Resume the nondimensionalization core. Read, in this order: `docs/nondimensionalization/continuity.md`, `docs/history/frontend/delivery-claude-nondimensionalization.md` (it may have new corrections from the user or from Codex), `docs/contracts/nondimensionalization-core.md` and the sections "Implementación Claude" and "Ampliación Claude" of `docs/history/frontend/plan-nondimensionalization-equations.md`. Run `python tests/validar_adimensionalizacion.py` to confirm the state before changing anything. No commit or push.

## Division of work and rules that do not change

- **Claude:** the scientific core in Python, its tests, the contract and the canonical examples.
- **Codex:** the `/adimensionalizacion` interface, readers, persistence and export. Since 18 October 2026 the user also assigned that interface to Claude ("right now you will work on it"), with the engine's look and without overloading the pages.
- Codex edits the plan, the delivery and sometimes the contract **in parallel**: reread them before touching them.
- The client does no scientific algebra; the core is not duplicated in the browser.
- `/motor`, `/laboratorio`, their solvers, thermodynamics and `core/dimensiones.py` are not modified. Of the frontend, only `/adimensionalizacion`.
- No new dependencies: sympy is installed but is **not** in `requirements.txt` and is not used. The algebra is the project's own (`fractions`); pint only interprets units.
- No commit or push unless explicitly asked.
- Nothing is ever published as "proven" if it was not proven; when in doubt, `no_demostrada`, `pendiente` or a diagnosis.

## Where each thing is

| File | Content |
|---|---|
| `core/adimensionalizacion/racional.py` | Fractions, exact incremental Gaussian elimination, null space |
| `core/adimensionalizacion/algebra.py` | Canonical form; modes `conservar`, `cartesiano`, `expandir`; `es_cero` by denominators |
| `core/adimensionalizacion/dimensional.py` | A1: inference, compatible/incompatible/undetermined, `faltantes`, units with pint |
| `core/adimensionalizacion/lector.py` | Strict reader: documents v1 and v2, `transformaciones`, `referencias`, `prioridadEscalas`, `opciones`, exploration settings |
| `core/adimensionalizacion/transformacion.py` | `Preparado`: maps v = g(v′) (scales are the multiplicative case), chain rule, global factor, A3 by rank; `ALCANCE_EQUIVALENCIA` |
| `core/adimensionalizacion/formulacion.py` | Published formulation, groups, constraints, certificate by back substitution |
| `core/adimensionalizacion/desarrollo.py` | Trace `desarrollo: PasoDesarrollo[]` |
| `core/adimensionalizacion/grupos_pi.py` | Π groups and alternative bases |
| `core/adimensionalizacion/nucleo.py` | `procesar(solicitud)` and `capacidades()`; operations `analizar`, `transformar`, `adimensionalizar`, `explorar` |
| `core/adimensionalizacion/transformacion.py` (v2) | `escalar_llamadas` / `deshacer_llamadas` (function scales), `_preparar_prioridad`, references in `_transformar_igualdad` |
| `tests/validar_adimensionalizacion.py` | Suite (249 checks as of 17 October, section "Contrato v2 del documento"); part of `python run_tests.py` |
| `tests/casos_adimensionalizacion.py` | Builders of test documents |
| `tests/generar_ejemplos_adimensionalizacion.py` | Generates the 18 pairs `docs/ejemplos/adimensionalizacion-*-{solicitud,resultado}.json` (2 of them v2) |

## State as of 17 October 2026

**Done in the core:**

- A0: contract published.
- A1: dimensions, with `requiere_datos` and the indispensable data.
- A2: transformation with a certificate.
- A3: targets by exact rank.
- Complete automatic search from the equation alone.
- Invertible affine and nonlinear maps, with the inverse proven.
- Π groups.
- Complete trace.

**Done by Codex (connected; do not touch from the core):**

- Endpoint: `backend/api_adimensionalizacion.py`, registered in `backend/main.py` (§7 of the contract), with `GET /capacidades`, `POST ""` and `POST /dimensiones`.
- Dimensional layer `backend/dimensiones_adimensionalizacion.py` (§12), with its suite `tests/validar_capa_dimensional.py`.
- Reader `frontend/app/adimensionalizacion/lecturaNucleo.ts`, validity rule, the "Adimensionalizar" button and the sheet notebook.
- **Local** v2 document with `Forma.transformaciones`. The `prepararSolicitud` adapter sends the core a v1 copy and moves the maps into `SolicitudNucleo.transformaciones`.

**Done in the core on 17 October: document v2** (§13 of the contract). It accepts `terminoId` in targets, `condiciones[].ubicacion`, `funciones[].escala` (`D(c) = D* D̂(u)`), `Forma.referencias`, `Forma.prioridadEscalas` and `Forma.transformaciones`, plus `opciones.referencias` and `opciones.prioridadEscalas` in the automatic search. The v1 output does not change. Codex does not send v2 yet: it has to update types, reader and inputs, and resolve the calls to `D̂` against `funcionesAdimensionales`.

**Done on 17–18 October: audit of Gemini's frontend and real studies.**

- Operation `estudiar` (contract §14) with nine analyses, in `estudio.py`, `asintotica.py`, `dinamica.py`, `simetrias.py`, `simulacion.py` and `numerico.py`.
- New interface: `EstudioFormulacion.tsx`, `Vista*.tsx`, `GraficoXY.tsx`, `ComparadorFormulaciones.tsx`, `informe.ts`, `lecturaEstudio.ts`, `contratoEstudio.ts`, `usoEstudio.ts` and `estudio.css`.
- 23 modules retired to `docs/history/archive/nondimensionalization-gemini-2026-10-17/`.
- Report: [docs/history/frontend/audit-nondimensionalization-2026-10-18.md](../history/frontend/audit-nondimensionalization-2026-10-18.md).
- Plan with the engine: [docs/history/frontend/plan-connection-nondimensionalization-engine.md](../history/frontend/plan-connection-nondimensionalization-engine.md), phases M1–M4, with four user decisions pending (§5).

**Done on 18 October: phase M1 with the engine.** `desdeMotor.ts` translates an engine matter sheet (read-only) into a v2 document + SI values; `origenMotor.ts` stores the link in `adim.motor.<documentoId>`; `ComparacionMotor.tsx` + `diferenciaMotor.ts` compare with the engine's saved result. The notebook uses the engine's CSS modules (`trabajoMotor`, `balances`, `motor`). Core: `simulacion.periodica` and `simulacion.tFinalSI`.

**Done on 18 October: module closed.** Scope in [docs/nondimensionalization/scope.md](scope.md). The sheet follows the engine's path (`EntradaSimple.tsx` carries the navigation and the equations page; `ResultadosNucleo.tsx` the formulations, study, development and compare pages). `Editor.tsx` provides the "Opciones avanzadas". Results are saved in `resultadosAdim.ts` (IndexedDB).

**Done on 19 October: only equations derived in an Engine sheet** (ARCHITECTURE.md §11). The only entry is importing a sheet, its equations are read-only, and hand-written documents are retired (`hojas.ts`, `retirarEscritas`). Details in [docs/nondimensionalization/scope.md](scope.md).

**Pending** (outside the closed scope; see the scope document):

- Phases M2 (mesh diagnosis with the engine's limits) and M3 (thermodynamic volumes) of the engine plan.
- Translate `step`, state rules and a variable mean density on import.
- Automatic proposal of nonlinear maps (log, powers).
- Coupled or curvilinear changes of coordinates and scales that depend on t/x.
- Non-monomial targets and the expansion of `div(D(c) grad c)` on request.
- Simulation in more than one coordinate.

## Known traps

- **Canonical examples.** If any output field changes, run `python tests/generar_ejemplos_adimensionalizacion.py`; otherwise the suite fails, and that is intended: it detects stale examples.
- **Scope of the certificate.** If the identities the algebra uses change, update `ALCANCE_EQUIVALENCIA` and the "Certificado" section of the contract together.
- **Patch scripts.** Write them with Write, never as a bash heredoc, which eats backslashes and quotes. Open files with `newline=''` so LF is not turned into CRLF.
- **Gemini's mathematics.** Whatever the core did not calculate and test against an analytical reference is not a result, even if a document calls it "certified" (see the audit).
- **The user's backends without reload.** Ports 8004/8005 are started without `--reload`: after changing the core they must be restarted. For testing, use your own backend on another port (for example, 8011) and do not stop other people's.
- **Studies.** The suite `tests/validar_estudio_adimensionalizacion.py` takes about 40 s. The `estudio-*` examples are regenerated with the same generator.
- **Running.** Run the suites from the root with `PYTHONIOENCODING=utf-8`. After changing the core, also run `python tests/validar_capa_dimensional.py` (Codex's wrapper depends on the core's output).
- **`backend/main.py`** only registers the routers since cleanup phase 3; edit it with a script that opens it with `newline=''`, not with Edit.
- **Frontend checks** (from `frontend/`): `node verificar_adimensionalizacion.mjs`, `verificar_integracion_adimensionalizacion.mjs`, `verificar_capa_dimensional.mjs`, `verificar_estudio_adimensionalizacion.mjs`, `verificar_importacion_motor.mjs` (calls Python, ~1 min), `npx tsc --noEmit --incremental false` and `npx eslint app/adimensionalizacion`.
- **File names on Windows** are case-insensitive: `comparacionMotor.ts` and `ComparacionMotor.tsx` collide. That is why the pure module is called `diferenciaMotor.ts`.
- **Engine:** it is not modified. Nondimensionalization only imports its pure functions and CSS modules.
