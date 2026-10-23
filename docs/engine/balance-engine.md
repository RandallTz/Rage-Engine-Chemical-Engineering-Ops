# Balance engine

18 October 2026. It is the "Balances + Assumptions" engine of [ARCHITECTURE.md](../../ARCHITECTURE.md) §5. It takes the fundamental equations and each volume's assumptions and produces the explicit equations the common compiler solves. The equations are generated **on the server**, from the assumptions the sheet declares; the client only says which datum is which.

- **Code:** `core/balances/` (`generar(modelo)`).
- **Adapter for Engine sheets:** `frontend/motores/modelo/desdeHojaBalances.ts` (`modeloBalancesDesdeHoja`, `cabeEnBalances`).
- **Solving:** `POST /modelo/resolver`. If the model has volumes with an assumed state and carries no `matematico`, `core/compilador/explicito.py` calls the balance engine and solves what it generates.
- **Tests:**
  - `python tests/validar_motor_balances.py` (30, against analytical solutions, with hand-written models);
  - `node frontend/verificar_bateria_multifisica.mjs` (every Engine sheet against the current calculation).

## 1. Path

    sheet (assumptions, topology, data)
      -> common model without equations (desdeHojaBalances.ts)
      -> balance engine: explicit equations + restrictions (core/balances)
      -> written-equations compiler + solvers (core/compilador/explicito.py, core/solvers)
      -> results in the common format

## 2. Laws

General: there are no branches by equipment, operation or substance. Each term appears or not according to the volume's assumptions.

### Matter (total form, mass of each component as state)

    dm_iv/dt = Σ_s B_vs ṁ_is − Φ_iv,rest + G_iv − C_iv

| Term | Appears if | Datum |
|---|---|---|
| ṁ_is through stream s (B = +1 if it enters v, −1 if it leaves) | the volume does not remove transport (a fixed boundary with no convection and no diffusion removes it) | `corrientes[s].materia`: per component (mass, or molar · M_i) or total with fractions |
| Φ_rest | the remaining boundary is not impermeable (`restoImpermeable: false`) | `terminos["resto.<i>"]` |
| G, C | the sources have not been removed (`sinReaccion`, `sinGeneracion`, `sinConsumo`) | `terminos["generacion.<i>"]`, `terminos["consumo.<i>"]`; per volume (rate · V) if they were declared uniform |

### Energy with u(T) declared as an assumption (`u_lineal`)

    U_v = m_v u(T_v),   u(T) = u_ref + c (T − T_ref)
    dU_v/dt = Σ_s [max(q,0)·h(upstream) + min(q,0)·h(v)] + Q̇ + Ẇ_τ + Ẇ_b + R − p·dV_v/dt

- q is the stream's total mass flow toward v. The donor is chosen by the **sign** with max/min: no direction is assumed.
- h = u(T) + p/ρ if the enthalpy carries the flow energy (`entalpia: true`). Otherwise h = u(T) and the flow work q·p/ρ is added separately.
- An external stream uses the temperature of its `estadoExterior`. Without it, the stream can only leave: if it reverses, the calculation stops.
- p·dV/dt only with a moving boundary (`fija: false`), with dV/dt = (dm/dt)/ρ.
- **Requirements of a linear u(T)**, which are checked and rejected with their reason:
  - total form;
  - accumulation;
  - negligible kinetic energy;
  - uniform thermal state;
  - single-phase regime without phase change;
  - stresses split into pressure and viscous;
  - with streams or a moving boundary, imposed pressure and density.

## 3. Restrictions (watched domain)

The calculation stops at the instant one would be violated, located by bisection (`core/solvers/integrador.py`). It is never clipped.

| Restriction | Why |
|---|---|
| m_iv ≥ 0 | a mass cannot be negative (depletion) |
| G, C ≥ 0 | they are gross rates |
| T_min ≤ T_v ≤ T_max | validity domain of the u(T) assumption |
| q_i·q_j ≥ 0 in a convective stream | a convective stream carries all its components in the same direction (a selective one does not) |
| −q ≥ 0 in an external stream without a declared state | matter of unknown state cannot enter |

## 3 bis. What is published besides the states

- **Observables** (`observable.<id>`), per volume with energy:
  - `volumen.v.T`, `volumen.v.dUdt` and `volumen.v.V`;
  - each active energy term: `volumen.v.calor`, `trabajo_viscoso`, `fuerzas`, `fuente` and `trabajo_frontera`;
  - per stream: `corriente.s.mdot`, `corriente.s.h` (donor enthalpy) and `corriente.s.E` (energy toward the volume).
- **Budget closures** (`verificaciones`), with auxiliary integrals (`campo.aux_*`):
  - `estado.<u>`: each state against the integral of its own balance;
  - `global.materia.<i>` and `global.energia`: the whole system against what crosses its boundary (external streams, sources, heat and work). Internal transfers must cancel, which checks that the network is assembled correctly.

The Engine's Resolver (`frontend/app/motor/resolverEngine.ts`) translates all of this into the `ResultadoMotor` the views read, without recalculating physics.

## 4. Variables in the expressions

The data are numbers or expressions (grammar of `core/expresiones_motor.py`). The variables are defined once, as expressions of the states:

| Scope | Variables |
|---|---|
| every datum | `t`; per volume v and component with symbol S: `m_S_v`, `m_total_v`; with volume as a datum, `V_v`, `rho_S_v`, `rho_total_v`; with energy, `T_v`, `U_v` |
| a volume's own data (terms, and streams with only one volume at one end) | `m` (of the term's component; the total if there is one), `m_total`, `m_S`, and with volume `V`, `rho`, `rho_total`, `rho_S`; with energy, `T`, `U` and, with density, `rho` and `V = m/rho` |

Each datum is converted to SI with the single units service. A unit whose dimension is not that of the term's quantity is rejected.

## 5. Contract (optional fields of common model v0)

See [docs/contracts/common-model.md](../contracts/common-model.md) §1. Per volume:

- `terminos` (key → datum);
- `volumenDatoId`;
- `termodinamica.parametros` of u(T): `cId`, `uRefId`, `TRefId`, `TMinId`, `TMaxId` and `rhoId`;
- `inicial.energia`, now optional without an energy balance.

Per stream, the `total_y_composicion` mode. In `restricciones`, the form `{expresion, tipo, descripcion}`.

## 6. Evidence (18 October 2026)

- **`tests/validar_motor_balances.py`, 27 checks against analytical solutions:**
  - series with constant flows;
  - Bateman cascade;
  - closed recirculation, with conservation and the damped oscillating solution;
  - conversion A → B;
  - per-volume source and molar flow;
  - total flow by fractions;
  - depletion at t = 50 s;
  - a convective stream that reverses, stopped at t = 5 s;
  - energy: a heated closed volume, a hot inlet with constant amount, filling with a moving boundary (T_in − T = (T_in − T0)(m0/m)^(in/(in−out))), and the stop at T_max at t = m c (T_max − T0)/Q;
  - ten rejections with a reason, and the static check.
- **Multiphysics battery:** the 10 volume networks (coupling and multicomponent, up to 8 components with traces), the 6 energy sheets with u(T) and the 5 single-domain matter sheets in total form. All equal to the Engine's current calculation, within 1e-16 to 1e-9 relative. See [docs/engine/multiphysics-battery.md](multiphysics-battery.md).

## 7. Outside this version

It answers `NoSoportado` with a reason in these cases:

- **Volumetric substitution or mean density** (`cantidadVolumen`) and **spatial fields:** they still go through the written-equations adapter and, later, through the discretization engine.
- **General state rules; unrestricted momentum balance; general constrained/steady-state execution.** The scoped reduced hydraulic compiler described in §10 is available.
- **Volumetric flows.**
- **The `step` function**, which has no translation into the common tree.
- **Energy with an equilibrium state:** the compiler's structural input handles it, with a thermodynamic package.

## 8. Shared material deduction and compilation

**Primary workspace:** Model. Inputs are fundamental material conservation, explicit operations, component identities, topology and closures. Outputs are a recorded material formulation and Python-generated mathematical development. Transform preserves the journal when selecting a formulation; Solve validates it before generating/compiling equations; Results retains execution provenance. Changes to assumptions/topology invalidate dependent calculations. Network journal changes also invalidate saved run provenance; presentation-only names remain excluded.

The implementation is `core/balances/material_derivation.py`; the versioned payload, authoring endpoint and strict readers are specified in [common model §8](../contracts/common-model.md#8-material-deduction-journal-implemented-subset). The material journal is not another equation source: the existing generator consumes the replay-verified flags. Component/stream topology is kept separate and supplies the actual incidence signs. Internal streams still cancel between their two endpoints; total balances need no artificial spatial grid.

Ordinary models serialize their active recorded material history. Newly constructed network templates explicitly apply the shared deduction operations before they receive a final material formulation; stored legacy network documents are never silently assigned this new history. The network Matter panel can explicitly rebuild from the unrestricted local law, apply deductions, undo and restore the previous material formulation. New volumes start from the fundamental material law; adoption of an ordinary model preserves its actual operations; deletion removes journal ownership; explicit mechanical-boundary edits record their material consequence. Full development includes Gauss, Reynolds, source/inventory definitions, assumptions and resulting conservation equations.

The thermodynamic compiler and revision-2 validation reject unsupported material forms rather than discarding their meaning: algebraic accumulation, unsupported spatial/volumetric forms, a boundary remainder without a law, incompatible mechanical boundaries or streams whose transport was removed. Selective transfer still requires its own coupled energy law. These guards add no new physical closure or solver.

**Remaining work:** volumetric-flow and moving-volume closures; general steady-state/DAE support; conservative Python spatial integration; reaction stoichiometry and constitutive kinetics. Prescribed generation/consumption already exists and is not equivalent to the full reaction layer. New models/examples must continue to use the shared tools.

## 9. First-law and state-closure evidence

The independent energy and thermodynamic journals are implemented through the same Model → Transform → Solve → Results boundary. See [common model §9](../contracts/common-model.md#9-first-law-and-thermodynamic-operation-journals) for their canonical contracts and [workspace implementation](model-workspaces.md#model-derivation-standard-and-audit) for the authoring lifecycle. The first law and state closure retain separate assumptions; replay is checked against the actual compiled volume. Heat assumptions, unsupported energy terms, phase-policy disagreement and competing manual/package closures cannot silently change the executed physics. Shared results retain the derivation report. None of this adds arbitrary DAE, spatial energy or reaction-energy support; the [capability inventory](engine-checklist.md) records those limits.

## 10. Momentum development

`core/balances/momentum_derivation.py` records and develops Cauchy/Navier–Stokes, control-volume and ideal-machine reductions in Model. It shares journal mechanics, model readers, units, provenance and the canonical worksheet with matter/energy. It publishes family-specific coupling relations rather than silently changing the energy or material generator. Its scalar symbolic relations are checked numerically and dimensionally. The common compiler now admits the explicit constant-density isothermal hydraulic specialization in [common model §12](../contracts/common-model.md#12-reduced-hydraulic-execution): dynamic path inertia, a recorded quasi-steady laminar circular wall closure, and hydrostatic storage pressure coupled to dynamic material inventories. Other active momentum formulations remain blocked. Numerical functions derive from the same symbolic scalar relations; shared units, RK45/BDF and Results services are reused. Run `npm run test:hydraulics` for analytical pressure and independent matrix-exponential checks. The [canonical contract](../contracts/common-model.md#11-momentum-deduction-cauchy-to-reduced-machines) specifies the exact assumptions, API, ideal centrifugal scope and remaining closures; [workspace behavior](model-workspaces.md#momentum-and-machine-deductions-20-october-2026) owns the presentation and verification record.


The hydraulic authoring correction replaces configuration-injected storage rows and a pre-solved profile with `core/modelo/equation_manipulation.py` and `core/balances/momentum_reductions.py`. Individual profile/axis/wall and pressure-reference/inventory assumptions act on expressions; the same derived expressions feed Model and compilation. Missing operations leave constants/couplings unresolved and block the numerical specialization. See [the maintained correction contract](../contracts/common-model.md#equation-operation-correction-20-october-2026).
