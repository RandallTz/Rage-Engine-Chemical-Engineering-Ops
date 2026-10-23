# Engine map (`/motor`)

18 October 2026. What the engine does, what it has today, how far it goes, and where nondimensionalization can be coupled to it. It is a map of what exists: the state and priority of the next phases are in [docs/engine/multiphysics-roadmap.md](multiphysics-roadmap.md), and the detailed list of items in [docs/engine/engine-checklist.md](engine-checklist.md). The engine was not modified to write it. The project's target structure, of which this map is the inventory, is in [ARCHITECTURE.md](../../ARCHITECTURE.md).

Current workspace names and changed interface copy are in English. Older descriptions below retain historical labels for scientific features whose internal contracts remain compatible.

## 1. In one sentence

The engine starts from the conservation laws (matter, energy, momentum) and lets the user reduce them step by step, with explicit hypotheses, to a system that is solved in time. That system can be one volume, a network of volumes, a 1D field, or volumes with real thermodynamics. It has no pre-cooked scenarios: each case is a sheet with its derivation and its data.

```mermaid
flowchart LR
  B[Model library<br/>/models] --> E[Model<br/>fundamental derivation + assumptions]
  E --> T[Transform<br/>optional mathematical techniques]
  T --> R[Solve<br/>data, units, DOF, methods]
  R -->|matter, 1 volume or network,<br/>manual u(T) energy| TS[TS solver in the browser<br/>RK45 · implicit Euler · 1D FV]
  R -->|mixtures, phases,<br/>several volumes| PY[Python backend<br/>/motor/ensamblajes · RK45 with phase events]
  R -->|sheets that reach the common Engine| CE[Common Engine<br/>POST /modelo/resolver]
  E -->|point state, diagrams| TD[Python backend<br/>/motor/termodinamica]
  TS --> G[Results<br/>charts, table, details]
  PY --> G
  CE --> G
```

Since 18 October 2026 the Resolver sends every sheet that reaches the common Engine to `POST /modelo/resolver` (ARCHITECTURE.md §10, step 5.1); the browser solver remains for 1D fields and volumetric substitution.

## 2. The user's path

| Screen | Route | What it does |
|---|---|---|
| Library | `/models` | Create blank models, open, duplicate, archive and recoverably remove models; no template loader |
| Model | `/models/[id]/model` | Fundamental derivation and variables on the left, one assumptions panel on the right; the same worksheet for all four families and every document or example |
| Physical system | `/models/[id]/model/state` | The same worksheet, with geometry, components and thermodynamic configuration expanded inside its right panel |
| Transform | `/models/[id]/transform` | Optional nondimensionalization and supported spatial discretization |
| Solve | `/models/[id]/solve` | Numerical data, units, initial values, boundaries, structural DOF, compilation and methods |
| Results | `/models/[id]/results` | Configurable charts, tables, CSV and verification details |
| Legacy bookmarks | `/motor`, `/motor/hojas` and old document/foundation routes | Redirect into the canonical model library or corresponding workspace |

`frontend/app/models/ModelWorksheet.tsx` alone owns the Model grid/sidebar; family and storage adapters supply its content. Physical configuration and coupled topology controls use that panel. `ModelLibrary.tsx` is the sole library. The old `BibliotecaHojas`, `BarraHojaMotor`, `EditorBalanceModular` and `DerivacionVolumenRed` components, plus the network editor's separate equation mode, have been removed. Examples never select another frontend. The [workspace specification](model-workspaces.md#model-derivation-standard-and-audit) records the 1,382-check regression enforcing this across all 42 templates, blank/legacy documents, four families and both configuration states.

## 3. Three calculation paths

| | A. The project's own solver in the browser | B. Thermodynamic assembly (backend) | C. State and diagrams (backend) |
|---|---|---|---|
| Code | `app/motor/modeloNumerico.ts`, `integracionMotor.ts`, `ensamblajeMateria.ts`, `modeloEnergia.ts` | `backend/motor_ensamblaje.py` (v1), `motor_ensamblaje_v2.py` (multiphase network, revision 2), `core/ensamblaje_dinamico.py`, `core/ensamblaje_red.py` | `backend/motor_termodinamica.py`, `motor_diagramas.py`, `motor_mezclas.py`, `motor_hielo.py`, `motor_catalogo.py` |
| Routes | none (local) | `GET /motor/ensamblajes/capacidades`, `POST …/validar`, `POST …/resolver` | `GET /motor/termodinamica/capacidades`, `POST …/evaluar`, `…/diagramas/{capacidades,trazar}`, `GET …/diagrama`, `GET /motor/catalogo` |
| Equations | Matter: total dmᵢ/dt (ports, rest, G, C), volumetric dV/dt, local transient dρᵢ/dt, Cartesian 1D field (convection, Laplacian/Fick/flux diffusion, sources). Network of mass volumes with shared streams. Energy: 1 volume, 1 species, U = m·u(T) manual | Matter and energy per volume and phase with the package's states; convective streams (per component or the donor's total, internal, with reversal); rigid or prescribed-pressure boundaries; thermal contact (imposed or conductance); homogeneous or per-phase extraction; second law | Equilibrium state TP, PH, UP, UV (and TV in dynamics); flashes; potentials; T–xy, P–xy diagrams and the P–T diagram of water with ice |
| Method | RK45 Dormand–Prince or adaptive implicit Euler; 1D by conservative finite volumes, **first-order upwind convection**, centred diffusion, ≤ 160 cells, ≤ 201 samples, ≤ 150 000 steps | RK45 with phase events, ≤ 1001 samples | Equilibrium solvers with stability certificates |
| Size | 1–8 species per domain; network of mass volumes | ≤ 3 volumes, ≤ 7 components per volume, ≤ 3 phases | depending on the package (below) |
| Result | `ResultadoMotor` in IndexedDB `rage-motor-resultados`, key [sheet, signature] | adapted to the same `ResultadoMotor` | point response or plot |

Sheets live in localStorage `rage.motor.hojas.v1`. Each result's signature includes the formulation, the data and the solver version; any edit invalidates it.

## 4. What it has today

### Matter

Done: local → integral → total derivation with assumptions; component catalog by ID; streams per component or total + composition; accumulation, filling and draining (depletion event); declared generation and consumption; several coupled volumes with a global balance; Cartesian 1D convection and diffusion; structural count; units and results.

Missing: selective transfer coupled to thermodynamics; reaction kinetics with real thermodynamics; general real-fluid flows from momentum; other geometries and dimensions; general inverse solution.

### Energy

Done: local → integral → total first law with Gauss and Reynolds; enthalpy transport; heat and boundary work; rigid vessel with calculated pressure; prescribed pressure; thermal contact between volumes; phase change along the trajectory; per-phase extraction and absent-phase events; conservation and second law with a known boundary T.

Missing: reaction energy; solids in dynamics; spatial energy transport; transfer out of equilibrium; mechanical work from momentum; discontinuous pressures.

### Thermodynamics (published packages)

| Package | Species | Phases | T domain [K] | In dynamics |
|---|---|---|---|---|
| `agua-iapws95` | water | L, V, fluid | 273.16–1073.15 (without the critical band) | yes |
| `agua-iapws95-hielo-ih` | water | S, L, V | 200–300 | no (static only) |
| `mezcla-ideal` | 8 | L, V | 159–583, P ≤ 5 bar | yes (cross-checked up to 7) |
| `nrtl-chemsep` | 8 | L, V | 159–583 | yes (cross-checked up to 4) |
| `nrtl-lle-agua-butanol` | 2 | L, L, V | 293–373 | yes |
| `unifac-original-public`, `unifac-dortmund-public` | 8 | L, V | 159–583 | yes |
| `unifac-original-lle-public` | 7 (no methanol) | L, L, V | 283–313 | yes (2 species cross-checked) |

Species: water, ethanol, benzene, toluene, 1-butanol, ethyl acetate, methanol and acetone. Streams only between packages with the same energy reference (not IAPWS water ↔ mixture). Accepted substitutions: v_L, ideal Cp and Psat per species.

### Momentum

The Model workspace now records Cauchy → Newtonian stress → Navier–Stokes → Gauss/Reynolds → two-port/hydraulic or angular-momentum reductions. It includes retained fluid/rotor dynamics, explicitly constrained passage storage, ideal radial-blade torque/head/pressure derivation, shared stream bindings and family-specific work/continuity/state relations. The same worksheet and assumptions panel serve every model. The common compiler now executes a strictly admitted isothermal constant-density hydraulic subset: retained path inertia, quasi-steady laminar circular resistance, prescribed-flow pressure recovery or dynamic flow/storage coupling. Existing Model assumptions, RK45/BDF, shared units and pressure/mass/flow charts are reused. General constrained networks, energy/rotor coupling and real-machine closures remain pending; other active momentum formulations remain blocked. See [reduced hydraulic scope](../contracts/common-model.md#12-reduced-hydraulic-execution) and `npm run test:hydraulics`. Contract, evidence and limits: [common model §11](../contracts/common-model.md#11-momentum-deduction-cauchy-to-reduced-machines).

## 5. State verified today

Suites run on 18 October 2026, without changes to the engine:

| Suite | Result |
|---|---|
| `npm run test:motor-fundamental` (31 frontend scripts: matter, solver, energy, coupling, multicomponent, thermodynamics, network, diagrams, UNIFAC, catalog) | all pass |
| `tests/validar_motor_termodinamica.py` | 585 passed |
| `tests/validar_motor_termodinamica_h3.py` | 3729 passed |
| `tests/validar_motor_ensamblaje.py` | 245 passed |
| `tests/validar_motor_ensamblaje_v2.py` | 114 passed |
| `tests/validar_motor_consolidacion_v2.py` | 128 passed |
| `tests/validar_motor_n_componentes.py` | 82 passed |
| `tests/validar_motor_unifac.py` | 136 passed |
| `tests/validar_motor_diagramas_equilibrio.py` | 78 passed |
| `tests/validar_motor_catalogo.py` | 125 of 126: **1 failure of the test itself, not of the engine** (below) |

**The catalog failure.** The check "point capabilities = those of F1 + acetone" removes acetone from the current capabilities and compares them with `docs/ejemplos/motor-unifac/motor-termodinamica-capacidades.json`, which should be the F1 snapshot. That snapshot was regenerated on 16 October (08:03) already including acetone, after the test was written (07:52). The capabilities did not change; the reference stopped being F1's. It is fixed by restoring the F1 snapshot or by comparing without removing acetone. It was not touched: it belongs to the engine.

## 6. Scope and known limits

- **It does not solve**: steady state, inverse problems, general DAEs, the unreduced integral form, 2D/3D, curvilinear coordinates, moving meshes, unrestricted momentum/rotor coupling, chemical reaction with thermodynamics, energy in 1D.
- **1D numerics**: first-order upwind. In the pure advection of test sheet 07, with 80 cells, it departs 8e-3 from the exact solution, against 9e-5 for the nondimensionalization core's simulation with the same data. With 20, 40 and 80 cells the mean errors are 0.042, 0.022 and 0.011 (order 1).
- **Free expressions**: a safe AST without internal dimensional certification; `step` and pulses need enough time resolution.
- **Open incidents (F9)**: R1 now has the located-event publication/work correction described below; R2 retains broader candidate-domain work.
- **Tests**: the overwritten-F1 reference assertion was corrected on 20 October 2026; all 126 catalog checks pass. See the consolidation record below.
- **Late appearance of a phase (v2 assembly): fixed on 18 October 2026.**
  - **Symptom.** In the example `motor-ensamblaje-v2-resolver-unifac-red-5-especie-entrante`, the engine published A's second liquid phase at 141.41 s. The independent stability limit (LL tangent plane with `thermo`) is between 113.5860 and 113.5861 s.
  - **Cause.**
    - The watch did detect the change, and the bisection located it at 113.5860 s.
    - But the state reintegrated up to that instant was still single-phase, because it differs from the interpolant by ~rtol right at the kink.
    - The later search by doubling steps ended with a failed sub-integration, and the whole step (111 → 142 s) was accepted **without an event**.
  - **Fix** (`core/ensamblaje_red.py`, `integrar`): if that search does not find the change, the event is taken at the bisection instant with the interpolant's state, which the bisection already showed changes the set of phases. The step is accepted without an event only if that state does not change either.
  - **Result.** Appearance at 113.58592 s (against the common compiler, 113.58602 s); trajectory equal to the common compiler's within 3e-7, previously 6e-5. The example was regenerated (only that file changed; the diagrams changed only their `segundos` field and were restored).
  - **Suites.** `validar_motor_ensamblaje_v2` 114, `validar_motor_consolidacion_v2` 128, `validar_motor_n_componentes` 82, `validar_motor_unifac` 136, `verificar_contrato_unifac`, `npm run test:motor-fundamental`, `validar_corte_vertical` 71 and `validar_capa_unifac` 82: all pass.
  - **Scope.** It does not close the checklist's general item "Detection of transitions the step sampling misses": a phase that appears and disappears between two watched points is still not seen. The v1 integrator (`core/ensamblaje_dinamico.py`) did not have this path.
- **Interface**: a green button without text in the action row of `/motor/hojas`, seen during the integration with nondimensionalization.

## 7. Where nondimensionalization couples in

Nondimensionalization is an extension of the engine: it reads its sheets and does not modify them. Each calculation path offers a different hook.

| # | Hook | Path | What it brings | Status | Touches the engine? |
|---|---|---|---|---|---|
| 1 | Single-domain matter sheet → document (`desdeMotor.ts`) | A | Groups, regime, independent simulation and comparison with the engine's result | **Done (M1)**, 117 checks | no |
| 2 | Network of mass volumes (`ensamblajeMateria.ts`) → ODE system per volume and species | A | Scales per volume, residence numbers and network stiffness | Proposed | no |
| 3 | Energy of one volume with manual u(T) → [m, U] or [m, T] | A | Thermal groups (Stanton, capacity ratio, thermal Damköhler) | Proposed | no |
| 4 | Mesh and stiffness diagnosis with the engine's limits (≤ 160 cells, upwind, 0.4 Δx/v, 0.2 Δx²/D) | A | Cell Péclet, cells needed, warning before solving | Proposed (M2) | no |
| 5 | v2 thermodynamic network → balances with properties as functions with a declared scale, for example h(T) = c_p,ref·T_ref·ĥ(T̂) | B | Groups for a network with real phases and states, without algebra on the package | Proposed (M3) | no |
| 6 | Show groups and mesh warnings inside the engine's Resolver; a higher-order convective scheme | A/B | The engine uses what the extension calculates | Needs your approval (M4) | yes |

Recommended order: 2 → 4 → 3 → 5. Points 2 and 4 reuse almost all of M1. Point 5 needs to read the assembly's v2 contract and decide which properties are scaled. Point 6 is decided at the end, with you.

## 8. Sources

[docs/engine/multiphysics-roadmap.md](multiphysics-roadmap.md) · [docs/engine/engine-checklist.md](engine-checklist.md) · [docs/engine/sheet-solver.md](sheet-solver.md) · [docs/engine/matter-coupling.md](matter-coupling.md) · [docs/engine/energy-foundation.md](energy-foundation.md) · [docs/engine/balances-ui.md](balances-ui.md) · [docs/history/frontend/integration-multiphase-v2.md](../history/frontend/integration-multiphase-v2.md) · [docs/engine/dynamic-assembly.md](dynamic-assembly.md) · live capabilities of `/motor/termodinamica/capacidades` and `/motor/ensamblajes/capacidades?revision=2` · [docs/history/frontend/plan-connection-nondimensionalization-engine.md](../history/frontend/plan-connection-nondimensionalization-engine.md).


## Recorded Model derivations and capability inventory (19 October 2026)

The four workspaces retain one physical model. Material and first-law reductions and thermodynamic constitutive choices have independent versioned operation journals, strict Python replay, common/native validation and compilation/Results provenance. Network editors can rebuild, undo and restore; new volumes start from fundamental laws. New templates use the same operations: all 42 pass the structural provenance audit. Saved legacy documents are never assigned fabricated histories. See [the workspace specification](model-workspaces.md#model-derivation-standard-and-audit) and [common model §9](../contracts/common-model.md#9-first-law-and-thermodynamic-operation-journals).

`/checklist` is the English capability inventory, with Available/Pending/Deferred states and workspace ownership. Its registry, live download and [canonical snapshot](engine-checklist.md) stay synchronized. First-law deduction is complete within the supported uniform transient scope. Spatial energy, reaction energy, general DAEs and extended thermodynamic physics remain pending in the existing roadmap. UNIFAC retains priority; NRTL is not extended.


## Property-driven vessel discovery (19 October 2026)

The shared template registry now contains 42 models. Its rigid water–1-butanol example uses recorded fundamental-law deductions, the original UNIFAC package and an unrestricted phase policy. It initializes TV, integrates closed inventories/energy and recovers UV states through the common and native paths. The computed heating trajectory passes from three phases to two to one without changing the model's equations or selecting a target equilibrium type. See the maintained [workspace specification](model-workspaces.md#property-driven-phase-discovery-example-19-october-2026) for inputs, independent references and limits. The historical generated battery is not retroactively claimed as a 42-case run.


## Nonspatial consolidation and clean library (20 October 2026)

The product library has no predefined-example loader and the live browser's 59 existing documents have been recoverably removed, including manual models. Regression inputs live in `frontend/testing/modelFixtures.ts`; they must never be loaded by the product library. New examples are authored on request through the same fundamental operations and canonical worksheet. New thermodynamic relations do not create another UI.

Current priority is nonspatial thermodynamics. The native event/publication boundary now retains located flash context and exact event times, with unchanged physical certification tolerances and independent work quadrature. Python development exposes the existing excess-potential/caloric identities. The historical catalog test-snapshot issue in section 5 has been corrected through a symmetric base comparison plus explicit current acetone admission; package data are unchanged. The existing roadmap and Checklist retain pending physics and finite-search limits. Spatial extensions are deferred.
