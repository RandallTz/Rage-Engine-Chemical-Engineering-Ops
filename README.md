# Rage Engine: an equation-oriented multiphysics engine for chemical engineering

Rage Engine is a **multiphysics simulation engine**. A model is never chosen from a menu of equipment or scenarios. Every model starts from the fundamental laws, which are local conservation of matter, the first law of energy, momentum and the fundamental thermodynamic relations. The user reduces those laws to the model they need with explicit, recorded assumptions. The engine then transforms, solves and presents that model, with thermodynamics always present.

Unit operations are **not** the centre of the project. A flash drum, a jacketed reactor, a stage cascade or a reactive distillation column is one combination of laws, assumptions and data. It goes through the same engines as any other model and has no code of its own. Reactive distillation, the problem this repository started from, is one operation among many.

> **Start here.** [ARCHITECTURE.md](ARCHITECTURE.md) explains the engine of engines, the common model, the always-present thermodynamics and the rules that are never broken. Agents (Claude, Codex, Gemini) start with [AGENTS.md](AGENTS.md). The documentation index is [docs/README.md](docs/README.md).

---

## How a model is built: Model → Transform → Solve → Results

The canonical entry point is `/models`. It offers four connected workspaces over one common model and one versioned sheet.

1. **Model.** Each family has its own panel: matter, energy, momentum and thermodynamics. Each panel starts at its fundamental equation. Assumptions are applied one at a time as typed operations on the equations, with before and after algebra, validity conditions and units, and with undo and redo. The model is never written directly. The thermodynamic state assumptions are declared in the thermodynamics panel: phases, phase change, the package per volume, and closures.
2. **Transform.** Any supported mathematical technique applied to the same model: nondimensionalization, scaling and steady state as a transform of the dynamic deduction. Spatial discretization is deferred.
3. **Solve.** Numerical data, degrees of freedom and methods. It handles explicit ODEs, index-one DAEs, nonlinear algebraic blocks, inverse specifications and block-sparse networks. The thermodynamic closure is evaluated at every step, so boiling, condensation or a second liquid phase appear without switching models.
4. **Results.** One results format (`rage.resultados`), one charting engine, verification certificates and provenance for every calculation.

Physical families and closures available today: multicomponent matter, energy and momentum balances on control volumes and networks; ideal, NRTL, original and Dortmund UNIFAC and IAPWS-95 water packages; Peng-Robinson mixtures; solid-liquid equilibrium; reaction kinetics; and certified ideal-gas chemical equilibrium. Equipment templates are recorded, parameterised deductions replayed per instance. Examples are a flash drum, a continuous jacketed reactor and one generic stage j reused n times. They are in review on the way to Demo 0.2.

Where things stand and what comes next:

- the [project board registries](docs/engine/project-board.json), validated with `node tools/roadmap_board/build_board.mjs --check`;
- the [multiphysics roadmap](docs/engine/multiphysics-roadmap.md);
- the capability Checklist (`/checklist`, generated snapshot in [docs/engine/engine-checklist.md](docs/engine/engine-checklist.md));
- the [engine map](docs/engine/engine-map.md).

---

## Repository layout

| Folder | Content |
|---|---|
| `core/` | The science, in pure SI: common model, mathematics and equation workbench, balance engine, compiler, solvers, thermodynamic layer, reactions, units service, results format and nondimensionalization |
| `backend/` | FastAPI over the core; one route per engine, no physics logic |
| `frontend/` | Next.js client: `/models` (Model, Transform, Solve, Results), `/checklist`, `/adimensionalizacion`. The interface never calculates |
| `docs/` | Contracts (`docs/contracts/`), engine documents (`docs/engine/`), examples and history ([index](docs/README.md)) |
| `tests/` | Python validation suites (`validar_*.py`) and pytest tests (`test_*.py`), each against an independent reference |
| `tools/` | Repository tooling: project board, CI checks (`tools/ci/`), graphify, inventory |
| `empaquetado/` | The offline Windows desktop build (SimuladorDR.exe) |
| `archive/` | Historical data kept for reference |

`pint` lives only at the boundary, never inside the numerical loops.

---

## Installation and use

```bash
pip install -r requirements.txt
python run_tests.py --tier fast    # quick physics and balance suites (a few minutes)
python run_tests.py --tier slow    # long suites, such as the UNIFAC validators (over an hour)
python run_tests.py --list         # which suite belongs to which tier
```

Run the client against a local API:

```bash
python -m uvicorn backend.main:app --port 8001 --reload   # in one terminal
cd frontend && npm run dev                                 # in another
```

The versions in `requirements.txt` are **pinned on purpose**. Several validations compare against exact values, and that only means something against fixed versions of `thermo`, `chemicals`, `numpy` and `scipy`. `tools/ci/check_requirements.py` fails if a third-party import is not pinned.

**Continuous integration.** `.github/workflows/validacion.yml` runs the fast tier, TypeScript, the browser-free frontend verifiers and the production build on every push. The slow tier, the Python-backed verifiers and the browser check run on pull requests to `main`, every night and on demand. The tiers are listed in `tools/ci/test_tiers.json`, and `tools/ci/check_tiers.py` keeps every suite in exactly one tier.

---

## How it is validated

> **A method that runs is not a method that works.** It is validated against something independent: a closed formula, a balance that must close, a literature value, another method, or a physical property that must hold.

- Every formula is checked numerically against a reference before it is accepted, never against the engine's own residuals.
- Nothing is published as proven unless it was proven. Uncertain results are marked, and a model the engine cannot handle is rejected with a located reason instead of being approximated silently.
- Examples of the standard:
  - benzene and toluene heated until fully vaporized go through the same equations from start to end, with bubble and dew points matching Raoult's law in closed form;
  - boiling water matches IAPWS;
  - first-order kinetics reproduces its analytical solution to 1e-12;
  - certified chemical-equilibrium extents match 50-digit mpmath roots to better than 1e-12;
  - interval bounds of reaction Jacobians are computed with outward rounding and contain every sampled value.

---

## What it does not do yet

- **Spatial models** are deferred by user decision: meshes, discretization, PDE solvers and geometry.
- **2D process diagram.** A flowsheet editor for the network topology is planned for Demo 0.2. Each block will be a template instance and each line a stream.
- **General equipment and networks.** Boundaries, real equipment, general pumps and hydraulic networks (roadmap F4 and F6), countercurrent columns (`demo-02-column`), and liquid-phase and thermally coupled chemical equilibrium (F5) are still pending.
- **Control and real-time stepping** are planned for Demo 0.3.

---

## History

The repository began as a reactive distillation simulator with a classic steady-state flowsheet and unit-operation modules. That Process Simulation side was deleted on 29 October 2026, and the earlier laboratory on 22 October 2026, both by user decision. Backups are kept in local `refs/backups/` refs, and capabilities are rebuilt from scratch through the engine rather than migrated. The folder name and some persisted identifiers keep the old name for compatibility.

---

## Documentation

Start with [docs/README.md](docs/README.md). Canonical documents are updated in place, in the same change as the work they describe ([documentation maintenance standard](docs/README.md#documentation-maintenance-standard)). New documentation, code and interface text are in English.
