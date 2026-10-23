# Simulation engine architecture

**The entry document for any person or LLM** (Claude, Codex, Gemini…) who works in this repository. It explains what the simulator is, which pieces it is made of, which rules are never broken, and where each piece lives today. It is the reference for structure; the progress of each physical phase is tracked in [docs/engine/multiphysics-roadmap.md](docs/engine/multiphysics-roadmap.md).

Version 1 · 18 October 2026 · The approach was approved by the user; the migration is in progress (see §10). Translated to English on 19 October 2026 (repository cleanup, [docs/repository-cleanup/README.md](docs/repository-cleanup/README.md)).

**Latest user decision, 19 October 2026:** the Engine has four connected workspaces, **Model → Transform → Solve → Results**. Section 12 governs their boundaries and all future work; the older navigation in §5 and §11 describes the earlier plan. Transform extends the same physical model; its selected output feeds compilation and execution. The [first scaling execution bridge and compilation report](docs/contracts/common-model.md#7-implemented-transform-execution-and-compilation-report) are implemented within their declared ODE scope. All new and changed code, documentation and interface text are in English. Published contract identifiers require a compatible migration before translation.

---

**Current priority, 20 October 2026:** consolidate nonspatial thermodynamics and its compilation/results consistency before any further spatial work. Existing spatial paths are retained; new discretization, geometry and spatial coupling are deferred. The product library has no predefined-example loader. Examples are created on demand through the same fundamental-law operations and `ModelWorksheet`; new equations or assumptions extend its family content and right-hand panel, never introduce another UI. Former example constructors are internal regression inputs, not a catalog to reload into the user's library. See the [maintained workspace specification](docs/engine/model-workspaces.md#clean-library-and-nonspatial-consolidation-20-october-2026).

## 1. What it is

An **equation-oriented** simulator of chemical processes. The user does not pick a "unit" or a "scenario":

1. they start from the general conservation laws;
2. they reduce them, with explicit assumptions, to the model they want;
3. the system solves it, analyses it and presents it.

The architecture is an **engine of engines**:

- each small engine does one thing, has an input contract and an output contract, and does not know the others;
- they all speak one language: the **common model** (§4);
- the interface does not calculate; it only composes engines and presents what they return.

Working analogy: each engine is a gear on its own shaft. A new gear (for example, nondimensionalization) is mounted between two others without rewriting them. An example, a test case or a "demo" does **not** bring its own code: it is a document (data) that goes through the same gears. Its charts come from the charting engine, not from a component made for it.

## 2. Principles that are never broken

1. **One model.** Every equation, variable, unit, domain, condition and assumption lives in the common representation (§4). There is no "one equation to show and another to solve".
2. **Thermodynamics is always present** (§3). No phase is assumed by default.
3. **Assumptions are traceable transformations.** Each reduction is an operation on the model with its validity condition, its author (user or rule) and its effect. It can be undone and audited. A history of flags beside a prewritten terminal equation is insufficient: the shared equation engine must apply the reduction and retain its input equations, mathematical rule and derived result. Missing operations are implemented in the engine before rebuilding the example; numerical configuration must never inject an undeduced physical relation.
4. **The client does no science.** Symbolic algebra, solvers, thermodynamics and units run in the backend (Python). The browser edits documents and presents results. (Current exception, still to migrate: the engine's TS solver, §6.)
5. **One service per responsibility.** One unit system, one results format, one charting engine, one document store. Duplicating any of them is a defect.
6. **Contract first.** Before an engine or a screen is written, its contract (input, output, errors, version) and its strict reader are fixed. Fields the backend does not publish are never invented.
7. **Nothing is published as proven unless it was proven.** An uncertain result is marked `no_demostrada`, `pendiente` or `requiere_datos`; a model the engine cannot handle is rejected with the reason, never approximated silently.
8. **Every piece is tested against an independent reference** (analytical, published, or another method), not only against itself.
9. **No bias toward any operation.** The fundamental equations give what they must give for any component, mixture or configuration.
10. **Every model ALWAYS starts from the fundamental equations** (user rule, 19 October 2026). The model that is needed is reached through assumptions, applied one at a time and recorded. The model is never posed directly.
    - This holds for each family, each in its own panel: local conservation of matter, the first law of energy, momentum, and the fundamental thermodynamic relations.
    - **Thermodynamics:** the state assumptions (number of phases, phase change, constant density, declared u(T), package) are declared in the thermodynamic derivation (`frontend/app/motor/recorridoTermodinamico.ts`), not in the energy derivation. The energy balance uses them through its effective formulation (`formulacionEnergiaHoja`).
    - **Thermodynamic networks:** recorded material, first-law and thermodynamic journals use Python replay/development and must match the compiled assumptions. `ModelWorksheet.tsx` owns the single Model layout for every family and ordinary, coupled, network, blank or legacy document: mathematical development and variables on the left, one assumptions panel on the right. `ModelAssumptions.tsx` supplies shared controls; physical-system and topology configuration stay in the same panel. Storage adapters never select an alternative layout. Examples are input documents; creating one must not introduce another Model editor. The old library, document toolbar, modular editor and reconstructed network derivation frontend have been removed; legacy URLs redirect into `/models`. This stable presentation is an explicit user requirement, reaffirmed on 20 October 2026.
      - **Audit correction:** a legacy explanation reconstructed from final flags does not establish a deduction journal. All 42 current templates now record shared material, first-law and thermodynamic operations as applicable, with Python replay against the actual physical input. Saved legacy models retain their evidence limitations and require deliberate rebuilds; their histories are never fabricated. The phase-discovery vessel is an ordinary input-only model under the same standard. See [the model derivation audit](docs/engine/model-workspaces.md#model-derivation-standard-and-audit).
    - No engine has branches by type of equipment ("tank", "column", "reactor") or by scenario name.
    - Quantities are defined by their dimension, not by a list of units.
    - The candidate phases are fixed by the package, not by the case.
    - Results and charts do not know where they come from.
    - A concrete operation is a combination of laws, assumptions and data: never code of its own.

## 3. Thermodynamics as a permanent part of the model

Thermodynamics is not a property table that is looked up when needed. It is a **set of relations that is part of every model with matter and energy**, even when a particular case seems not to need it.

### 3.1 The idea

The state of each volume is described by **conserved quantities**: moles of each species nᵢ, internal energy U (or enthalpy H when the pressure is prescribed) and volume V. The balances integrate only those quantities. At every evaluation, the **equilibrium closure** solves, from (n, U, V) or (n, H, P), the temperature, the pressure, how many phases there are, and the amount and composition of each one.

The equations of every possible phase **are always there**:

- **Subcooled liquid:** the calculation gives β_vapor = 0; the amount of vapor is zero and its equilibrium condition stays an inequality (non-negative tangent plane).
- **On heating:** the accumulated energy reaches the bubble point. There the vapor condition becomes an equality and β_vapor starts to grow from zero.
- **At the end:** with enough heating, the liquid disappears in the same way.

The model does not change, no "vapor mode" is switched on, and no new equation appears: it is the same formulation, which gave zero before and does not now. That is how the engine **knows** a liquid is a liquid, not because the user declared it. It can therefore go through boiling, condensation or the appearance of a second liquid phase without discontinuities in the model.

Mathematically it is a complementarity condition per phase k: βₖ ≥ 0, tangent-plane distance TPDₖ ≥ 0, and βₖ·TPDₖ = 0.

### 3.2 What does change when a phase appears

The properties have a **kink** at the saturation boundary: the derivative of h(T) changes abruptly and the apparent cp jumps. That is physics, not a change of equations.

The integrator handles it this way:

1. it detects the instant at which the set of phases changes;
2. it locates it by bisection;
3. it restarts there, so as not to average across the kink.

The event is a numerical technique for accuracy. The model does not change.

### 3.3 The three pieces of the thermodynamic layer

| Piece | What it is | Example |
|---|---|---|
| Data and parameters | Database with source, unit, domain and fingerprint | Tc, Pc, Psat(T), ideal Cp, v_L, NRTL parameters, UNIFAC groups |
| State model | The package's thermodynamic potential, from which every property derives | IAPWS-95, ideal gas + ideal solution, NRTL, UNIFAC |
| Equilibrium closure | The always-present relations: given (n, U, V) or (n, H, P), it returns T, P, phases, βₖ, compositions, potentials and a stability certificate | UV, PH and TP flash, with a stability test |

The balances (the Formulate layer) never contain a "fixed" property that contradicts the package. A linear u(T) or an "assumed phase" exists only as an **explicit assumption**, recorded by the assumptions engine, with its validity domain watched during the calculation.

### 3.4 Current state against this principle

| Path | Complies? | Detail |
|---|---|---|
| Assembly backend (`core/ensamblaje_dinamico.py`, `core/ensamblaje_red.py`) | **Yes** | State (n, U) or (n, H); UV or PH closure at every evaluation; phase events only to restart the integrator; samples certified with a full flash |
| Common-model compiler (`core/compilador/`) | **Yes** | State (n, U or H); the layer's closure at every evaluation; events only to restart the integrator |
| Common-model thermodynamic layer (`core/termodinamica/capa.py`) | **Yes** | Candidate phases fixed by package; every state publishes all of them with β, composition and tm; complementarity β·tm = 0 ([docs/contracts/thermodynamic-layer.md](docs/contracts/thermodynamic-layer.md)) |
| The engine's TS solver (`frontend/app/motor/modeloEnergia.ts`) | No | Manual linear u(T) and a phase "assumed without verification". It must become an explicit assumption or move to the real closure |
| Nondimensionalization (`core/adimensionalizacion`) | Not yet applicable | It does not see thermodynamics. When coupled, properties enter as functions with a declared scale, for example h(T) = c_p,ref·T_ref·ĥ(T̂), without the core operating on the package |

## 4. The common model

It was the missing piece and the first one built (§10). One versioned representation, with a strict reader in Python and in TypeScript.

| Entity | Content |
|---|---|
| Symbol | id, role (time, coordinate, field, parameter, constant), exact dimension, unit, sign, dependencies |
| Expression | typed tree: number, symbol, sum, product, quotient, power, function, call to a declared function, derivative, gradient, divergence, Laplacian |
| Equation | equality with id, family (matter, energy, momentum, constitutive, thermodynamics, definition) and provenance |
| Volume / domain | region with its conserved quantities, its boundary and its thermodynamic package |
| Stream / connection | topology: origin, destination, mechanism, what it carries |
| Condition | initial or boundary, with its location |
| Assumption | operation applied, validity condition, who applied it, equations affected |
| Declared function | properties and laws the model uses but does not develop, with dimension and, where relevant, scale (h(T, P, x), D(c)…) |
| Provenance | where each element comes from: template, assumption, user, engine |

Starting point: the nondimensionalization v2 document ([frontend/app/adimensionalizacion/contrato.ts](frontend/app/adimensionalizacion/contrato.ts) and [docs/contracts/nondimensionalization-core.md](docs/contracts/nondimensionalization-core.md)). It was the most complete representation available: exact dimensions, differential operators, domains, located conditions and functions with scale. It lacked volumes, streams, assumptions and the thermodynamic layer, which were added.

## 5. The engines

Each engine has an input contract, an output contract and typed errors. It has no interface, knows no other engine except through the common model, and has its own tests.

### Formulate

| Engine | Does | Input → output |
|---|---|---|
| Balances | Library of general laws in local form: matter per species, energy (first law), momentum, entropy | family + components → local equations |
| Assumptions | Reduces the model with traceable operations: integrate over the volume, Gauss, Reynolds, invariances, uniformity, ports, steady state… | model + operation → model + record |
| Constitutive | Laws plugged into terms: Fick, Fourier, kinetics, discharge laws, interphase transfer | term + law → developed term |
| Topology | Composes several volumes and streams into one model; incidences, internal connections | volumes + streams → assembled model |
| Thermodynamics | Adds to each volume its equilibrium closure (§3) | volume + package → state relations |

### Transform and analyse

| Engine | Does | Input → output |
|---|---|---|
| Units and dimensions | Parses units, converts to SI, infers dimensions, checks homogeneity | model → diagnosis + dimensions |
| Structure | Degrees of freedom, data versus unknowns, system type (ODE, DAE, algebraic), rank and index | model + data → count + classification |
| Nondimensionalization | Scales, certified formulations, groups, Π theorem | model → scaled model + groups |
| Discretization | PDE → semi-discrete system with the chosen scheme (finite volumes, method of lines, scheme order) | model + mesh → ODE or DAE system |

### Calculate

| Engine | Does | Input → output |
|---|---|---|
| Properties | Evaluates a package's state model and equilibrium closure | (n, U, V) or (T, P, x) → certified state |
| Compiler | Model + data → numerical functions (right-hand side, Jacobian, events) | model + data → numerical system |
| Solvers | Integrate or solve without knowing physics: explicit and implicit ODEs, DAEs, steady state (Newton), continuation | numerical system → trajectory |
| Studies | Stability, dominant regime, sensitivity, continuation, symmetries | model (+ values) → analysis |

### Present and check

| Engine | Does | Input → output |
|---|---|---|
| Results | One series format: variable, unit, domain, time, provenance, signature | trajectory → result set |
| Charts | The only charting and diagram engine; it takes results and a specification | results + specification → figure |
| Verification | Conservation residuals, second law, certificates, comparison with references | results + model → verification report |
| Reports | LaTeX, CSV, PDF/HTML, Python script | model + results → file |

### Cross-cutting

| Engine | Does |
|---|---|
| Document | The sheet is the project: model, data, assumptions, results and views. One store, versions, signatures that invalidate whatever depends on them |
| Catalog | Components, packages and **templates** (examples are templates: documents, never code) |
| Orchestrator | The path of a sheet: which engine is called at each step and with what |

### The path of a sheet

Formulate (balances → assumptions → constitutive → topology → thermodynamics) → Data → Units and Structure → (Nondimensionalize, optional) → Discretize → Compile → Solve → Results → Charts, Verification, Studies, Reports.

In the interface each step is **the view of an engine**, not an independent module.

## 6. Where each piece lives today

What exists works and is tested, but it is scattered and duplicated. This table is the starting point of the migration.

| Engine | Today | Note |
|---|---|---|
| Common model | `core/modelo/`, `frontend/motores/modelo/` | v0: representation, reader and relations; the Engine's Resolver and the balance engine consume it |
| Thermodynamic layer | `core/termodinamica/` | Fixed candidate phases and complementarity on top of `core/mezclas` and `core/agua_iapws95` |
| Balances + Assumptions | **Server-side balance engine: `core/balances/`** ([docs/engine/balance-engine.md](docs/engine/balance-engine.md)): generates the matter equations (volume networks) and the energy equations with an assumed u(T) from each volume's assumptions. The derivation that is shown stays in the client: `frontend/app/motor/recorridoMateria.ts`, `operadores.ts`, `recorridoEnergia.ts` | The visible derivation and the executable generation coexist; momentum includes symbolic deductions and the scoped reduced hydraulic compiler |
| Topology | `frontend/app/motor/ensamblajeMateria.ts` (mass, TS); `backend/motor_ensamblaje_v2.py` + `core/ensamblaje_red.py` (thermodynamic network) | Two implementations |
| Thermodynamics | `core/agua_iapws95.py`, `core/mezclas.py`, `core/unifac.py`, `core/hielo_ih.py`, `core/coexistencia_lv.py`, `core/catalogo.py`, `backend/motor_termodinamica.py` | Correct and cross-checked (thousands of checks). The base for §3 |
| Units | **One service, `core/unidades/`** (`/unidades/*`, [docs/contracts/units-service.md](docs/contracts/units-service.md)). Still in use, to migrate: `frontend/app/motor/unidadesMotor.ts`, `backend/motor_ensamblaje.UNIDADES`, `core/adimensionalizacion/dimensional.py`, `core/dimensiones.py` | Equivalence checked unit by unit against all four |
| Expressions | `frontend/app/motor/expresionesMotor.ts`, `core/expresiones_motor.py`, `frontend/app/adimensionalizacion/contrato.ts` | **Three representations** |
| Structure | `analizarMotor` in `modeloNumerico.ts` (structural count) | Count only |
| Nondimensionalization | `core/adimensionalizacion/` (core), `frontend/app/adimensionalizacion/` | Closed within its scope: [docs/nondimensionalization/scope.md](docs/nondimensionalization/scope.md) |
| Discretization | Upwind finite volumes in `modeloNumerico.ts`; centred method of lines in `core/adimensionalizacion/simulacion.py` | Two schemes in two places |
| Compiler + Solvers | **The common model's own: `core/compilador/` and `core/solvers/`** (vertical slice). Still in use: TS `modeloNumerico.ts` and `integracionMotor.ts`; Python `core/ensamblaje_*.py` and `core/adimensionalizacion/simulacion.py` (BDF, method of lines) | The common compiler reproduces the engine's assemblies; 1D and the TS solver are still to migrate |
| Studies | `core/adimensionalizacion/{estudio,dinamica,asintotica,simetrias}.py` | Tied to the dimensionless model; they must accept any model |
| Results | **Common format `core/resultados/` and `frontend/motores/resultados/`** ([docs/contracts/results-format.md](docs/contracts/results-format.md)). The core simulation publishes it; the v2 assembly and the TS solver have an adapter | `ResultadoMotor` and `RespuestaResolucionV2` stay as their own outputs until their engines migrate |
| Charts | **One engine, `frontend/componentes/graficas/`** (pure data + renderer); nondimensionalization uses it. To migrate: `frontend/app/motor/TableroMotor.tsx` and `frontend/app/components/Diagrama*.tsx` | `GraficoXY.tsx` archived |
| Verification | Backend residuals and certificates; comparison in `diferenciaMotor.ts` | Scattered |
| Reports | `frontend/app/adimensionalizacion/{informe,exportar,exportarDesarrollo}.ts`, the engine's CSV | Scattered |
| Document | localStorage `rage.motor.hojas.v1` + IndexedDB `rage-motor-resultados`; localStorage `rage.adimensionalizacion.hojas.v1` + IndexedDB `rage-adimensionalizacion-resultados` | **Two stores** |

Detailed functional map of the current engine: [docs/engine/engine-map.md](docs/engine/engine-map.md).

**Outside the new engine** (earlier work, not modified without an explicit request): `/columna`, `/flowsheet`, `/termodinamica`, `thermodynamics/`, and the classic modules of `core/` (McCabe-Thiele, Ponchon-Savarit, FUG, CSTR, PFR, column…). Their future is pending a decision (§9). The laboratory (`/laboratorio`) was deleted on 22 October 2026 by user decision; a full working-tree backup is in the local ref `refs/backups/pre-lab-deletion-2026-10-22`.

## 7. Target code organization

```
core/                     Python: one package per engine
  modelo/                 common representation, reader and version
  balances/  supuestos/  constitutivas/  topologia/
  termodinamica/          data, state models, equilibrium closure
  unidades/  estructura/  adimensionalizacion/  discretizacion/
  compilador/  solvers/  estudios/  resultados/  verificacion/  informes/
backend/                  FastAPI: one route per engine, no physics logic
frontend/
  motores/<engine>/       TS contract, HTTP client and strict reader (no UI)
  componentes/            shared visual pieces: chart, formula,
                          field with unit, figures panel, tables
  app/hojas/[id]/<step>/  pages of a sheet's path; they compose
                          engines, they do not calculate
docs/                     mathematical foundations per engine
tests/                    tests per engine against independent references
```

Package and folder names will move to English during the repository cleanup ([docs/repository-cleanup/README.md](docs/repository-cleanup/README.md), phase 6). The migration is incremental (§10): no current module is rewritten in one go, and its suites must keep passing at every step.

## 8. Working rules for any agent

- **Read before touching:** this document; then the continuity document of the affected engine ([docs/nondimensionalization/continuity.md](docs/nondimensionalization/continuity.md), [docs/engine/multiphysics-roadmap.md](docs/engine/multiphysics-roadmap.md)) and its contract.
- **Maintain documentation in place:** follow the [documentation maintenance standard](docs/README.md#documentation-maintenance-standard). Existing architecture, contracts, workspace specifications and roadmaps are updated; a new change, session or agent does not justify a new document (user decision, 19 October 2026).
- **Do not modify the current engine (`frontend/app/motor`, `backend/motor_*.py`, `core/ensamblaje_*.py`) without an explicit request from the user.** The migration happens in approved steps.
- **Contract first:** every change to an engine's output updates its contract, its canonical examples (`docs/ejemplos/`) and its strict reader in the same change.
- **Tests:** each engine has its suite. Changing an engine requires running its suite and the suites of its consumers.
  - nondimensionalization: [docs/nondimensionalization/scope.md](docs/nondimensionalization/scope.md) §Verification;
  - engine: `npm run test:motor-fundamental` and `tests/validar_motor_*.py`.
- **Git:** no commit or push unless asked. When committing, file by file, never `git add -A`: the tree carries changes from several authors. Working branch: `fase-a-adopcion`.
- **Processes:** the user's backends run on 8004 (general) and 8005 (nondimensionalization) and the frontend on 3000. Use another port for testing. Do not stop other people's processes; if one of your own must be stopped, do it by PID, never by name.
- **Editing:** `backend/main.py` only creates the app and registers the routers (cleanup phase 3). Routes live in `backend/routes_engine.py` (`/motor/*`), `backend/routes_process_simulation.py` (legacy side) and the existing `backend/api_*.py` routers. `backend/main.py` keeps CRLF endings and the new route modules use LF; edit backend files with a script that opens them with `newline=''`. Do not use heredocs for scripts that contain backslashes.
- **Language:** all new and changed documents, code, identifiers and interface text are written in English (latest user decision, 19 October 2026). Existing published contracts, routes and persisted keys are not translated in place: use explicit versioning and compatible migrations. This supersedes the earlier Spanish-interface policy in [docs/repository-cleanup/README.md](docs/repository-cleanup/README.md) §7.
- **Each equation goes in its place** (user rule, 19 October 2026). A panel of the sheet shows only the equations of its physical family, never "all of the system's":
  - **Matter:** conservation per component, flow and composition of each stream, global matter check.
  - **Energy:** first law, stream enthalpy, heat between volumes, boundary work, global energy check.
  - **Momentum:** momentum.
  - **Thermodynamics:** state closure and phase equilibrium, with its stability.
  - The classification lives in one place, `frontend/app/motor/ubicacionEcuaciones.ts`. An equation without a place is an engine error. `frontend/verificar_ubicacion_ecuaciones.mjs` checks that every equation the Engine publishes in the examples has exactly one place.
  - A new family of equations is classified there before it is shown.
- **Science:** every formula or API that comes from another source (including another LLM) is implemented and checked numerically against a reference before it is accepted.

## 9. User decisions

### 9.1 Taken (18 October 2026)

1. **UNIFAC has full priority; NRTL is not worked on.** The NRTL packages stay published and their suites must keep passing, but they are not extended, not cross-checked further and not used as the guide case for new pieces. Every new test of non-ideal mixtures uses UNIFAC (`unifac-original-public`, `unifac-dortmund-public`, `unifac-original-lle-public`).
2. **Priority on polishing thermodynamics** (§10, block A).
3. **Discretization and meshing are not nondimensionalization.** They belong to the transformation/solvers engine and are a step **after** scaling in the sheet's path (§5, §11). The method of lines that lives today in `core/adimensionalizacion/simulacion.py` will move to a discretization engine of its own (`core/discretizacion/`); nondimensionalization keeps scales, groups, certified formulations and studies.
4. **Polish the balances** according to what is pending in the checklist (`/checklist`, `frontend/app/checklist/datos.ts`) (§10, block B).
5. **Unify Equations and Nondimensionalization** into one path of the sheet, so the user sees how the engine works (§11).
6. **Where the calculation lives:** in Python (approved with step 5). The engine's TS solver is replaced by the common compiler and solvers once parity is shown.
7. **The final goal is to simulate multiphysics, not to have UNIFAC at 100 %.** The experimental contrast of UNIFAC (and of any package) is done **at the end**. What matters now is that the Engine works end to end: start from the fundamental equations, simplify them with assumptions, and solve. The model is general: nothing is biased so that it solves one type of model.
8. **Visible name:** the page the navigation bar called "Ecuaciones" (`/motor`) is called **Engine**. Routes and code keep `motor`; the "Ecuaciones" step inside each sheet is still the equations step.
9. **Multiphysics battery:** `frontend/verificar_bateria_multifisica.mjs` runs every test sheet through the common path and writes [docs/engine/multiphysics-battery.md](docs/engine/multiphysics-battery.md), with what it solves and what is missing, by reason. It is the common Engine's worklist.

### 9.2 Open

1. **Where the calculation lives.** *(Resolved in 9.1.6; the original text is kept.)* Proposal: everything in Python, migrating the engine's TS solver. Alternative: keep a light solver in the browser for immediate response.
2. **What goes into the engine.** Are `/laboratorio`, `/columna`, `/flowsheet` and `/termodinamica` rebuilt as templates and studies of the engine, or do they stay as legacy? *(Resolved: cleanup decision D6 deletes the Process Simulation side, and on 22 October 2026 the user deleted the laboratory instead of rebuilding it; see [the cleanup plan](docs/repository-cleanup/README.md#7-decisions).)*
3. **Division of work.** Today only Claude works on this. With separate engines, each agent can take specific engines without stepping on another.

## 10. Work order

1. **Common model v0** — **done on 18 October 2026.**
   - Contract: [docs/contracts/common-model.md](docs/contracts/common-model.md).
   - Code: `core/modelo/` (reader, always-present relations, adapters) and `frontend/motores/modelo/` (types, reader and adapter for the engine's sheets).
   - Tests: `tests/validar_modelo_comun.py` (102) and `frontend/verificar_modelo_comun.mjs` (117).
   - The three cases (the TS engine's matter sheets, the thermodynamic assembly's v2 requests and the nondimensionalization documents) fit without loss. The model's structural relations match the equations the backend generates in 23 assemblies.
2. **Thermodynamics as a layer of the model** — **done on 18 October 2026** for the mixture packages: [docs/contracts/thermodynamic-layer.md](docs/contracts/thermodynamic-layer.md), `core/termodinamica/`.
   - Each volume has a fixed set of candidate phases. Every state publishes, per phase, its amount, its composition (or the incipient one) and its distance to the tangent plane, with complementarity β·tm = 0.
   - Guide test `tests/validar_capa_termodinamica.py` (179 checks): benzene and toluene heated until fully vaporized. The same equations from start to end; bubble and dew points equal to Raoult in closed form (1e-4 K) and to Antoine (0.02 K).
   - Pure water (IAPWS-95) wrapped with its boiling test `tests/validar_capa_agua.py` (161 checks), cross-checked against IF97 and published tables.
3. **One units service**, **one results format** and **one charting engine** — **done on 18 October 2026.**
   - Units: `core/unidades/` and `/unidades/*`. 264 checks, plus 235 against the engine's table; exact equivalence with the four earlier systems.
   - Results: `core/resultados/` and `frontend/motores/resultados/`. 34 checks.
   - Charts: `frontend/componentes/graficas/`. 175 checks with results from three different engines drawn by the same code.
   - The old systems keep working until each engine is migrated (step 5).
4. **Vertical slice** — **done on 18 October 2026:** [docs/engine/vertical-slice.md](docs/engine/vertical-slice.md).
   - The common model is solved with its own compiler and solver (`core/compilador`, `core/solvers`), with output in the common format and in the charting engine.
   - Routes: `POST /modelo/validar` and `POST /modelo/resolver`.
   - Tests: `tests/validar_corte_vertical.py` (71) and `frontend/verificar_corte_vertical.mjs` (14).
   - The same code, with no branches per case, reproduces the guide test, the boiling water and the engine's four assemblies, within 1e-7 to 1e-16 of the existing engine.
   - The current screens keep working.
5. **Migration engine by engine:** balances and assumptions to the backend; the TS solver replaced by the common compiler and solvers; nondimensionalization and studies consume the common model.
   - **5.1, core done on 18 October 2026:** the compiler has a second input that runs written equations (`core/compilador/explicito.py`); the solver supports BDF and domain events (it stops at the exact instant a non-negative variable would run out). Contract: `restricciones` and values `datos["matematico.<id>"]` ([docs/contracts/common-model.md](docs/contracts/common-model.md)). Evidence in [docs/engine/vertical-slice.md](docs/engine/vertical-slice.md) §5: `tests/validar_compilador_explicito.py` (27, against analytical solutions) and `frontend/verificar_compilador_explicito.mjs` (76: the six matter sheets without a spatial field, with RK45 and with the implicit method, equal to the TS solver and to the analytical solution).
   - **5.1 closed on 18 October 2026:** the Engine's Resolver (`frontend/app/motor/resolverEngine.ts`, `resolverHojaEngine`) calculates on the server (`POST /modelo/resolver`) every sheet that reaches the common Engine: 21 test sheets (single-domain matter, volume networks and energy with u(T)).
     - The common result is translated into the `ResultadoMotor` the views already read. States, derived quantities (`observables`) and budget closures (`verificaciones`) are published by the server.
     - `frontend/verificar_resolver_engine.mjs` (178) checks, field by field, that it equals the browser's earlier calculation. It was also checked in the browser.
     - The browser solver remains only for 1D fields and volumetric substitution. `resolverHoja`, the local solver, still exists for those forms and for the suites that test it.
     - **Requirement:** the backend the interface uses (8004) must have the `/modelo/*` routes and `core/balances` loaded; if it is older, the Resolver answers "Servicio del Engine no disponible (HTTP 404)".
   - **5.3, 5.4 and the core of 5.5, done on 18 October 2026:** the balance engine (`core/balances`, [docs/engine/balance-engine.md](docs/engine/balance-engine.md)) generates on the server the equations of volume networks and of energy with an assumed u(T), from each volume's assumptions. `tests/validar_motor_balances.py` (27, against analytical solutions) and the multiphysics battery: the 10 networks and the 6 energy sheets equal to the current Engine.
   - **Rest of step 5:** 5.2 discretization (an engine of its own, §9.1.3); the rest of 5.5 (volumetric substitution, state rules, momentum); 5.6 nondimensionalization and studies on the common model.
6. **Frontend reorganization** according to §7, with the sheet's path as the only navigation (§11).

### Current order (18 October 2026, decisions §9.1)

**A. Thermodynamics (first), only UNIFAC for non-ideal mixtures.**

1. Thermodynamic layer and common compiler tested with the three UNIFAC packages — **done on 18 October 2026:** `tests/validar_capa_unifac.py` (82), [docs/contracts/thermodynamic-layer.md](docs/contracts/thermodynamic-layer.md) §4.
   - The engine's seven dynamic UNIFAC requests give the same state and the same events as the engine. Phase appearances match independent references (`thermo`): γ-φ bubble point, LLE binodal and tangent plane.
   - The compiler now honours the phase policy (event `politica_incumplida`).
   - **Finding, fixed the same day:** the existing engine published the second liquid phase of the five-species network 28 s late, because it accepted a step without an event when it did not find the change again in the reintegrated state. Fixed in `core/ensamblaje_red.py` and the example regenerated; engine, common compiler and independent reference agree ([docs/engine/engine-map.md](docs/engine/engine-map.md) §6).
   - **Next within A:** the layer's performance with UNIFAC (the five-species network takes ~255 s) and the pending items of point 2.
2. Pending thermodynamics items from the checklist that apply: material streams between IAPWS and mixture packages; complete L–L and L–L–V diagrams (today L–L is detected but not drawn); continuation of curves with folds; multicomponent slices. The experimental contrast of UNIFAC is **deferred to the end** (§9.1.7).
3. Deferred for physical scope (each needs a new model, not polishing): non-ideal vapor and high pressure, critical regions, solid–liquid equilibrium of mixtures, chemical equilibrium coupled to reactions.
4. Out by decision: "complete parameters and NRTL contrasts with 5 or more components".

**B. Balances: what is pending in the checklist.**

| Pending | Class | Goes with |
|---|---|---|
| Selective transfer coupled to thermodynamics in /motor | polishing balances | A + v2 network |
| Reaction kinetics coupled to the real thermodynamics | polishing balances (constitutive) | with reaction energy |
| Reaction energy with consistent thermodynamic references | polishing balances | with the previous one |
| Solid phase change during the dynamics | balances + thermodynamics | ice Ih already exists in statics |
| Heat and mass transfer out of equilibrium | constitutive | after the first two |
| Detection of transitions the step sampling misses | solver | signature events of the common solver |
| Discontinuous pressures with a physical jump rule | balances | — |
| Flows and work coupled to the momentum balance | balances (momentum) | later |
| General inverse solution of assembled systems | structure + solvers | later |
| Spatial resolution in other geometries and dimensions; spatial energy transport | **discretization** (§9.1.3) | 5.2, a later step |

**C. Single sheet** (§11), starting with the read-only bridge.

**Across A, B and C: make the Engine work** (§9.1.7). Each block is tested with the multiphysics battery (§9.1.9), and whatever the battery does not solve through the common path is tackled first, if it is general.

**D. The rest of step 5 and step 6.**

Each step closes with its tests and with an update of this document.

## 11. Single sheet: Equations and Nondimensionalization in one path

Today they are two pages with two stores: `/motor/hojas/[id]` (balance derivation, state, resolver, charts) and `/adimensionalizacion` (notebook of equation documents, scaling, groups, studies, simulation). The user does not see that they are **the same model** at different steps. The proposal is **one document, the sheet (common model), and one path**; each step is the view of an engine:

| Step | Engine | Today it is in | What the user sees |
|---|---|---|---|
| 1. Formulate | balances + assumptions, and the thermodynamic derivation | Equations of `/motor` | The local equation, each assumption applied and the final equation, by family. **There are no "written equations" sheets** (principle 10): every model is derived from the fundamental equations |
| 2. State | thermodynamics | State of `/motor` | Components, package (UNIFAC), candidate phases, equilibrium sample, diagrams |
| 3. Data and structure | units + structure | part of the Resolver of `/motor` | Data with units, count of variables and equations, degrees of freedom |
| 4. Scale (optional) | nondimensionalization | `/adimensionalizacion` | Scales, dimensionless groups, certified formulations, dominant regime, studies. **It neither integrates nor meshes** |
| 5. Discretize (only with spatial fields) | discretization | Advanced options of the Resolver; nondimensionalization's method of lines | Mesh, scheme, Péclet and cell diagnostics |
| 6. Solve | compiler + solvers | TS solver; nondimensionalization's simulation; v2 assembly | Method, tolerances, state and events |
| 7. Results | results + charts | Charts of `/motor`; nondimensionalization's views | One dashboard; the same series in physical variables or scaled with the scales of step 4 |

**Rules.**

- Step 4 reads and writes `motores.adimensionalizacion` of the same common model; it never copies the model. The scales do not change the equations of step 1: they are a view and a recorded transformation.
- The simulation stops being a view of nondimensionalization: it is step 6 on the same model (explicit compiler, §10 step 5.1), with the discretization of step 5 when there are spatial fields.
- One store of sheets (§6, Document). Nondimensionalization works on the equations the sheet derives, never on a hand-written model (principle 10).
  - **Decided (19 October 2026):** nondimensionalization works only on equations derived in an Engine sheet.
    - Its only entry is importing a sheet; the equations of a derived document are not edited there.
    - Documents written directly are retired (kept so they can be exported). Details in [docs/nondimensionalization/scope.md](docs/nondimensionalization/scope.md).
    - What does not arrive this way today (reaction with its thermodynamics, energy in 1D, non-material systems) will arrive when the Engine can derive it.
  - The compiler's written-equations input (`core/compilador/explicito.py`) stays: it is how the Engine runs what the balance engine generates, not a way of posing models.
- The library shows templates, not examples with code of their own.

**Done (18 October 2026):**

- Every sheet, including the thermodynamic-network sheets of the examples, shows the same four panels: Matter, Energy, Momentum and Thermodynamics (§3; [docs/contracts/thermodynamic-layer.md](docs/contracts/thermodynamic-layer.md) §4 bis).
- The Thermodynamics panel shows the always-present relations, each volume's closure (from `POST /modelo/termodinamica`) and the possible thermodynamic assumptions.
- The Resolver calculates on the common Engine (§10, 5.1).

**Incremental order** (each stage leaves both pages working and their suites green):

1. *Read-only bridge:* in the engine's sheet, a "Scale" tab that mounts the nondimensionalization views on `modeloDesdeHojaMotor(hoja)`; the manual import ("From the engine") disappears.
2. *Common Resolver:* the sheet's Resolver uses `POST /modelo/resolver` (closes 5.1) and nondimensionalization's simulation view uses the same result.
3. *One store:* nondimensionalization uses the Engine's sheet store. Its hand-written documents were retired (decision above).
4. *Routes:* `/hojas/[id]/<step>` (§7); `/motor` and `/adimensionalizacion` become redirects.

## 12. Four-workspace framework (user decision, 19 October 2026)

**Finite usability objective (user decision, 22 October 2026).** The [M1 milestone](docs/engine/multiphysics-roadmap.md#m1--minimum-usable-multiphysics-engine) sets a fixed three-case nonspatial acceptance suite and two gates. D1 verifies sufficient deduction capability and ends general kernel polishing; U1 delivers the exact Transform/Solve/Results path for that scope. After D1, extend the kernel only for a reproduced M1 blocker or a confirmed correctness defect. Broader symbolic completeness, unused adapter migration and full distillation-column support are later milestones. This priority supersedes open-ended deduction expansion; neither gate is certified by defining it.

**Mathematical foundation below multiphysics (22 October 2026).** `core/mathematics` owns typed equation graphs, algebra/calculus, dimensional checks, conditional operations and chronological replay. It does not import physical families, thermodynamic packages, equipment, the model compiler or solvers. Physical adapters supply fundamental laws, definitions and constitutive premises; multiphysics connects their quantities and interfaces; numerical adapters admit only supported derived systems. The kernel accepts arbitrary equation groups and explicitly declared units, including non-chemical models. Names and equipment categories never select its mathematical rules. Existing physical-family controls remain adapters in the same Model worksheet; extracting the kernel does not claim that every physical control already has a chronological algebraic proof or that every symbolic graph is numerically executable.

The kernel also records typed real/sign domains, bounded exact intervals and singleton parameter cases, with actual specialization rows before inversion. Typed SI constants preserve units in nonzero parameter cases, and explicit interval-unit conversions use exact catalog factors from the shared units service. It proves domain membership when selecting among complete degree-one/two polynomial root sets. Accepted and excluded branches remain visible in the existing equation rows. Unresolved membership and unsupported inversions are findings; new domain premises require numerical admission before Solve. Newly recorded equation operations pin their input expressions, conditions and units. Replay retains actual before/after equations and rejects changed algebra behind an unchanged equation ID. Legacy unsigned histories remain unsigned. See the [common operation contract](docs/contracts/common-model.md#13-selectable-equation-operations-in-model) and the maintained [execution plan](docs/engine/multiphysics-roadmap.md#general-deduction-engine-execution-plan-21-october-2026) for verified scope and remaining work.

The four workspaces organize one connected Engine. They are not separate applications or a mandatory sequence of four independent calculations. Every future request is first assigned to a primary workspace, with its inputs, outputs, consumers and invalidation rules identified before implementation. A capability may serve several workspaces through a shared contract; its scientific implementation is not duplicated.

**Dynamic conservation decision (20 October 2026):** retain every active conservation law as `dI/dt = Phi`. A permanent fixed-inventory assumption adds `I(t)=I(t0)` and compatibility `Phi=0`; it does not delete a state or replace the balance by a steady-only model. Total mass, individual component amounts and energy have distinct ownership and constraints. An initially stationary operating point belongs to Solve initialization and must permit later perturbations without changing physical equations. Dependent flows must be explicitly identified; no controller or changed boundary value is invented. The Model authoring contract, review of legacy flags and current execution guards are defined in [common-model.md §10](docs/contracts/common-model.md#10-dynamic-inventory-definition-model-first). This increment completes the nonspatial Model policy foundation, not general constrained integration or real-time execution. Next physical work is momentum in Model; Transform/Solve extensions follow separately.

**Momentum clarification and Model implementation (20 October 2026):** Navier–Stokes and machine models must be deduced through recorded assumptions, exactly like matter and energy. The new Python momentum journal starts at Cauchy conservation, declares Newtonian stress, and records every integration, port, hydraulic, angular and ideal-blade reduction. An ideal centrifugal characteristic additionally needs explicit mass/angular/energy passage constraints and geometric/constitutive assumptions; it is never a hard-coded equipment scenario or a curve claimed to follow from conservation alone. All balances remain visible. Pressure/flow/shaft-work relations feed the same common model and their own physical panels. Model deductions and execution guards are specified in [common model §11](docs/contracts/common-model.md#11-momentum-deduction-cauchy-to-reduced-machines). The subsequent [reduced hydraulic increment (§12)](docs/contracts/common-model.md#12-reduced-hydraulic-execution) now executes constant-density isothermal laminar paths, recovered pressure and hydrostatic storage/matter coupling on the shared RK45/BDF solvers. General pump, energy/rotor, constrained-network and spatial execution remain pending.

**Product decision and frontend implementation:** the saved user-facing object is a **model**, replacing "sheet" in the interface. The canonical library is `/models`; every model has Model, Transform, Solve and Results workspaces. Model preserves the derivation and assumptions without run controls. Transform includes any supported mathematical technique, not only nondimensionalization. Numerical data and remaining degrees of freedom are completed in Solve. The implementation, compatibility boundaries, current limitations and handoff for Claude are in [model-workspaces.md](docs/engine/model-workspaces.md). Earlier references to sheets describe the existing internal document and storage, not the product terminology.

| Workspace | Owns | Produces |
|---|---|---|
| Model | Fundamental laws, recorded physical assumptions, constitutive relations, thermodynamic packages and closures, topology, physical geometry, data with units, unknowns, initial and boundary conditions | A physical/mathematical problem in the common representation, independent of a numerical method |
| Transform | Nondimensionalization, invertible variable maps, algebraic reformulation, spatial meshes and discretization, recorded numerical approximations | A derived formulation with provenance, validity conditions, variable/domain/condition maps and approximation metadata |
| Solve | A compatible execution plan, numerical compilation, solver-dependent assembly, time integration, nonlinear/linear methods, initialization, tolerances and events | A versioned run with its actual method, diagnostics, termination reason and common results |
| Results | Final dimensional or dimensionless solution, charts, conservation and constraint checks, numerical accuracy studies, comparison and reports | Views and verification tied to the exact model, formulation and run that produced them |

### Shared services and dependencies

- Keep the common model, expression representation, units service, structural analysis, thermodynamic implementation, results format and sheet store shared. Validate at the boundaries that need them; do not make separate copies per workspace.
- Model defines thermodynamic relations; Solve evaluates the same closure as the state changes. A property calculated once in Model is not a replacement for that coupling.
- Physical assumptions belong to Model even though their implementation transforms equations. Numerical approximations belong to Transform. Physical geometry and boundary conditions are specified in Model; their mesh representation belongs to Transform.
- Nondimensionalization is optional. Each transformation declares its admissible input and ordering; no unsupported composition or reordering is assumed valid. A discretization is marked as an approximation, not certified as an exact equivalence.
- Transform and Solve coordinate through the numerical formulation and method requirements. Concrete matrices or Jacobians can depend on the time step, state and iteration; they are assembled or updated when the chosen method needs them. Do not require every solver to consume one preassembled matrix.
- **Proposed equation-to-solver boundary:** compile the active equation graph into residuals and constraints, with explicit ODE and nested-closure execution as supported specializations. Removed terms do not automatically remove unknowns; valid elimination requires reconstruction and structural checks. Thermodynamics may be coupled or solved as a nested closure, with its coupling preserved. The detailed design and current implementation limits are maintained in [common-model.md §6](docs/contracts/common-model.md#6-proposed-equation-to-solver-boundary); this is not a claim of implemented general DAE support.
- Retain the original model and record derived formulations. Each result identifies its model revision, transformation branch, numerical settings and relevant data/package versions. An upstream change invalidates dependent artifacts; a new solver tolerance creates a new run without changing the physical model. Names and presentation changes do not invalidate science.
- Preserve dimensional meaning through variable maps, conditions and tolerance conversion. Unknown dimensions remain unknown; incompatible equations are rejected. Quantity names cannot be inferred uniquely from dimensions alone.
- Report structural solvability, supported capability, solver convergence and numerical accuracy separately. Unsupported DAEs or missing consistent initialization are diagnosed, not silently reduced to explicit ODEs. Successful integration does not certify mesh convergence or physical validity.
- Studies use Model or Transform inputs and invoke Solve when calculations are needed; Results presents their output. Studies do not acquire a second compiler or solver.

### Multiphysics composition architecture

User decision, 21 October 2026: composition must remain **multiphysics**. The approved architectural direction below governs implementation; hierarchical instance assembly is still pending and must not be listed as delivered. A physical region owns field or inventory balances and their assumptions. A model is a reusable mathematical definition that may contain one or several regions, relations and connections. Region boundaries follow the physical approximation, not an equipment catalog. A thermodynamic phase does not automatically require a separate region.

Allow a model to contain instances of reusable model definitions, recursively, as well as directly authored regions. Each instance needs its own identity, parameter bindings and state, a pinned definition revision, and explicitly exposed ports. A thermal assembly, fluid–structure system, electrochemical cell or process network can each be a composite model. None is a mandatory domain category. Compositions remain models in the existing library and reuse Model → Transform → Solve → Results and the same compiler, storage contracts and canonical equation worksheet. Model definitions remain derived from fundamentals; reuse preserves their operation history and does not introduce equipment-specific equation branches.

Physical connection contracts must define compatible quantities, species, units, signs and property/energy-reference compatibility. An ideal fluid connection enforces pressure compatibility and conservation with direction-aware composition and enthalpy transport; pressure losses belong to a declared relation or resolved region. Material, thermal, mechanical, electrical and signal interfaces have distinct semantics. Interface types are quantity contracts, not equipment types; supporting another physical family requires its laws and connector semantics, not an application-specific renderer. Connections are not arbitrary assignments of one solved model's outputs to another's inputs.

Assemble the selected hierarchy into one coupled mathematical problem, retaining instance paths and provenance. A common simulation clock coordinates coupled states. Sparse/block solution and optional partitioning belong to Solve; independent child time stepping is not the default physical coupling. Standalone testing supplies explicit boundary conditions outside the reusable definition, so insertion into a larger system cannot silently overconstrain its ports.

Physical edits invalidate the affected parent formulation, compilation and results. Renaming or moving diagram elements does not. Changing a reusable definition must not silently rewrite pinned instances; updates require a visible revision/dependency review. The current flat common model remains compatible until the versioned composition contract and migration are implemented. Do not silently flatten snapshots by string replacement: equation identities, per-instance state, component mappings, ports, package references and complete operation dependencies must be validated. The existing shared-region selector and material connections are a flat authoring capability, not hierarchical composition. The [workspace audit](docs/engine/model-workspaces.md#current-authoring-and-solve-audit) records the present gaps.

Primary references for the design comparison: [Modelica connector semantics](https://specification.modelica.org/maint/3.6/connectors-and-connections.html) and [IDAES unit-model/control-volume ports](https://idaes-pse.readthedocs.io/en/stable/reference_guides/core/unit_model_block.html). These support the architectural comparison, not a claim that this Engine already implements their capabilities.

### Continuation and implemented milestones

1. **Shared sheet contract and dependencies:** specify model revisions, transformation records, run identity, strict readers, compatible persistence and invalidation using the existing common model and results contracts. Inventory current adapters and remaining browser calculations before migrating them.
2. **First connected path — implemented within its declared scope:** the existing fundamental-equation derivation is under Model; Transform records an explicit scaling selection; the common Python Solve path executes supported multiplicative ODE formulations; Results reconstructs physical solutions and retains execution provenance. The [workspace specification](docs/engine/model-workspaces.md) and [common-model §7](docs/contracts/common-model.md#7-implemented-transform-execution-and-compilation-report) record supported cases, independent verification and remaining limits. General transformation composition is still pending.
3. **Spatial path:** introduce the dedicated Transform discretization engine, starting with the existing 1D matter cases rejected by the common compiler. Feed its semi-discrete system to Solve and publish spatial results through the common format. Verify conservation and mesh/time refinement; retire the corresponding browser calculation only after parity and independent checks.
4. **Structural and solver extensions:** publish method compatibility and initialization requirements before extending algebraic/DAE support. Continue pending thermodynamics, balances and constitutive coupling within their owning workspaces, following the physical roadmap and the common battery.

Unimplemented milestones specify the proposed execution order. Current limitations remain those recorded in the contracts and [multiphysics battery](docs/engine/multiphysics-battery.md). The physical priorities and restrictions in §8–§10 still apply unless explicitly superseded by the user.
