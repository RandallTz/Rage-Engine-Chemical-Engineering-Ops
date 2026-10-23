# Vertical slice: the common model solved by its own engines

18 October 2026. Step 4 of [ARCHITECTURE.md](../../ARCHITECTURE.md) §10. It is the first complete path through the new architecture, without going through the earlier engine:

    common model (core/modelo)
      -> always-present relations (core/modelo/relaciones.py)
      -> thermodynamic layer (core/termodinamica)
      -> compiler (core/compilador)  -> solver (core/solvers)
      -> results in the common format (core/resultados)
      -> charting engine (frontend/componentes/graficas)

**HTTP routes**

- `POST /modelo/validar` with `{modelo}`: returns the relations and the layer's variables.
- `POST /modelo/resolver` with `{modelo}`: returns a result set in the common format.

## 1. Compiler (`core/compilador/compilador.py`)

It runs the model's relations **without branches by equipment, operation or substance**:

| Relation | Form executed |
|---|---|
| Matter, per volume and component | dn_vi/dt = Σ_s B_vs·ṅ_s·x_si |
| Energy, per volume | dE_v/dt = Σ_s B_vs·ṅ_s·h_s + Σ_q B_vq·Q_q (+ V_v·dP_v/dt) |
| State | E = U with a rigid boundary (UV closure, V a datum); E = H with prescribed pressure (PH closure, P(t) a datum) |
| Equilibrium | The thermodynamic layer's, at every evaluation: the phases are a result |
| Stream | Flow is a datum; composition and enthalpy of the **donor** according to the current sign of the flow. The donor is a volume (the mixture, or one phase by a physical criterion when there are two liquids) or the surroundings (a declared TP state) |
| Exchange | Q a datum (imposed) or G·(T_from − T_to) (conductance) |
| Verification | Auxiliary integrals of the matter and energy exchanged with the surroundings; global conservation residual |

- The data (a number or an expression in `t`) are converted to SI with the single units service. `core/expresiones_motor` parses the expressions, including the derivative dP/dt.
- Internal evaluations use the fast closure (`core/termodinamica/volumen.py`, seeded and without the full stability test).
- Each published sample is certified with `capa.cierre`: every candidate with its `tm`.

## 2. Solver (`core/solvers/integrador.py`)

Dormand-Prince 5(4) with per-component tolerances. The system offers it `rhs(t, y)` and `firma(t, y)`, an arbitrary discrete value; here it is the set of phases of each volume, but the solver does not know that.

- **If the signature changes within a step:** it bisects on the dense output, reintegrates to the instant of the change and restarts there, so as not to average across the kink in the properties.
- **If a stage fails:** it retries with a smaller step.
- **If the system raises `Detencion`** (depletion, an extracted phase that is absent…): the trajectory stops with its code.
- **If the system does not accept the new regime** (`admite(firma)` returns a reason, for example a single-phase policy when another phase appears): it stops at the instant of the change with code `politica_incumplida`.

## 3. Evidence

`python tests/validar_corte_vertical.py` (71 checks). The **same code** solves:

| System | Against | Result |
|---|---|---|
| Guide test: benzene + toluene (ideal), 100 W from 330 K | Raoult in closed form, H = H₀ + Q t and the existing engine live | Vapor at 365.275 K and liquid gone at 371.919 K (1e-4 K); state equal to the engine (1e-7); events at the same instant (1e-6 s) |
| Boiling pure water (IAPWS-95) | IF97 and the engine live | T_sat (5 mK) and plateau heat = n·h_fg (1e-3); state equal to the engine |
| Two volumes with a stream and a conductance | The engine's published response | Differences of order 1e-9 |
| Two rigid waters (UV) in thermal contact | Published response | 1e-9 |
| Water–butanol decanter extracting the less dense liquid phase | Published response | 1e-16 |
| Boiling NRTL ethanol–water | Published response | 1e-11, identical events |

In all six cases, in addition:

- global conservation of matter and energy below 1e-12;
- complementarity below 1e-8;
- every candidate phase published at every sample, with β = 0 before it appears.

A static check verifies that the compiler, the solver, the layer, the relations, the results and the units do not mention equipment, operations or substances.

`node verificar_corte_vertical.mjs` (14 checks): the HTTP route returns the same set, and the charting engine draws it, including the β of every candidate against time.

## 4. Second input: written equations (step 5.1)

`core/compilador/explicito.py`. A model whose volumes declare their state as assumed and that carries `matematico` is run as written: one equation du/dt = f(t, u, parameters) per field variable and one initial condition per variable. `resolver()` chooses the input; the structural one does not change.

- Values in SI from `datos["matematico.<id>"]`, checking that the unit matches the symbol's dimension.
- Methods: RK45 (`rk45`) or implicit BDF (`euler_implicito`, `bdf`).
- Domain: non-negative `restricciones` → event `agotamiento` at the exact instant, by bisection on the dense output (`core/solvers/integrador.py`, `dominio(t, y)`); a zero at t = 0 with a negative derivative stops at t = 0.
- Rejected with a reason: spatial coordinates and differential operators (discretization engine, 5.2), algebraic equations (DAE), order higher than one, declared functions without a definition, an initial condition that depends on variables, an incompatible unit, a pending datum.

## 5. Evidence for the second input

- `python tests/validar_compilador_explicito.py` (27 checks), with hand-written models, without volumes or components:
  - logistic with the rate in 1/min, against the analytical solution (1e-7);
  - oscillator as a first-order system (1e-8);
  - depletion stopped at exactly m0/k (1e-6 s) and, without a restriction, the straight line that continues;
  - stiff y' = −a(y − cos t), a = 1e4: BDF equal to the analytical solution with less than 1/20 of RK45's steps;
  - eight rejections with a reason, the HTTP route and the static check (no equipment or substance in the code).
- `node verificar_compilador_explicito.mjs` (76 checks): the six test matter sheets without a spatial field, brought into the common model by `modeloDesdeHojaMotor` and solved by `POST /modelo/resolver`, with RK45 and with the implicit method. Same state and final time as the TS solver; against the analytical solution and the TS solver, within 1e-16 to 1e-11 (RK45). With the implicit method, the compiler is 4e-9 from the analytical solution and the TS solver's implicit Euler 1.3e-5. The two 1D sheets are rejected with their reason.

## 6. Outside this version

The compiler answers `NoSoportado` with a reason in these cases:

- **Material sources (reaction) in the structural input:** they belong to the constitutive engine.
- **Volumetric flows.**
- **Volumes with an assumed state in the structural input:** it requires the equilibrium closure (the written-equations input and the balance engine handle them, [docs/engine/balance-engine.md](balance-engine.md)).
- **Initial U with prescribed pressure.**
- **Momentum, spatial fields (1D) and steady state:** phases F3 to F7 of the roadmap.
