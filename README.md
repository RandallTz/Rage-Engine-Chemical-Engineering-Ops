# Reactive distillation simulator

An **equation-oriented** simulator of chemical processes, now growing into a general **multiphysics engine**: every model starts from the fundamental conservation laws, is reduced with recorded assumptions to the model that is needed, and is solved with thermodynamics always present.

> **Project structure and working rules:** [ARCHITECTURE.md](ARCHITECTURE.md) (engine of engines, common model, always-present thermodynamics). Agents start with [AGENTS.md](AGENTS.md). Documentation index: [docs/README.md](docs/README.md).

The user interface is in Spanish; documents, file names and new code are in English. The repository is being tidied up and moved to English in phases ([docs/repository-cleanup/README.md](docs/repository-cleanup/README.md)).

---

## The Engine (`/motor`)

The Engine is where current work happens. A **sheet** is a model built step by step:

1. **Formulate.** Four panels — Matter, Energy, Momentum and Thermodynamics. Each starts at its fundamental equation (local conservation, the first law, momentum, the fundamental thermodynamic relations), and each assumption is applied one at a time, with undo and redo. The model is never written directly.
2. **State.** Components from a catalog, a thermodynamic package per volume (ideal, NRTL, UNIFAC, IAPWS-95 water), candidate phases and equilibrium samples.
3. **Solve.** The server generates the balance equations from the sheet's assumptions (`core/balances`), compiles them with the common compiler (`core/compilador`) and integrates them (`core/solvers`). The thermodynamic closure is evaluated at every step, so boiling, condensation or a second liquid phase appear without switching models.
4. **Results.** One results format (`rage.resultados`) and one charting engine for every calculation.

Where things stand and what comes next: [docs/engine/engine-map.md](docs/engine/engine-map.md), [docs/engine/multiphysics-roadmap.md](docs/engine/multiphysics-roadmap.md) and the generated [multiphysics battery](docs/engine/multiphysics-battery.md).

---

## Repository layout

| Folder | Content |
|---|---|
| `core/` | The science, in pure SI (`float`/NumPy): the common model, balance engine, compiler, solvers, thermodynamic layer, units service, results format, nondimensionalization, and the classic unit operations |
| `thermodynamics/` | Providers built on `thermo`: VLE (bubble and dew points), unified enthalpy $h(T,x,\text{phase})$, reaction equilibrium and kinetics |
| `backend/` | FastAPI over the core; one route per engine, no physics logic |
| `frontend/` | Next.js: the Engine, nondimensionalization, flowsheet, columns, lab |
| `docs/` | Contracts, engine documents, method guides, examples and history ([index](docs/README.md)) |
| `tests/` | Python validation suites, each against an independent reference |
| `tools/` | Repository tooling (inventory, link checker) |
| `api/`, `archive/` | The first simulator and the Yaws data ETL, kept for reference |
| `empaquetado/` | The offline desktop build (SimuladorDR.exe) |

`pint` lives only at the boundary, never inside the numerical loops.

---

## Installation and use

```bash
pip install -r requirements.txt
python run_tests.py          # every Python suite of the core and the API
```

The interface suites check what no Python suite can see — that the right number reaches the screen — and need both servers running and a browser:

```bash
python -m uvicorn backend.main:app --port 8001 --reload   # in one terminal
cd frontend && npm run dev                                 # in another
cd frontend && node verificar_todo.mjs                     # the interface suites
cd frontend && npm run test:motor-fundamental              # the Engine's suites
```

The runner looks at each suite's **exit code**, not its text output: every suite ends with a different message, so searching for "TODO OK" once passed a suite that had just crashed with another sentence.

The versions in `requirements.txt` are **pinned on purpose**: the validations compare against exact values (`365.515693 K, bit-for-bit identical`), and that only means something against a fixed version of `thermo`.

A minimal example of the classic core:

```python
from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from core.flash import EvaluadorFlash

prov  = ProveedorTermodinamico(["benzene", "toluene"])
flash = EvaluadorFlash(CalculadoraELV(prov))

r = flash.isotermico(T=368.0, P=101325.0, z=[0.5, 0.5])
print(r["beta"], r["x"], r["y"])
```

See also `ejemplo_columna_destilacion.py`, `ejemplo_orquestador.py` and the templates in `backend/ejemplos_flowsheet.py`.

---

## The classic simulator: flowsheets and columns

It is not a script that calculates in a fixed direction: each unit contributes equations to a shared pool and the orchestrator decides what is solved for according to the available data, as a commercial simulator does.

```
fresh ──► mixer ──► exchanger ──► flash ──┬──► vapor
            ▲                             │
            │                             └──► liquid ──► splitter ──┬──► purge
            └──────────────── recycle ──────────────────────────────┘
```

**Separation** — binary column (McCabe-Thiele / Ponchon-Savarit), multicomponent column (FUG), L-V flash, component separator, absorber/stripper (Kremser), liquid-liquid decanter.

**Reaction** — CSTR with kinetics and an energy balance, chemical-equilibrium reactor, plug-flow reactor (PFR).

**Thermal** — heat exchanger, two-stream exchanger (heat integration), isenthalpic expansion valve.

**Transport and mixing** — pump, compressor/turbine, mixer, splitter.

The flowsheet detects **recycles** automatically, tears them and converges them with Wegstein.

### Design, not only calculate

**Design specifications.** Instead of giving the reflux and getting the purity, you ask for the purity and the simulator finds the reflux:

```python
from core.especificaciones import Especificacion

resultado = diagrama.resolver_con_especificaciones(
    [Especificacion(objetivo="producto.x2", valor=0.9055,
                    manipulada="r1.T_salida", minimo=330.0, maximo=370.0)],
    **datos,   # without r1.T_salida: the specification turns it into an unknown
)
```

The target and the manipulated variable **can be in different units, with a recycle in between**: each evaluation solves the whole flowsheet, recycles converged. The range is not decoration — it bounds the search to the region where the flowsheet can be solved. The degrees-of-freedom count takes it into account: each specification adds **one equation**, so a problem that lacked one datum (DOF = 1) is closed (DOF = 0).

**Sensitivity sweeps.** Move one variable and see how the rest responds:

```python
filas = diagrama.barrido("col1.R", [1.6, 2.0, 3.0, 5.0, 10.0],
                         seguir=["col1.N", "col1.Q_c"], **datos)
```

A point that fails **does not bring down the sweep**: the reason is recorded and it continues. The classic trade-off appears by itself: from $R=1.6$ to $R=10$, $N$ falls from 19.5 to 7.5 and $Q_c$ rises from 3.1 to 13.2 MW.

Both are also in the API (`POST /diagrama/resolver` accepts `especificaciones`; `POST /diagrama/barrido`) and in the interface, in the flowsheet's **"Diseño"** tab. Details in [docs/13-especificaciones.md](docs/13-especificaciones.md).

### Where each number comes from

Each `/diagrama/resolver` response can say what it was calculated with, what is wrong with it and how far it can be trusted:

- **`calculo`** — engine version and git commit (with a `-sucio` suffix if the tree had changes), versions of `thermo`/`chemicals`/`fluids` — the *real* version of the thermodynamic provider — and a **deterministic SHA-256 fingerprint of the physical inputs**.
- **`diagnosticos`** — incidents with a **stable code**, category (data / physics / numerical / model) and severity. The category comes from where the problem was generated, **never from searching words in the message**.
- **`convergencia`** — per block, the method, the tolerance and the residual **when the algorithm really evaluates one**. A McCabe-Thiele construction has no residual and says why; inventing one would be a lie that looks like precision.

Details in [docs/14-trazabilidad.md](docs/14-trazabilidad.md).

---

## How it is validated

One rule, applied across the project:

> **A method that runs is not a method that works.** It is validated against something independent: a closed formula, a balance that must close, a literature value, or a physical property that must hold.

"Returns an array of the right shape" and "the number looks reasonable" do not count. These do, and they are real:

- The energy balance of a plant with a recycle closes to $4\times10^{-12}$ relative.
- The ethanol/water azeotrope appears at $x = 0.894$ (literature: 0.894).
- The solubility of MIBK in water at 25 °C comes out at 1.41 wt % against 1.55 % in Perry's table 15-8, and the distribution of acetic acid falls 17 % to 26 % short — **the error is measured and written down**, not hidden behind a loose tolerance.
- The liquid leaving a flash is at its bubble point to $10^{-9}$ K, checked against an independent routine.
- In the Engine, benzene and toluene heated until fully vaporized go through the same equations from start to end; bubble and dew points match Raoult in closed form to $10^{-4}$ K, and boiling water matches IAPWS-IF97 to 5 mK.
- A first-order kinetics reproduces its **analytical solution** to $10^{-12}$, and a transient batch ends at the calculated equilibrium to $5.6\times10^{-17}$ — integrating an ODE and solving $\ln Q = \ln K$ are two paths with nothing in common.

The full detail, and **the limits**, in [docs/12-validacion.md](docs/12-validacion.md).

---

## What it does NOT do

This is as important as the above, and it is documented unit by unit:

- **No rigorous MESH column yet** — only the scaffolding.
- The classic flowsheet is steady state only; dynamics live in the Engine.
- **Liquid-liquid equilibrium is for exploring, not for sizing.** Against Perry's table 15-8, UNIFAC-LLE underestimates the distribution ratio by 17 % to 26 %, systematically. It gets the trend right, which is what decides whether a solvent is useful; the magnitude is not enough for sizing.
- Pressure drop **per unit**, not an internal profile.
- **Partial sizing:** tray column diameter by the Fair correlation and two-stream exchanger area by U·A·LMTD, validated against Perry's Example 9. No real trays from theoretical ones, no packed columns, and **no costs** — a diameter and an area are not a price.

---

## Sharing a simulation

Each flowsheet simulation fits inside a link. "Copiar enlace" in the simulations list generates a URL that carries the whole flowsheet — components, units, equipment and data — and opens in any browser without installing or registering anything. It goes in the URL **fragment** (`#`), so it is not sent to the server; **results do not travel, only the setup**, and whoever opens the link recalculates them with the same validated core.

---

## Documentation

Start with [docs/README.md](docs/README.md). The mathematics is written in Markdown with LaTeX, versioned together with the code and updated in the same commit as the change that prompts it — the only way it does not go stale.
