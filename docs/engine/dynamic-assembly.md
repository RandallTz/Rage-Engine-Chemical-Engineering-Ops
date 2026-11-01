# Assembly and dynamic solution of the independent engine

> **Retired on 23 October 2026 (user decision `dec-r5-legacy-v1`).** Revision 1 and its solver `core/ensamblaje_dinamico.py` were removed: that solver checked phase signatures at quarter points with a full-step bracket and could miss a short phase window (F9-R5). Every revision-1 case is now expressed as a revision-2 request (`tests/v1_assembly_cases.py`, field by field) and solved by the common compiler; `tests/test_retired_v1_assembly.py` reproduces the nine frozen resolutions (T, P, V, U, H and mass within 1e-7 relative, events within 1e-6 s) and the liquid-exhaustion stop against an independent IAPWS-95 reference. A revision-1 request now receives `MOTOR_ENS_REVISION_RETIRADA` (status `no_soportado`), and `GET /motor/ensamblajes/capacidades` without a revision returns a retirement notice pointing to revision 2. The shared types moved to `core/dynamic_common.py`; the exterior water enthalpy moved unchanged into `core/paquetes_volumen.py`; the protocol helpers that revision 2 reuses stay in `backend/motor_ensamblaje.py`. The frozen requests and responses in `docs/ejemplos/motor-ensamblaje-*` remain as references, and the frontend contract types were not changed. The text below documents the retired revision as delivered.

14 October 2026. It answers [docs/history/frontend/contract-claude-assembly-dynamic-engine.md](../history/frontend/contract-claude-assembly-dynamic-engine.md) (E0–E3) on top of the physics already delivered in [docs/engine/thermodynamics-h0-h1.md](thermodynamics-h0-h1.md) and [docs/engine/thermodynamics-h3.md](thermodynamics-h3.md). The backend is mine; the frontend is Codex's and was not modified. No commit or push.

**What it contains.** One volume of pure water, identified by CAS, with total matter and energy balances, an IAPWS-95 closure and a rigid or prescribed-pressure boundary. It accepts streams with the donor chosen by the sign of the flow, heat, initialization with U or T, trajectories with phases appearing and disappearing, extraction by phase or of the mixture, events and certified samples. The schema is the types of `frontend/app/motor/contratoEnsamblajeTermodinamico.ts`, unchanged. Three routes: capabilities, validate and solve.

## Requirements of the assignment

| Requirement | State | Where / evidence |
| --- | --- | --- |
| **E0** Contract formalized with the TS types, without changes of shape | Met | §1; `tests/verificar_contrato_ensamblaje.mjs` compiles 13 real pairs with `strict`, plus a negative control |
| E0 Validation of syntax, units, magnitudes, finite values and physical limits, with the origin of each datum | Met | §2; suite, sections 1 and 6 |
| E0 Catalog of variables and equations with IDs, families and LaTeX | Met | §3 |
| E0 Structural count (complete, incomplete, conflict, not evaluable) without integrating | Met | §3; sections 1 and 6 |
| E0 Compatible initialization: UV, UP, TP and **TV** (a new local operation) | Met | §4; section 3 |
| **E1** Rigid single-phase volume, closed and open, with a real variable P | Met | §5; sections 2 and 4 |
| E1 Donor by sign; reversal; pressure continuity; pending donor | Met | §5; section 4 |
| **E2** Constant and smooth prescribed pressure, work with the total derivative of V, H coordinate verified | Met | §5; section 5 |
| E2 Discontinuous pressure | **Rejected on purpose** (`MOTOR_ENS_NO_SUAVE`): the physical jump rule is missing | §5 |
| **E3/H4** Two-phase equilibrium along the trajectory, appearance and disappearance events, per-phase or homogeneous extraction, absent phase, forbidden change | Met | §6; section 8 |
| Certified samples; stopping with a partial result without invalid samples | Met | §6; section 9 |
| Examples generated from the endpoints; TS reader; full regression | Met | §7, §8 |
| Outside the assignment: several volumes, mixtures, reaction, selective transfer, solids, critical region | Not implemented; diagnosed | §9 |
| `redundante_compatible` in the count | **Not produced**: no accepted constraint is both redundant and compatible (§3) | — |

Integrator: `rk45` only. `euler_implicito` comes out `no_soportado` because it is not verified with the IAPWS closure.

---

## 1. Routes and schema

```
GET  /motor/ensamblajes/capacidades   verified scope (shape in §1.2)
POST /motor/ensamblajes/validar       SolicitudEnsamblajeDinamico -> RespuestaValidacionDinamica
POST /motor/ensamblajes/resolver      SolicitudEnsamblajeDinamico -> RespuestaResolucionDinamica
```

It is revision 1 of the assembly protocol, independent of revision 1 of the point API, which does not change. The point API still publishes `dinamica: false`; being able to integrate does not change the meaning of that flag. The body is read as free JSON and the response is HTTP 200 with contract diagnostics: there is no 422 for known errors. A rejection never keeps earlier results: `resultados: null`.

### 1.1 Responses

- **validar**: `{revision, solicitudId, modeloId, recuento, variables, ecuaciones, diagnosticos, inicializacion}`. It does not integrate. `inicializacion.estadoTermodinamico` is an `EvaluacionEstado` certified by the point service, or `null`.
- **resolver**: `{validacion, estado, resultados}`. The validation comes complete. `estado` is:
  - `resuelto`: integrated up to tf;
  - `parcial`: stopped by a policy event, an absent phase, leaving the domain, depletion, or a donor at saturation;
  - `no_soportado`: some `no_soportado` diagnosis;
  - `invalido`: a count other than `listo`, an incompatible initialization or pending diagnostics;
  - `no_convergente`.
- `resultados` carries:
  - `metodo`: integrator, tolerances, steps, retries and how events are watched;
  - `tiempos` and `series`, all in SI;
  - `estadosTermodinamicos`: one certified `EvaluacionEstado` per sample, without the long `motivo` of the checks (optional in the type);
  - `eventos` and `residuos`.
- **Series:** `volumen.<v>.m.<c>`, `.U`, `.T`, `.P`, `.V` and `.q` (vapor mass fraction, defined below); `.H` and `.W` only with prescribed pressure; `.Q`; `corriente.<i>.F` (kg/s, signed, in the declared direction) and `corriente.<i>.h` (the donor's enthalpy). If a sample does not define h (absent extraction phase), that series is **not published**: the types do not admit nulls inside `valores`.
- **Vapor fraction `q`** (initial variable and series, the same definition in both): the sum of the `fraccionMasica` of the `vapor`-type phases present in the certified state, inside or outside the dome. Superheated vapor gives q = 1 even without coexistence; liquid, 0; in coexistence, the quality. A supercritical fluid (type `fluido`, T > Tc and P > Pc) is not vapor: q = 0, read together with the published phases. Above Tc with P ≤ Pc, H1's convention calls the phase `vapor`, so q = 1. It is the definition `lectorEnsamblajeTermodinamico.ts` applies. *Correction of 14/10/2026 (incident [docs/history/frontend/incident-claude-fraction-vapor-assembly.md](../history/frontend/incident-claude-fraction-vapor-assembly.md))*: before, a single vapor phase only counted q = 1 if it carried the `equilibrio` check, and superheated vapor came out with q = 0.
- **`modeloId`**: `ens-` and 32 hexadecimal characters of a SHA-256 of the normalized assembly. In it go the CAS and M, the model and the policy, the IAPWS reference, balances and forms, the boundary type with its data in SI, Q, each stream with its sign, flow, donor, continuity and extraction, and the initial values in SI. `solicitudId`, `derivacion`, `origen`, `estudio` and results do not go in. Equivalent units of a constant datum give the same identity (10 L and 0.01 m³); a function of t goes in as a canonical form plus factor and offset, so "200·t kPa" and "2·t bar" are treated as different (a declared limitation). It is `null` if there are invalid data.

### 1.2 Capabilities: an additive shape without a TS type

Proposed for Codex to add:

```ts
export type CapacidadesEnsamblaje={revision:1;disponible:boolean;motivo:string|null;modelos:ModeloEstado[];
  componentesCAS:string[];volumenes:number;componentes:number;balances:{materia:boolean;energia:boolean;momento:boolean};
  formas:{materia:'cantidad';energia:'total'};fronteras:('rigida'|'presion_prescrita')[];
  inicializaciones:Record<'rigida'|'presion_prescrita',('U'|'T')[]>;presionPrescrita:{constante:boolean;funcionSuave:boolean;discontinua:boolean};
  corrientes:{mecanismos:'convectivo'[];materia:('por_componente'|'total_y_composicion')[];presionExterior:('dato'|'continuidad')[];inversion:boolean};
  extracciones:('mezcla_homogenea'|'fase')[];fases:{monofasico:boolean;coexistenciaLiquidoVapor:boolean;eventos:boolean};
  transferencias:'calor'[];expresiones:{variables:['t'];unidadTiempo:'s';suaves:string[];noAdmitidas:string[]};
  integradores:{id:'rk45';nombre:string;tolerancias:string[]}[];muestrasMaximas:number;dinamicaApiPuntual:false};
```

### 1.3 Diagnostics

`DiagnosticoPreparacion` = `{codigo, estado, mensaje, variableIds, origen:{propietarioId, ruta}}`. If the problem is in a datum, `origen` is **the datum's** (owner and path to the sheet's field). If it is in the structure, the path is a JSON pointer into the request.

| Code | State | When |
| --- | --- | --- |
| `MOTOR_ENS_DATO_PENDIENTE` | incompleto | blank text (pending, never zero) |
| `MOTOR_ENS_UNIDAD`, `MOTOR_ENS_MAGNITUD`, `MOTOR_ENS_FUNCION_DATO` | invalido | a unit of another family, an unexpected quantity, a wrong function (`inicial`, `frontera`, `geometria`, `estudio`) |
| `MOTOR_ENS_EXPRESION`, `MOTOR_ENS_DEBE_SER_CONSTANTE` | invalido | syntax, a non-finite value in [0, tf], t in a datum that must be constant |
| `MOTOR_ENS_NO_SUAVE` | no_soportado | abs, min, max or step in a datum (a jump without a physical rule) |
| `MOTOR_ENS_FUERA_DE_MAGNITUD` | invalido | T, P, V or tf not positive in [0, tf]; a negative amount |
| `MOTOR_ENS_REFERENCIA`, `MOTOR_ENS_FALTA`, `MOTOR_ENS_CAMPO_NO_ADMITIDO`, `MOTOR_ENS_FORMA` | invalido | structure (a `termodinamica` with a saved query is rejected) |
| `MOTOR_ENS_COMPONENTES`, `…_COMPONENTE_NO_SOPORTADO`, `…_IDENTIDAD_NO_VERIFICABLE` | no_soportado | more than one component, another CAS, proveedorId |
| `MOTOR_ENS_IDENTIDAD` / `…_CAS_INVALIDO` / `…_MASA_MOLAR_CONTRADICTORIA` | incompleto / invalido / invalido | identity; the contradictory molar mass is kept and rejected |
| `MOTOR_ENS_BALANCES`, `…_FORMA`, `…_TERMINOS`, `…_ESTACIONARIO`, `…_FUENTES`, `…_SELECTIVO`, `…_TRANSFERENCIA`, `…_METODO`, `…_MODELO` | no_soportado | outside the accepted regime |
| `MOTOR_ENS_DOS_CIERRES` | conflicto | manual u(T) and EOS at the same time |
| `MOTOR_ENS_DENSIDAD` | conflicto | density declared constant (a constraint additional to the EOS) |
| `MOTOR_ENS_POLITICA` | conflicto | phase hypotheses of matter or energy different from the closure's (without OR) |
| `MOTOR_ENS_FRONTERA`, `MOTOR_ENS_CONTEXTO`, `MOTOR_ENS_EXTRACCION` | conflicto or invalido | inconsistent boundary and formulation; ports without a stream; different extraction in the stream and in the closure |
| `MOTOR_ENS_MECANICA` | incompleto | a moving boundary without a mechanical relation |
| `MOTOR_ENS_Q_PENDIENTE` / `MOTOR_ENS_Q_ADIABATICO` | incompleto / conflicto | no heat and not adiabatic (an empty Q ≠ 0) / adiabatic with heat |
| `MOTOR_ENS_DONANTE_PENDIENTE` | incompleto | matter can enter and there is no external state; `variableIds` = `corriente.<i>.Text`, `.Pext` |
| `MOTOR_ENS_P_DUPLICADA` | conflicto | continuity and a pressure datum in the same stream |
| `MOTOR_ENS_EXTRACCION` | incompleto | multiphase possible, the stream can extract and there is no extraction policy |
| `MOTOR_ENS_SOBREDETERMINADO` | conflicto | an equation without an unknown of its own, e.g. an additional P in a rigid volume; it refers to the data involved |
| `MOTOR_ENS_INICIAL…` | depending on the case | initialization (§4); the point service's codes are prefixed with `MOTOR_ENS_INICIAL.` |
| `MOTOR_ENS_DETENIDO_<EVENTO>` | invalido | trajectory stopped; it comes with `estado: parcial` |
| `MOTOR_ENS_MUESTRA_NO_CERTIFICADA`, `…_DONANTE_NO_CERTIFICADO` | invalido | a sample or a donor is not certified: it is cut before it |

---

## 2. Data and a single source

- **Where the values are.** Only in `datos`: one record per ID with quantity, function, text, unit and origin. The volume and the streams keep references.
- **Which data are read.** Only those referenced by the active structure. A datum of the inactive mode (for example, T0 when the initial energy is U) is not read or turned into a constraint.
- **Units.** The table of `unidadesMotor.ts`, with offset for °C and °F.
- **Expressions** (`core/expresiones_motor.py`):
  - the same grammar as `expresionesMotor.ts`, parsed into a tree of its own, never with `eval`;
  - **t is time in seconds** whatever the datum's unit, and it is accepted only in `frontera` data;
  - they are evaluated at 401 points of [0, tf] to check that they are finite and respect the physical sign;
  - the dP/dt of a prescribed pressure comes from the tree's **symbolic derivative**, checked against finite differences.
- **Flows.**
  - The two modes are exclusive.
  - The basis of the flow and that of the composition are kept separately.
  - Mass ↔ moles uses the model's molar mass (18.015268 g/mol), never a universal conversion.
  - With one component, `total_y_composicion` requires the fraction 1 on its basis; the suite checks that a molar flow with a mass composition gives exactly the same as the equivalent mass flow.
- **External donor.**
  - It is required unless the flow is constant and matter cannot enter (a constant positive outlet, or zero).
  - An expression in t can reverse the direction and requires a donor.
  - A constant zero carries no energy and asks for no donor.
- **Extraction.** With a non-single-phase policy, it is required only of the streams that can extract: a non-zero outlet or a flow that depends on t. A constant positive inlet never extracts, and is declared so. The frontend asks all of them for it, which is stricter and compatible.

## 3. Assembly, catalog and count

**Variables** (`VariableEnsamblada.papel`):
- **Differential:** m and U in a rigid volume; m and H with prescribed pressure (there U becomes algebraic).
- **Algebraic:** T; P (rigid) or V (pressure); q; h of each stream; the donor's P with continuity; W with prescribed pressure.
- **Data:** V (rigid) or P (pressure), F, Q, T_ext, P_ext. A pending datum becomes one more unknown.

**Equations** (`EcuacionEnsamblada`, families matter, energy, state and mechanics):

| id | Relation |
| --- | --- |
| `materia.<c>` | dm/dt = Σ s_j F_j |
| `energia` | rigid: dU/dt = Σ s_j F_j h_j + Q − P dV/dt, with V = V_geom ⇒ dV/dt = 0. Pressure: dH/dt = J_E + V dP/dt, with H = U + PV |
| `estado.u` / `estado.h`, `estado.v`, `estado.reparto` | UV closure (rigid) or PH (pressure): T, P or V and q, by maximum of S |
| `estado.U`, `mecanica.trabajo` | pressure: U = H − PV; dW/dt = P dV/dt with the total derivative (check of the U form) |
| `estado.donante.<i>` | h_j: external h(T_ext, P_donor) if s_j F_j > 0; of the volume (mixture or phase) if < 0 |
| `mecanica.continuidad.<i>` | P_donor = P of the volume |
| `mecanica.P_restriccion` | P = P_datum in a rigid volume (an additional constraint: conflict) |
| `estado.flujo` | if the formulation keeps u + Pv in the transport: the identity u + Pv ≡ h is published and solved with h |

**Count.** It is a **structural** analysis: maximum matching (augmenting paths) between equations and unknowns. The unknowns are the derivatives of the states, the algebraic variables and the pending data; the latter are matched last, so that, if an unknown is left over, it is **the missing datum** that is pointed out and not an internal variable.

- An equation without a match → `conflicto`, with `MOTOR_ENS_SOBREDETERMINADO`.
- An unknown without a match, a missing datum or a missing initial value → `incompleto`; `gradosLibertad` = unknowns − equations.
- Invalid data → `no_evaluable`, with the numbers null.
- `ecuacionesIndependientes` is the structural rank.
- The phase rule is not subtracted separately: the equilibrium closure fixes the split.
- `datosDefinidos` and `datosFaltantes` count the referenced data.
- **The count neither integrates nor evaluates the EOS.**

## 4. Initialization

Always through the **local point service**, without HTTP, with the closure's policy. There is only one active choice of initial energy.

| Boundary | Data | Operation |
| --- | --- | --- |
| Rigid | m(0), U(0), V | certified UV |
| Rigid | m(0), T(0), V | local **TV** (`agua.evaluar_TV`): minimum of A at (T, V, m); lever rule in v inside the dome. Then a certified UV with the u obtained, which must reproduce T(0) to 1e-7 |
| Pressure | m(0), U(0), P(0) | certified UP |
| Pressure | m(0), T(0), P(0) | certified TP. At saturation → `pendiente` (an energy or split specification is missing; q is not invented) |

Resulting states:
- `compatible`: it publishes the initial variables and the `EvaluacionEstado`.
- `incompatible`: a state outside the domain (e.g. U(0) below the triple point), a policy violated at t = 0 (single-phase with a two-phase state) or a zero initial mass (no intensive state).
- `no_soportada`: critical region.

No result of an earlier query is used as a seed. `c_u` does not take part.

## 5. Physics of the trajectory (E1, E2)

**Rigid volume.** States (m, U); u = U/m, v = V/m → UV → T, P, phases. The pressure changes on heating: in Codex's real sheet (10 kg in 10 L, 1 kW, 300 s) it goes from 6.08 to 10.89 MPa, and U = U₀ + Q·t exactly.

**Prescribed pressure.** Quasi-static, with uniform P equal to P_ext(t), smooth. H coordinate:

$$\frac{dU}{dt} = J_E - P\frac{dV}{dt},\ H = U + PV \ \Rightarrow\ \frac{dH}{dt} = J_E + V\frac{dP}{dt}$$

States (m, H): h = H/m → PH → T, v, phases; V = m·v and U = H − PV are rebuilt, not integrated. To **verify** the equivalence, W = ∫P dV/dt dt is integrated separately with the total derivative:

$$\frac{dV}{dt} = v\frac{dm}{dt} + m\Big[\Big(\frac{\partial v}{\partial h}\Big)_P\frac{dh}{dt} + \Big(\frac{\partial v}{\partial P}\Big)_h\frac{dP}{dt}\Big],\qquad \frac{dh}{dt} = \frac{dH/dt - h\,dm/dt}{m}$$

- **Derivatives in one phase**, analytical from the EOS:
  - (∂v/∂h)_P = (∂v/∂T)_P / cp;
  - (∂v/∂P)_h = (∂v/∂P)_T − (∂v/∂T)_P (v − T(∂v/∂T)_P)/cp.
- **Derivatives in coexistence:**
  - (∂v/∂h)_P = (v″−v′)/(h″−h′);
  - (∂v/∂P)_h by central differences of PH (δP = 1e-6·P), only if dP/dt ≠ 0.
- **Published residual:** `energia` = |U − (U₀ + ∫J_E dt − W)|. A constant dm/dt/ρ is never used.
- **Independent test:** a quasi-static adiabatic compression with P(t) as a ramp and as a sine must be **isentropic**. It holds with |Δs| ≤ 1.0e-6 J/(kg·K) at every certified sample, and that condition appears in none of the coordinator's equations.

**Streams.**
- J_E = Σ s_j F_j h_j + Q.
- The donor by the **current** sign: external h(T_ext(t), P_donor(t)) when entering; the volume when leaving.
- `continuidad` takes P_donor = P of the volume at each evaluation.
- The external state is that of the transport plane: no invisible valve, pump or loss is interposed.
- If the external donor falls on saturation, the trajectory stops with `donante_en_saturacion`. It is a real case: by continuity, the donor follows the vessel's pressure up to Psat(T_ext).

**What the EOS does not do.** It recovers the mechanical equilibrium of a lumped state. It is not a momentum balance, it does not predict hydraulic flows and it adds no pump work.

## 6. Integration, phases and events (E3/H4)

**Integrator.**
- Dormand-Prince 5(4) (`scipy.integrate.RK45`), with `rtol` and `atol` separated by quantity: mass in kg, energy in J.
- Maximum step = the sampling interval.
- States [m, E, ∫J_E dt, W].

**Stages.** They use fast flashes without a sweep or certification (`certificar=False`) seeded with T. The seed only speeds things up: u at fixed v and h at fixed P are monotonic, so the root of the bracket is the only one.

**Phase watch.**
- On each **accepted** step, at three interior points of the dense output and at the end. The stages of rejected attempts do not count.
- If the phase set changes, the instant is located by bisection on the dense output (tolerance 1e-9·tf). Then the integration is **redone from the start of the step up to that instant** (with no steps crossing the kink in the properties) and the integrator is restarted.
- Event codes: `aparicion_fase`, `desaparicion_fase` and `cambio_denominacion` (liquid ↔ fluid ↔ vapor without coexistence, which is not a phase transition).
- A change that comes and goes within one step and is not seen at those 4 points could go unnoticed. That is the declared scope: the watch is pointwise; it does not certify the whole trajectory.

**Policies.**
- `cambioInterno: prohibido` stops the trajectory at any appearance or disappearance.
- `monofasico` stops it when a second phase appears.
- `tiposPermitidos` stops it at a type that is not allowed.
- The certified samples up to the instant of the event, which is also a sample, are published, and the response is `parcial`.

**A flash failing at a stage.**
- Properties from the previous stage are not reused: it repeats from the last accepted state with the step divided by 4.
- Below 1e-10·tf it stops with `salida_dominio`, `agotamiento`, `donante_en_saturacion` or `fase_ausente`, depending on the reason.
- An extraction phase absent at t = 0 stops at t = 0 with the initial sample.

**Samples.**
- Uniform in [0, tf], plus the instant of each event and of the stop.
- Each one is **certified** with the point service (UV or PH with a global sweep and stability).
- Active external donors are certified with TP.
- If a sample is not certified, the trajectory is cut before it: there are no invalid samples or substitutes.

**Latent heat.** No source is added: it is in h″ − h′. The test checks it, because H = H₀ + Q·t exactly throughout the boiling.

### Published residuals (`resultados.residuos`)

| ecuacionId | maximoEscalado | tolerance |
| --- | --- | --- |
| `materia.<c>` | max\|m − m₀ − ∫Σ s F dt\| with an **independent** quadrature (`quad`) of the flows, divided by (atol_m + rtol·max m) | 10 |
| `energia` | max\|U − (U₀ + ∫J_E − W)\| / (atol_E + rtol·max(\|U\|, \|∫J_E\|)). With pressure it is the equivalence U form ↔ H form; in a rigid volume it is a bookkeeping check | 10 |
| `estado.u` / `estado.h` | max\|m·u_cert − U\| (or h_cert, H) of the certified state / energy scale | 1 |
| `estado.v` | max\|m·v_cert − V\|/V / 1e-9 | 1 |
| `mecanica.P` | pressure: max\|P_cert − P_ext(t)\|/P / 1e-12 | 1 |
| `estado.donante` | max\|certified TP h − h used\|/(RT) / 1e-9 | 1 |

---

## 7. Evidence

```
python tests/validar_motor_ensamblaje.py                # 239 checks, ~1.5 min
node tests/generar_solicitudes_ensamblaje.mjs           # REAL requests with prepararEnsamblajeTermodinamico
python tests/generar_ejemplos_motor_ensamblaje.py       # docs/ejemplos/motor-ensamblaje-* from the endpoints
node tests/verificar_contrato_ensamblaje.mjs            # strict TS types + 175 EvaluacionEstado through the point reader
```

| Test (section of the suite) | Independent reference | Result |
| --- | --- | --- |
| 1. Incomplete request | — | count `incompleto` with the datum and its path; initialization `pendiente` and empty; resolver does not integrate; a missing Q ≠ 0 |
| 2. Closed rigid | U = U₀ + Q·t exactly; **evaluar_TP(T, P)** of each sample returns u = U/m and v = V/m (a different path from the UV closure) | U exact to 1e-6; v to 1e-8; P from 6.08 to 10.9 MPa |
| 3. Initialization | T(0) → TV → U(0) → UV → T(0); °C and K | U reproduced to 1e-3 J; incompatible and pending cases correct |
| 4. Rigid filling | m = m₀ + F·t; U = U₀ + F·h_in·t exactly | exact to 1e-7 relative |
| 4. Draining with heat, reversal F = 0.8·cos(0.05t), continuity | **fixed-step RK4** of the test with the core's flashes | ≤ 1e-6 to 2e-6 relative; external donor h when entering and the volume's when leaving |
| 5. Constant P | H = H₀ + Q·t, W = P(V − V₀), U = H − PV exactly | to 1e-6 |
| 5. Smooth adiabatic P (ramp and sine) | **constant s** (second law) | \|Δs\| ≤ 1.0e-6 J/(kg·K); `energia` residual 0.019 of the tolerance |
| 6. Constraints and duplicates | — | u(T) + EOS, additional P in a rigid volume, constant density, policies, continuity + datum, molar mass, units; identity stable against units and titles |
| 7. Convergence | series of rtol 1e-5 … 1e-11 | decreasing errors; < 1e-6 relative at rtol 1e-9 |
| 8. Boiling at 1 bar, 10 kW, 1 kg | t_boil = m(h′ − h₀)/Q, t_dry = m(h″ − h₀)/Q | events at 33.349786 and 259.094162 s (theory 33.349786 and 259.094162); T = Tsat during the plateau to 1e-8 K; H = H₀ + Q·t (no double latent heat) |
| 8. Condensation in a rigid volume (2 kg, 1 m³, −5 kW) | t* with v″(T*) = V/m and u″(T*) | event at 55.220155 s, equal to the theory to 1e-6 |
| 8. Extraction by phase | h′, h″ and h of the state | exactly h_l, h_v or h is extracted; U_vapor < U_mixture < U_liquid |
| 8. Absent phase and forbidden policy | — | `parcial` at the event; extracting vapor from a liquid stops at t = 0; the extracted liquid runs out at 7.27 s |
| 9. Domain and depletion | — | rigid heating until above 100 MPa and draining until empty: `parcial` with certified samples; an invalid U(0) does not integrate |
| 11. Vapor fraction | `q` against the phase split published in the initialization and at **every** sample: liquid, coexistence, superheated vapor, entering and leaving the dome, supercritical fluid, and the event sample that a policy stops | equal to 1e-12 in all |
| 10. HTTP and real frontend requests | `prepararEnsamblajeTermodinamico` on Codex's test sheets | all 5 validate; the real rigid one solves over HTTP |

Typical times with 101 samples: 4 to 7 s. Certifying each sample, with a global sweep and TPD, dominates. `coexistencia(T)` and `saturacion(T)` are memoized: they are pure functions of T and the cache changes no result (the H1 and H3 suites pass the same).

## 8. Examples (`docs/ejemplos/motor-ensamblaje-*`)

Generated from the endpoints. Several requests are the frontend's real requests.

| Case | Result |
| --- | --- |
| `capacidades` | published scope |
| `validar-incompleto` | blank V: `incompleto`, it blames `volumen.dominio.V` |
| `validar-conflicto-dos-cierres` | real sheet with manual u(T): `MOTOR_ENS_DOS_CIERRES` |
| `validar-conflicto-P-rigida` | real rigid sheet with P: `conflicto`, `MOTOR_ENS_SOBREDETERMINADO` |
| `validar-inicial-T-rigida` | real sheet with T(0): compatible TV (293.15 K, 4.03 MPa) |
| `resolver-rigida-calentamiento` | real sheet: 297.10 → 304.42 K, 6.08 → 10.89 MPa |
| `resolver-abierta-presion-constante` | real sheet open at 1 bar, inlet 3 kg/s at 40 °C and 2 bar, outlet 2 kg/s, 8 kW |
| `resolver-llenado-rigido` | filling a liquid-full vessel with pressure continuity: 7.83 → 12.48 MPa |
| `resolver-vaciado-con-ebullicion` | outlet 1.5 kg/s with 20 kW from a state with a trace of vapor |
| `resolver-presion-suave-adiabatica` | P = 3e5 + 2e5·sin(0.05t): isentropic |
| `resolver-ebullicion-presion-constante` | appearance and disappearance of a phase at the theoretical times |
| `resolver-condensacion-rigida` | liquid appears at 55.22 s |
| `resolver-extraccion-liquido` | extracted phase exhausted: `parcial` |
| `resolver-cambio-fase-prohibido` | single-phase policy: `parcial` at the event |

## 9. Integration guide for Codex

1. **Capabilities.** Read `GET /motor/ensamblajes/capacidades` and offer only what is published. If `disponible: false`, show `motivo`.
2. **Validate.** Send the result of `prepararEnsamblajeTermodinamico` as is to `/validar`, also with local diagnostics if the backend's analysis is wanted. Show `recuento` (with `motivo`), the `ecuaciones` (LaTeX) and the diagnostics by `origen.ruta`. A compatible initialization carries T, P, V and q, and an `EvaluacionEstado` the point reader accepts.
3. **Solve.** Call `/resolver` only with `recuento.estado === 'listo'` and a `compatible` initialization; the backend checks it again. Discard late responses by `solicitudId` and invalidate the result if `modeloId` changes.
4. **Results.** The series are in SI and by `variableId`. `estadosTermodinamicos[k]` corresponds to `tiempos[k]`. Events carry their code and instant. With `estado: 'parcial'`, the `MOTOR_ENS_DETENIDO_*` diagnostics say why.
5. **Units.** The variable t of the expressions is **seconds**.
6. **No network in the integrator.** The coordinator calls the properties locally.
7. **Dynamic closure and manual engine kept apart.** A solution is not a saved query, and the manual engine with u(T) remains intact.
8. **Reload.** uvicorn must be restarted: there are new routes and modules.

## 10. Files

| File | Change |
| --- | --- |
| `backend/main.py` | +3 routes and imports (additions only; mixed line endings respected) |
| `backend/motor_ensamblaje.py` | new: contract, validation, assembly, count, initialization, solution |
| `core/ensamblaje_dinamico.py` | new: numerical coordinator |
| `core/expresiones_motor.py` | new: safe expressions and symbolic derivative |
| `core/agua_iapws95.py` | added: `evaluar_TV`, `certificar=False` and `T_semilla` (everything the same as H3 by default), cache of `coexistencia` and `saturacion` |
| `tests/validar_motor_ensamblaje.py`, `tests/generar_ejemplos_motor_ensamblaje.py`, `tests/verificar_contrato_ensamblaje.mjs`, `tests/generar_solicitudes_ensamblaje.mjs`, `tests/fixtures_ensamblaje/*.json` | new |
| this document, `docs/ejemplos/motor-ensamblaje-*` | new |

The frontend, the lab and `thermodynamics/proveedor.py` were not touched.

## 11. Real limits and pending items

- One volume, one component (water), without reaction, selective transfer, momentum or solids. The critical region (Tsat > 643.86 K) is rejected as in H3.
- Pressure with steps stays rejected until the jump rule is defined (work impulse and reinitialization).
- Non-smooth functions (abs, min, max, step) in flows, heat or external T: also rejected in this delivery.
- The phase watch is pointwise (§6). Certification is per sample, not continuous.
- The identity of functions of t does not unify equivalent units (§1.1).
- The exhaustion of an extracted phase is detected when a stage needs it and it no longer exists. The instant is bounded to 1e-10·tf, and the last published state keeps a trace (< 1e-6) of the phase that runs out.
- The cost of certification grows linearly with the number of samples: ~45 ms per sample in UV, with a maximum of 1001 samples.

## 12. V2 retirement parity audit

**24 October 2026, Codex; `risk-parallel-solve`. Historical inventory; the ordered compatibility migration is now approved by `dec-v2-parity-migration`. Deletion still requires separate approval.** This section describes the current revision-2 path, not the retired revision-1 scope above. The common compiler already covers substantial numerical behavior, but **v2 cannot yet be retired without losing behavior and result evidence**. This was a read-only code and fixture audit. No v2 route, solver, fixture or thermodynamics file was changed.

The primary workspace is **Solve**, consuming the versioned common model and the formulation selected in Transform. Results consumes its trajectory and certificates. Model owns the physical assumptions and recorded deductions. Migrating execution must preserve source identities, reject stale selections after physics/data edits, invalidate results when their numerical inputs change, and keep display-only renames physically neutral. The existing network UI also consumes v2 validation, catalog and diagnostics before solving. These consumers require compatibility; replacing an integrator call alone is insufficient. M1 A/B/C is complete and unchanged; its acceptance does not certify general thermodynamic-network parity.

### Routes and execution consumers

| Current interface | Implementation and consumer | Common-path coverage / migration requirement |
|---|---|---|
| `GET /motor/ensamblajes/capacidades?revision=2` | `backend/routes_engine.py` → `backend/motor_ensamblaje_v2.py:capacidades_v2`; `frontend/app/motor/servicioEnsamblajeV2.ts:capacidadesV2` | No equivalent complete assembly capability contract at `/modelo`. Retain an adapter until all capability and evidence fields have a shared owner. Omitting the revision intentionally returns the v1 retirement notice. |
| `POST /motor/ensamblajes/validar` with `revision:2` | `backend/motor_ensamblaje.py` dispatches to `validar_v2`; UI uses the structural count, variable/equation catalogs, located diagnostics, normalized identity and certified initialization | `desde_ensamblaje_v2` preserves the common representation and `relaciones` reproduces structural equation identities. `/modelo/validar`, `/modelo/compilation` and `/modelo/formulation-summary` do not reproduce the entire v2 response or its diagnostic semantics. |
| `POST /motor/ensamblajes/resolver` with `revision:2` | `resolver_v2` builds `core/ensamblaje_red.py:Red/Sistema`, then calls its integrator and publishes the v2 result | `/modelo/resolver` uses `core/compilador` and the common solver. It returns the common results contract and HTTP 422 for supported rejection categories; v2 normally returns HTTP 200 with structured statuses and `resultados:null`. Compatibility must be explicit. |
| Network Model/Solve/Results | `EspacioRedTermodinamica.tsx` calls all three service methods; `contratoEnsamblajeV2.ts`, `lectorEnsamblajeV2.ts`, `resultadoEnsamblajeV2.ts`, `estadoResolucionRed.ts`, `redTermodinamica.ts`, metadata/diagnostic and equilibrium-context helpers consume their results | Keep the shared `ModelWorksheet` layout. Preserve cancellation, stale-response rejection, result signatures, certification display, charts, exports and diagram provenance. The network route still calls v2 directly; `resolverEngine.ts` does not remove that caller. |
| Shared adapters and scientific services | `core/modelo/adaptadores.py`, `relaciones.py`, `core/termodinamica/capa.py` and `volumen.py`, package/point/diagram/catalog services | Adapters are data contracts, not a second solver. Keep them while persisted requests or fixtures need them. Point equilibrium, diagrams and package catalogs are shared science and are not retirement targets. |

### Complete published capability surface

The source of this inventory is `capacidades_v2`, `TAMANOS`, `validar_v2`, `resolver_v2` and their actual consumers. **Verified** below means a named common-path numerical test exists; **implemented** means code support without a complete v2 parity certificate; **gap** blocks retirement. Earlier acceptance counts are historical evidence, not a claim that all expensive suites were rerun for this audit. The status column is updated through the 24 October step-(c) checkpoint; section 13 distinguishes implemented scope, independent acceptance and remaining parity gates.

| V2 capability | Common compiler status and evidence |
|---|---|
| Revision 2 availability, package versions, property domains, parameter/group coverage, evidence levels, limits and unsupported combinations | **Gap in publication.** The common thermodynamic layer uses the packages, but does not replace this whole capability response. Preserve quantitative vs qualitative evidence, NRTL pair coverage and UNIFAC group coverage. |
| IAPWS-95 water: one liquid/vapor/supercritical fluid, LV coexistence; TP/PH/UP/UV/TV package operations | **Initialization accepted; dynamic subset verified.** Step (b) supplies shared TP/TV/UV/UP initialization, including prescribed-pressure U; `test_v2_initialization`, the vertical slice and retired-v1 references pass. Supercritical event parity remains blocked by the separate cold-water certification failure recorded in section 13. The rigid-mixture TV repair does not resolve this water control. |
| Ideal mixture; ChemSep NRTL; water/butanol LLE NRTL; UNIFAC original, Dortmund and original LLE | **Verified subset.** `validar_corte_vertical` covers ideal heating, NRTL heating, water/butanol decanting and coupled volumes. `validar_capa_unifac` covers seven archived UNIFAC requests against existing results and independent `thermo` references. NRTL is preserved, not extended. |
| At most 3 volumes, 7 declared species per volume, 3 phases; zero species retain identity; finite candidate stability search | **Admission implemented; complete evidence parity pending.** Shared admission enforces the native volume/species/sample limits. Claude's R7 ternary/five-species controls cover permutations, scaling and absent species, but are not a proof of every advertised combination. Preserve the size matrix below and finite-search caveats in the step-(d) capability adapter. |
| Rigid and prescribed-pressure boundaries; smooth pressure functions; `dH/dt = J_E + V dP/dt` | **Verified subset; rigid-mixture rows unblocked.** Claude's approved TV bracket fix makes all six `rig_*` controls solve: U_A + U_B = U0 + Q t within 1.5e-11 J and agreement with v2 within 3.7e-9. Common step (c) also publishes accumulated work and its independent P(V - V0) check. Shared admission screens positive time data on the native 401-point horizon grid; structured stops cover later expected closure failures. The full adapter matrix remains step (d). |
| Component inventories in mass/molar input bases; total donor flow or per-component flow; external TP donor and mass/molar composition; donor reversal and pressure continuity | **Implemented / partial evidence.** `SistemaCompilado.rhs`, `_donante_exterior` and `_donante_volumen` implement these branches; water v1 parity and coupled/UNIFAC tests cover selected paths. Replay the complete v2 reversal, zero-flow, mixed-sign and missing-donor negative matrix before certification. |
| Internal transfers between distinct mixture packages sharing a thermodynamic reference; reject incompatible references | **Admission accepted.** Shared admission checks thermodynamic reference identity for material transfer. Step (b) reproduces the `f25b` incompatible-reference code alongside missing heat; `f25c` heat-only contact remains admitted. Claude's independent archive review confirms the native rejection codes. Step (d) must preserve the complete validation envelope and diagnostic precedence. |
| Imposed heat, internal/external conductance, externally declared boundary temperature | **Verified subset; shared entropy accounting delivered for review.** Step (c) reuses signed heat and entropy-exchange operations, including declared boundary temperature. Common tests retain `no_evaluable` without boundary temperature and `no_cumple` for negative entropy generation. Missing heat remains an admission rejection; a heat singularity at 50 s retains the partial prefix. |
| Homogeneous extraction or a phase; resolve multiple liquids by higher/lower density; absent/ambiguous-phase stops | **Verified subset.** Vertical-slice decanter and migrated water extraction tests cover numerical cases, including the independent liquid-exhaustion time. `fase_ambigua` is implemented; its complete v2 response/partial-publication behavior still needs parity. |
| Phase policies: monophase, forbidden internal change, allowed phase types | **Verified subset.** Common `admite` applies these policies; UNIFAC monophase and phase-window regressions cover selected transitions. Preserve each native diagnostic and partial-result meaning. |
| RK45 with seeded closures, tolerances, accepted/rejected steps, at most 1001 requested samples, event samples and final point | **Verified integration subset.** Common RK45/BDF, narrow-window, margin and stage-stop tests pass; v2 remains RK45-only by contract and implicit Euler is explicitly rejected. Common compilation inspection advertises the executed method and auxiliary count. Shared publication preserves event replacement/deduplication; full method/HTTP compatibility is checked in step (d). |
| Phase appearance/disappearance, substitution and supercritical denomination changes; stable phase IDs across samples; stored event-side state | **Shared publication implemented; complete event parity pending.** Common step (c) reuses typed event classification, stable phase tracking and certified event-side publication with before/after IDs. The independent narrow-window control retains all three transitions. Supercritical-water cold certification is an explicit expected-failure target; substitution and the full adjunct event matrix still require step-(d) parity evidence. |
| Certified thermodynamic states and chemical potentials per sample; all candidate phases and complementarity | **Delivered for review.** Common results retain the shared `estados`/`potenciales` payload in `procedencia.equilibrium`, alongside candidate phase series. Unavailable samples truncate aligned arrays/events to the certified prefix; no initial publishable sample yields an empty failed result. Common tests inject both publication failures and retained physical failures. |
| Series for n, U/H, T/P/V, mass, entropy, boundary work, signed stream molar rate, heat rate and entropy generation; series catalog with role/provenance | **Delivered for review.** Shared Python publication supplies these quantities and catalog roles to the common result, including extensive potential units and package provenance. The common reader checks agreement with the retained equilibrium payload. V2 wire aliases and consumer routing remain step (d), not frontend physics. |
| Global component/energy residuals, integrated-vs-certified energy and volume, independent boundary-work identity | **Shared residuals delivered for review.** Step (c) retains existing native residual definitions and tolerances. Common controls independently check n = n0 - F t and W = P(V - V0), and retain failed work evidence under injected corruption. The native 1e-6 extensive-scale control still has about 2.85% work drift and physical `no_cumple`; no tolerance was changed to hide it. |
| Second law (`cumple`, `no_cumple`, `no_evaluable`); missing boundary T stays unevaluable | **Delivered for review.** Common integration reuses entropy auxiliaries and shared second-law publication. Missing boundary temperature remains `no_evaluable`; deliberately negative generation retains its evidence and `no_cumple`. These common controls complement the 128-check native consolidation suite. |
| Aggregate physical certification separate from numerical `estado`; last certified sample; partial trajectory and located stop diagnostic | **Delivered for review.** Common provenance carries all four aspects, first failure, last certified sample and actual scope separately from numerical completion. Python/TypeScript readers reject inconsistent aggregation or misaligned evidence. `resuelto` never asserts physical `cumple`; the open supercritical target prevents full step-(c) acceptance. |
| Model identity, package fingerprints and model provenance used to compare a trajectory with diagrams | **Scientific provenance delivered; compatibility pending.** Common step (c) reuses package fingerprints, model provenance and the series catalog. Complete v2 model-identity normalization and wire aliases for series, equations, residual references and catalog links remain step (d). Preserve diagram comparison and saved-result invalidation. |
| Unsupported selective transfer, reaction, electrolytes, membranes, nucleation, capillarity, momentum, pressure jumps, dynamic ice and mixture solids; ideal-mixture LL impossibility, filled incompressible rigid-liquid indeterminacy and critical-region limits | **Preserve boundaries.** These are explicit native restrictions, not migration opportunities. The common compiler also rejects many of them; audit exact admission/diagnostics rather than assuming all guards coincide. Static ice and diagrams remain separate supported services. |

The native size evidence matrix must survive migration with its original meaning (static evidence does not imply dynamic parity):

| Package | Static species counts | Dynamic species counts |
|---|---|---|
| `agua-iapws95` | 1 | 1 |
| `mezcla-ideal` | 2, 3, 4, 5, 7 | 2, 4, 5, 7 |
| `nrtl-chemsep` | 2, 3, 4 | 2, 4 |
| `nrtl-lle-agua-butanol` | 2 | 2 |
| `unifac-original-public` | 2, 3, 4, 5, 7 | 2, 4, 5 |
| `unifac-dortmund-public` | 2, 3, 4, 5, 7 | 2, 4 |
| `unifac-original-lle-public` | 2, 4, 6 | 2 |

### Archived examples and their common-path evidence

All 25 top-level revision-2 request documents under `docs/ejemplos` are listed here, including negative cases and the unimplemented open-boundary draft. Their sibling validation/resolution responses are retained as references; they were not regenerated. No old examples were republished in the product library.

| Request document (relative to `docs/ejemplos/`) | Common compile-only probe | Numerical parity evidence / remaining work |
|---|---|---|
| [borrador-frontera-abierta/olla-abierta-peticion.json](../ejemplos/borrador-frontera-abierta/olla-abierta-peticion.json) | Rejected: unsupported rigid-with-pressure boundary type. |Unsupported draft, not a delivered dynamic capability; no migration expansion. |
| [demostracion/demostracion-heteroazeotropo-agua-butanol-peticion.json](../ejemplos/demostracion/demostracion-heteroazeotropo-agua-butanol-peticion.json) | Admitted | Native fixture exists; common end-to-end parity for this exact request not established by this audit. |
| [demostracion/demostracion-rayleigh-etanol-agua-peticion.json](../ejemplos/demostracion/demostracion-rayleigh-etanol-agua-peticion.json) | Admitted | Native fixture exists; common end-to-end parity for this exact request not established by this audit. |
| [motor-catalogo/motor-ensamblaje-v2-resolver-acetona-agua-unifac-peticion.json](../ejemplos/motor-catalogo/motor-ensamblaje-v2-resolver-acetona-agua-unifac-peticion.json) | Admitted | Native fixture exists; common end-to-end parity for this exact request not established by this audit. |
| [motor-catalogo/motor-ensamblaje-v2-resolver-contacto-iapws-y-mezcla-peticion.json](../ejemplos/motor-catalogo/motor-ensamblaje-v2-resolver-contacto-iapws-y-mezcla-peticion.json) | Admitted | Positive control (`f25c`): heat contact only, no material stream; the archived resolution succeeds. Preserve this admission while rejecting the incompatible material stream in `f25b`. |
| [motor-catalogo/motor-ensamblaje-v2-resolver-corriente-nrtl-a-unifac-peticion.json](../ejemplos/motor-catalogo/motor-ensamblaje-v2-resolver-corriente-nrtl-a-unifac-peticion.json) | Admitted | Native fixture exists; common end-to-end parity for this exact request not established by this audit. |
| [motor-catalogo/motor-ensamblaje-v2-resolver-sustitucion-vl-etanol-peticion.json](../ejemplos/motor-catalogo/motor-ensamblaje-v2-resolver-sustitucion-vl-etanol-peticion.json) | Admitted | Native fixture exists; common end-to-end parity for this exact request not established by this audit. |
| [motor-catalogo/motor-ensamblaje-v2-validar-rechazo-corriente-iapws-a-mezcla-peticion.json](../ejemplos/motor-catalogo/motor-ensamblaje-v2-validar-rechazo-corriente-iapws-a-mezcla-peticion.json) | NoSoportado: Volume A: declare a heat exchange (including an explicit zero) or an adiabatic boundary. | Negative/incomplete input; compare precise native diagnostic and initialization status. |
| [motor-n-componentes/motor-ensamblaje-v2-resolver-calentamiento-ideal-5-peticion.json](../ejemplos/motor-n-componentes/motor-ensamblaje-v2-resolver-calentamiento-ideal-5-peticion.json) | Admitted | Native fixture exists; common end-to-end parity for this exact request not established by this audit. |
| [motor-n-componentes/motor-ensamblaje-v2-resolver-calentamiento-nrtl-4-peticion.json](../ejemplos/motor-n-componentes/motor-ensamblaje-v2-resolver-calentamiento-nrtl-4-peticion.json) | Admitted | Native fixture exists; common end-to-end parity for this exact request not established by this audit. |
| [motor-n-componentes/motor-ensamblaje-v2-resolver-red-ideal-5-especie-entrante-peticion.json](../ejemplos/motor-n-componentes/motor-ensamblaje-v2-resolver-red-ideal-5-especie-entrante-peticion.json) | Admitted | Native fixture exists; common end-to-end parity for this exact request not established by this audit. |
| [motor-n-componentes/motor-ensamblaje-v2-validar-nrtl-4-par-ausente-peticion.json](../ejemplos/motor-n-componentes/motor-ensamblaje-v2-validar-nrtl-4-par-ausente-peticion.json) | Rejected: required ChemSep NRTL pair data are unavailable. |Negative/incomplete input; compare precise native diagnostic and initialization status. |
| [motor-unifac/motor-ensamblaje-v2-resolver-unifac-calentamiento-2-peticion.json](../ejemplos/motor-unifac/motor-ensamblaje-v2-resolver-unifac-calentamiento-2-peticion.json) | Admitted | Included in the seven-request common UNIFAC acceptance; output contract still differs. |
| [motor-unifac/motor-ensamblaje-v2-resolver-unifac-calentamiento-4-peticion.json](../ejemplos/motor-unifac/motor-ensamblaje-v2-resolver-unifac-calentamiento-4-peticion.json) | Admitted | Included in the seven-request common UNIFAC acceptance; output contract still differs. |
| [motor-unifac/motor-ensamblaje-v2-resolver-unifac-dortmund-calentamiento-4-peticion.json](../ejemplos/motor-unifac/motor-ensamblaje-v2-resolver-unifac-dortmund-calentamiento-4-peticion.json) | Admitted | Included in the seven-request common UNIFAC acceptance; output contract still differs. |
| [motor-unifac/motor-ensamblaje-v2-resolver-unifac-lle-mezcla-agua-butanol-peticion.json](../ejemplos/motor-unifac/motor-ensamblaje-v2-resolver-unifac-lle-mezcla-agua-butanol-peticion.json) | Admitted | Included in the seven-request common UNIFAC acceptance; output contract still differs. |
| [motor-unifac/motor-ensamblaje-v2-resolver-unifac-monofasico-detenido-peticion.json](../ejemplos/motor-unifac/motor-ensamblaje-v2-resolver-unifac-monofasico-detenido-peticion.json) | Admitted | Included in the seven-request common UNIFAC acceptance; output contract still differs. |
| [motor-unifac/motor-ensamblaje-v2-resolver-unifac-red-5-especie-entrante-peticion.json](../ejemplos/motor-unifac/motor-ensamblaje-v2-resolver-unifac-red-5-especie-entrante-peticion.json) | Admitted | Included in the seven-request common UNIFAC acceptance; output contract still differs. |
| [motor-unifac/motor-ensamblaje-v2-validar-rechazo-unifac-simulado-asignacion-ausente-peticion.json](../ejemplos/motor-unifac/motor-ensamblaje-v2-validar-rechazo-unifac-simulado-asignacion-ausente-peticion.json) | Admitted | Included in the seven-request common UNIFAC acceptance; output contract still differs. |
| [motor-v2/motor-ensamblaje-v2-resolver-binario-acoplado-peticion.json](../ejemplos/motor-v2/motor-ensamblaje-v2-resolver-binario-acoplado-peticion.json) | Admitted | Vertical-slice state trajectory comparison; full v2 publication/certification still missing. |
| [motor-v2/motor-ensamblaje-v2-resolver-calentamiento-etanol-agua-peticion.json](../ejemplos/motor-v2/motor-ensamblaje-v2-resolver-calentamiento-etanol-agua-peticion.json) | Admitted | Vertical-slice state trajectory comparison; full v2 publication/certification still missing. |
| [motor-v2/motor-ensamblaje-v2-resolver-contacto-dos-aguas-peticion.json](../ejemplos/motor-v2/motor-ensamblaje-v2-resolver-contacto-dos-aguas-peticion.json) | Admitted | Vertical-slice state trajectory comparison; full v2 publication/certification still missing. |
| [motor-v2/motor-ensamblaje-v2-resolver-decantador-agua-butanol-peticion.json](../ejemplos/motor-v2/motor-ensamblaje-v2-resolver-decantador-agua-butanol-peticion.json) | Admitted | Vertical-slice state trajectory comparison; full v2 publication/certification still missing. |
| [motor-v2/motor-ensamblaje-v2-validar-calor-pendiente-peticion.json](../ejemplos/motor-v2/motor-ensamblaje-v2-validar-calor-pendiente-peticion.json) | NoSoportado: Volume A: declare a heat exchange (including an explicit zero) or an adiabatic boundary. | Negative/incomplete input; compare precise native diagnostic and initialization status. |
| [motor-v2/motor-ensamblaje-v2-validar-decantador-sin-criterio-peticion.json](../ejemplos/motor-v2/motor-ensamblaje-v2-validar-decantador-sin-criterio-peticion.json) | Admitted | Negative extraction case: compilation is not a solve; match its native stop/diagnostic. |

Other example producers and consumers are part of the migration inventory: `tests/solicitudes_v2.py`; the five `tests/generar_ejemplos_{motor_ensamblaje_v2,motor_n_componentes,motor_unifac,motor_catalogo,demostracion}.py` generators; `frontend/sincronizar_ejemplos_{n_componentes,unifac}.mjs`; `frontend/app/motor/hojasPrueba{Multifasico,NComponentes,UNIFAC}.ts`, `hojasDemostracion.ts`, `materialNetworkTemplates.ts`, `phaseDiscoveryExample.ts`; `frontend/examples/heatedFillingVessel.ts`; and `frontend/testing/modelFixtures.ts`. The canonical common-model JSON examples in `docs/ejemplos/modelo-comun/` exercise the adapters/results contract. The nine retired-v1 resolution fixtures remain covered through `tests/v1_assembly_cases.py` and `tests/test_retired_v1_assembly.py`. These are regression inputs, not authorization to repopulate the product library.

### Test and dependency inventory

The following lists combine direct v2/network imports with request-fixture, protocol and reader references. They include shared-thermodynamics and diagram tests because their v2 fixtures/metadata are consumers, not because their scientific services should be deleted. File-level inventory is not a claim that every test in a listed file exercises v2. Retain independent physical oracles when replacing a solver-to-solver comparison.

<details>
<summary>Python numerical, admission and shared-contract suites (26 files)</summary>

- `tests/test_common_phase_window.py`
- `tests/test_dynamic_definition.py`
- `tests/test_energy_derivation.py`
- `tests/test_material_derivation.py`
- `tests/test_momentum_derivation.py`
- `tests/test_retired_v1_assembly.py`
- `tests/test_solver_stability_margins.py`
- `tests/test_solver_stage_stop.py`
- `tests/test_thermodynamic_derivation.py`
- `tests/test_thermodynamic_events.py`
- `tests/test_transient_phase_window.py`
- `tests/test_workspace_handoffs.py`
- `tests/validar_capa_agua.py`
- `tests/validar_capa_termodinamica.py`
- `tests/validar_capa_unifac.py`
- `tests/validar_corte_vertical.py`
- `tests/validar_descripcion_termodinamica.py`
- `tests/validar_modelo_comun.py`
- `tests/validar_motor_catalogo.py`
- `tests/validar_motor_consolidacion_v2.py`
- `tests/validar_motor_diagramas_equilibrio.py`
- `tests/validar_motor_ensamblaje_v2.py`
- `tests/validar_motor_n_componentes.py`
- `tests/validar_motor_unifac.py`
- `tests/validar_resultados.py`
- `tests/validar_unidades.py`

</details>

<details>
<summary>TypeScript contract suites against published v2 payloads (3 files)</summary>

- `tests/verificar_contrato_catalogo.mjs`
- `tests/verificar_contrato_ensamblaje_v2.mjs`
- `tests/verificar_contrato_unifac.mjs`

</details>

<details>
<summary>Frontend v2 contracts, editing, certification, diagram and result consumers (21 files)</summary>

- `frontend/auditar_fiabilidad_evento_fase.mjs`
- `frontend/verificar_aviso_certificacion.mjs`
- `frontend/verificar_bateria_multifisica.mjs`
- `frontend/verificar_catalogo_motor.mjs`
- `frontend/verificar_cobertura_grupos.mjs`
- `frontend/verificar_consolidacion_multifasica.mjs`
- `frontend/verificar_contrato_termodinamica.mjs`
- `frontend/verificar_destinos_diagnosticos_red.mjs`
- `frontend/verificar_diagramas_equilibrio.mjs`
- `frontend/verificar_edicion_componentes_red.mjs`
- `frontend/verificar_edicion_y_operaciones_red.mjs`
- `frontend/verificar_entrega_n_componentes.mjs`
- `frontend/verificar_integracion_multifasica.mjs`
- `frontend/verificar_integracion_unifac.mjs`
- `frontend/verificar_material_journals.mjs`
- `frontend/verificar_modelo_comun.mjs`
- `frontend/verificar_paquetes_entregados.mjs`
- `frontend/verificar_preparacion_diagramas_equilibrio.mjs`
- `frontend/verificar_preparacion_paquetes.mjs`
- `frontend/verificar_reparto_componentes.mjs`
- `frontend/verificar_resultados_graficas.mjs`

</details>

Additional common-path acceptance gates: `tests/test_m1_thermal_acceptance.py`, `test_m1_coupled_acceptance.py`, `test_m1_u1_acceptance.py`, `test_derived_execution.py`, `test_hydraulic_execution.py`, `test_transformed_execution.py`, `validar_compilador_explicito.py`; `frontend/verificar_derived_lifecycle.mjs`, `verificar_equation_workbench.mjs`, `verificar_hydraulics.mjs`, `verificar_model_derivations.mjs`, `verificar_physical_journals.mjs`, `verificar_transform_execution.mjs`, `verificar_workspace_handoffs.mjs`; TypeScript and scoped ESLint. `tests/benchmark_unifac.py` owns performance evidence and must be included in the eventual R6 acceptance. `tests/ajuste_nrtl_lle_agua_butanol.py` is historical parameter-fit evidence, not a migration target.

The native-only certification and event regression suites are especially important: `validar_motor_consolidacion_v2.py` perturbs inventory/energy and checks global certification; `test_thermodynamic_events.py` rejects cached certificates, checks event-side states, auxiliary-work corruption and replacement of nearby sample times; `test_transient_phase_window.py` supplies the native window comparison. The common versions must retain the same negative controls, not just reproduce temperatures.

### Evidence and ordered migration proposal

Fresh checks for the preceding Codex checkpoint: 173 kernel/deduction tests (the 38-test workbench suite was rerun after explicitly selecting BDF in its execution fixture); 73 compiler/M1 tests (the sole frozen-B mismatch was fixed by restoring the historical frontend fixture, then fresh A/B authoring reproduced both frozen documents); 8 common phase-window/margin tests; 6 margin/stage-stop tests; TypeScript, scoped ESLint and the frontend journal, Transform, hydraulic, LLE, workbench and lifecycle verifiers. A/B/C remain 43/31/25 operations with unchanged hashes. These runs used the shared working tree, not an isolated clean checkout; mixed-author dependencies remain locally modified.

Existing numerical parity evidence: `validar_corte_vertical.py` 71 checks, `validar_capa_unifac.py` 82 checks and the nine frozen v1 resolutions in `test_retired_v1_assembly.py`; see the F9-R5 acceptance record in the roadmap for the tested source and runtime. The expensive 82-check UNIFAC suite was not repeated during this read-only inventory. The inventory below also ran all 25 native archived requests through common adaptation and compilation only: **21 admitted, 4 rejected**. Admission is neither initialization nor integration nor physical certification; negative requests that compile are explicitly retained as gaps.

1. **Freeze the parity target before implementation.** Use the requests, responses, capability matrix and suites below; include negative diagnostics, initialization, result fields, phase identity, certificate failures and performance budgets. Preserve independent references, frozen M1 and v1 fixtures. Agree on whether v2 HTTP/JSON compatibility is retained through an adapter (recommended).
2. **Close common admission and initialization gaps.** Start with reference compatibility, prescribed-pressure U initialization, size/evidence limits and rejection parity. Coordinate any `core/termodinamica/`, package or equilibrium change through a Claude-owned board claim. Codex must not edit `core/ensamblaje_red.py`.
3. **Close common Results and certification gaps.** Add the shared physical output and accounting needed for entropy, work, streams, heat, chemical potentials, package provenance, stable phase identities and certified-prefix handling. Verify each against independent references and corruption controls. Align advertised methods with executed methods.
4. **Prove parity behind a compatibility adapter.** Keep v2 routes/readers while converting their request to the common model and translating the common output to the agreed response. Compare every supported fixture and generated negative case, then move network Solve through the same Transform selection and invalidation rules as other models. Never fall back silently to the old solver.
5. **Retire only after user approval and independent review.** Require all affected suites, HTTP/reader/browser tests and R6 budgets to pass. Then obtain a separate deletion decision and a Claude-owned retirement change for the network solver. Remove only proven-unused assembly code; retain shared thermodynamics, adapters needed by persisted inputs and independent regression fixtures.

**Current stopping point (27 October 2026):** the user approved steps (a)-(e) in `dec-v2-parity-migration`. Claude independently accepted steps (a)-(c), then repaired supercritical-water certification. Its expected-failure marker is removed and all nine common Results tests pass. Step (d) has an isolated compatibility adapter and all 25 requests executed: 23 pass against fresh native v2, and 21 pass when unchanged historical responses are also enforced. Four strict comparison findings remain for Claude; full parity is not accepted. No production route switch or v2 deletion has occurred; `risk-parallel-solve` remains open.

## 13. V2 compatibility adapter contract

**Steps (a)-(d), updated 27 October 2026, Codex; contract version 1 amended after Claude's review.** The approved migration retains the revision-2 HTTP/JSON interface through a compatibility adapter. This section defines the required behavior; implementation evidence is limited to the completed steps below. The adapter translates requests and results, and the common compiler owns admission, initialization, equations, integration and physical verification. It must never silently invoke the v2 solver when the common path rejects or fails. No deletion or production route switch belongs to these steps.

### Production route switch (28 October 2026)

User decision `dec-v2-route-switch` authorizes routing the three revision-2 HTTP operations through `backend/v2_dispatch.py` to `backend/v2_compatibility.py`. The adapter invokes the common compiler; the native solver is retained without modification. Historical step-(a)-(e) statements below that no production switch was authorized describe the earlier gate, now superseded by this decision. Deletion is still not authorized.

The default server configuration (environment variable absent) uses the common adapter for `GET /motor/ensamblajes/capacidades?revision=2`, `POST /motor/ensamblajes/validar` and `POST /motor/ensamblajes/resolver` with revision 2. The omitted capability revision and non-v2 bodies keep the existing retired-v1 behavior. All existing scientific capability values, published revision, request keys, result keys, statuses, diagnostic codes and units remain those of the accepted adapter contract. This change does not broaden v2 to BDF or implicit Euler.

**Explicit native fallback:** set `RAGE_V2_ASSEMBLY_EXECUTOR=native` in the server process environment before starting/restarting an operator-owned server. This selects native v2 for all three operations; set it to `common` or remove it to restore the common path. There is no client/request/query parameter to choose an executor and no automatic fallback after a rejection, failed result or exception. A value other than exactly `common` or `native` is a configuration error, not a request to guess another path. Tests can set the environment in an isolated process. The direct Python entries `backend.motor_ensamblaje_v2.{capacidades_v2,validar_v2,resolver_v2}` remain native reference/fallback entries; the historical shared dispatcher remains unchanged for direct internal callers. This decision switches HTTP consumers, not every private Python call site. No running user or other-agent server is restarted by this change.

Each revision-2 HTTP response adds optional, versioned top-level provenance only: `executionProvenance: {version:1, path:'common-compiler'|'native-v2', selection:'default'|'server-override'}`. This includes capabilities, validation and rejected resolutions with `resultados:null`, so the selected path is recorded even without a trajectory. It does not replace package provenance `procedenciaModelo`, change request/model identity, or claim physical certification. Historical responses without it remain readable. The existing TypeScript readers retain it and reject malformed/unknown versions, paths or selections; a native result cannot claim default selection. Default/common and explicit-native route tests require deep equality to the respective direct response after removing this single provenance member. The adapter's already accepted native/common numerical and method-text differences retain the section-13 comparison rules; no scientific payload is rewritten by dispatch.

Verification uses `tests/test_v2_route_switch.py` with real in-process ASGI HTTP requests, no substituted route handler. All 25 frozen requests run freshly through both default common and explicit native HTTP execution; the existing `CompatibilityTests.compare` and predeclared parity thresholds are reused unchanged for series, potentials, events, certificates, rejections and units. Both validation routes are also compared exactly to their direct counterparts. `V2_HTTP_SHARD` / `V2_HTTP_SHARDS` partition test execution only; they do not alter the server contract or admit cached trajectories. Evidence is written under `.tmp/codex-v2-http/`, never into archived requests/responses. `tests/verificar_v2_route_switch.mjs` applies the production frontend readers to both sets of HTTP results and validations, checks historical compatibility and rejects malformed provenance. Completed supporting verification: unchanged v2 assembly validator 114 checks; consolidation validator 128; common-network Results 9 tests; v2 initialization 6; retired-v1 assembly 4; existing adapter HTTP/units, no-fallback/aliases and five-code open-boundary controls 3. Frozen frontend v2 contract verification covers 10 paired documents, 60 volume states and 12 point-state examples; the prior full adapter evidence still passes the updated readers (25 pairs, 7 adjuncts, 197 states, 19 corruption rejections). TypeScript, scoped ESLint and 1,391 physical-journal checks pass. Final fresh HTTP evidence: **25/25 passed**, covering both execution paths and both validation paths; the production readers pass all 50 publications and 394 volume states, preserve legacy responses and reject nine malformed provenance variants. All 49 frozen request/response files retain their manifest hash. Every record matches execution digest `4fbd9cc91499be01a17b6cdeacc49fe9ba79b32c4926d441af6da3afa98fea94`. The heteroazeotrope common/native times were 1370.76/64.02 s; five-species UNIFAC times were 1894.44/440.23 s under concurrent test load. The latter has relative series error 3.690e-8 and potential error 6.118e-9. Heteroazeotrope common event error is at most 3.395e-10 s; the previously adjudicated native lateness of 1.1973224e-6 s remains in `nativeFindings`, not hidden or repaired. The long shard was rebalanced: its unique heteroazeotrope case completed and passed before that owned process was stopped to avoid duplicate work; all 25 per-case comparisons completed freshly. Timings are evidence, not performance-budget acceptance. Dispatch selection/deep-equality/no-automatic-fallback controls also pass. **Status: review for Claude**; claim released, no commit, push, deletion, thermodynamic edit or archive regeneration.

**Independent review (Claude, 28 October 2026): accepted.** Read-only review on two reviewer-owned servers started from the current working tree (port 8041 without the variable, port 8042 with `RAGE_V2_ASSEMBLY_EXECUTOR=native`; both stopped by PID afterwards). (1) *Dispatch:* `GET capacidades?revision=2`, `validar` and `resolver` with revision 2 report `{version:1, path:'common-compiler', selection:'default'}` on 8041 and `{version:1, path:'native-v2', selection:'server-override'}` on 8042. The omitted capability revision, `revision:1` and `revision:true` keep the retirement notice (`MOTOR_ENS_REVISION_RETIRADA`) without provenance. (2) *No silent fallback:* live rejections stay on the selected path. These cover the IAPWS-to-mixture stream (`no_soportado`, `MOTOR_ENS_REFERENCIAS_INCOMPATIBLES` + `MOTOR_ENS_Q_PENDIENTE`, null results), missing heat (`invalido`) and two malformed bodies (`MOTOR_ENS_FALTA`/`MOTOR_ENS_FORMA`). An independent in-process ASGI fault-injection probe made native `resolver_v2` and `core.ensamblaje_red.integrar` raise. It then confirmed the following: both rejections and a valid short resolve stay on the common path; an injected typed common `NoSoportado` returns null results; unexpected adapter `resolve`/`validate` exceptions surface as HTTP 500, not a result or a native retry; with `native`, injected adapter failures are never reached; `Native`, `auto` and an empty value fail as configuration errors (HTTP 500). (3) *Evidence:* the heteroazeotrope, five-species UNIFAC network, IAPWS rejection, missing-heat rejection and coupled binary were rerun over live HTTP on both paths. All 20 validation/resolution responses equal Codex's `.tmp/codex-v2-http/` records exactly after removing provenance (maximum relative difference 0, no structural difference). Reviewer wall times: heteroazeotrope common/native 4725.6/391.8 s and five-species 4807.3/691.3 s. Both common cases ran concurrently in one server process; these are evidence, not a performance budget. (4) *Contract:* provenance is additive and optional in `contratoEnsamblajeV2.ts`; the reader accepts every response with it removed and rejects a native result claiming default selection. Revision, field names, statuses and rejection codes are unchanged. `backend/motor_ensamblaje_v2.py` was last modified on 27 October, before this switch. Validators `validar_motor_ensamblaje_v2` 114 and `validar_motor_consolidacion_v2` 128 pass, as do `tests/verificar_v2_route_switch.mjs` (25 cases, 50 publications, 394 states, nine malformed variants) and `tests/verificar_contrato_ensamblaje_v2.mjs` (10 pairs, 60 states, 12 point examples). **Non-blocking note for deletion planning:** the `common-compiler` label on capabilities and validation names the adapter route. `v2_compatibility.capabilities` still returns native `capacidades_v2`, and `validate` starts from native `validar_v2` (transitional, as recorded in step d). Deleting `backend/motor_ensamblaje_v2.py` therefore first needs those wire readers and capability tables extracted to a shared owner. The native late-event finding and performance-budget gate remain open. No commit, push, deletion or archive change.

### Interface and ownership

| Boundary | Required compatibility |
|---|---|
| Routes and revision | Keep the three `/motor/ensamblajes/{capacidades,validar,resolver}` routes and `revision: 2` request discriminator. Capabilities with `revision=2` keep `revisionesAdmitidas: [2]`; omitted revision retains the existing v1 retirement notice. |
| Request and persisted identities | Keep `SolicitudEnsamblajeV2`, units, component IDs including zero species, volume/stream/heat IDs, boundary and phase policies, package versions, initial data and study fields. Preserve optional derivation provenance through `desde_ensamblaje_v2`; conversion is not evidence that missing historical deductions occurred. No translation of persisted keys. |
| Validation | Preserve `RespuestaValidacionV2`: `solicitudId`, normalized `modeloId`, structural count, variable/equation catalogs, diagnostics and per-volume certified initialization. `recuento.estado: listo` alone never authorizes a solve. Pending, incompatible and unsupported initialization remain distinct. |
| Resolve and failures | Preserve `RespuestaResolucionV2` and its five statuses (`resuelto`, `parcial`, `invalido`, `no_convergente`, `no_soportado`). Application-level rejection on the v2 endpoints remains HTTP 200 JSON with the validation envelope and `resultados: null`. Translate expected common admission/initialization failures explicitly; preserve ordinary transport/framework errors. `/modelo` retains its own HTTP contract. Never convert an unexpected programming error into a successful or physically certified result. |
| Diagnostics | Preserve native diagnostic codes, severity/status, owner, source path and variable IDs for equivalent failures; English explanations may improve wording. Multiple independent problems remain visible. Do not reduce an incompatible-reference rejection to a generic convergence or missing-heat error. |
| Capabilities and methods | Retain seven package scopes, the section-12 size/evidence matrix, 3 volumes, 7 declared species per volume, 3 phases and the existing 1001 requested-sample limit. Preserve finite-search caveats. V2 accepts `null`/`rk45` only; BDF on common routes is not permission to broaden v2. Reject `euler_implicito` explicitly, without aliasing it to BDF. Resolve any common method-advertisement discrepancy before switching consumers. |
| Shared science | Reuse the common thermodynamic layer and units service. Thermodynamic reference identifiers, package fingerprints, phase searches and certification thresholds are authoritative. Any needed change in Claude-owned files is a separately coordinated board item. NRTL, spatial work and unsupported physical regimes are not expanded by this migration. |

The primary workspace is Solve. Model supplies the versioned physical document; Transform supplies the selected supported formulation; Results receives the executed identities and certificates. Preserve `modeloId` normalization for equivalent v2 requests and the existing package fingerprints for diagram comparison. Numerical data, topology, assumptions, package or Transform-selection changes invalidate the corresponding compilation/run; display-only changes remain physically neutral. Preserve the existing client abort handling, stale-response rejection, result signatures, charts and exports. Client cancellation must not be presented as server-side job cancellation, which remains separate work.

### Admission and initialization gate (step b)

`PaqueteV2.datosPuros` must reach the shared thermodynamic layer unchanged. Its substitutions participate in the shared package fingerprint and, in step (c), `procedenciaModelo.huella`; diagram comparison and invalidation must use that fingerprint. The initializer uses existing certified TP/TV/UV/UP package operations, including prescribed-pressure U, without a second thermodynamic root finder in the adapter.

Capabilities retain `disponible`/`motivo` and the water-audit gate (which can empty `paquetes`), `combinaciones` with evidence IDs, `pares`, `coberturaGrupos`, `dominio`, `limites`, `corrientes.entrePaquetes`/`inversion`, `segundaLey`, `integradores` and `noSoportado`. Their scientific scopes come from the shared layer. The adapter may advertise second-law/aggregate certification only after step (c) delivers and verifies it; step (b) is not permission to copy unsupported capability claims. Existing v2 capabilities remain unchanged during migration.

Before any routing change, match the native validation catalog and initialization for all archived requests and generated negative controls. This includes reference compatibility for **material** transfers, UP initialization from prescribed pressure and initial U, rigid/pressure boundary restrictions, units and data completeness, donor and reversal rules, extraction ambiguity, phase policies, size limits and unsupported combinations. Use shared Python initialization; the adapter must not retain a private thermodynamic initialization path. Include the newly recorded F9-R7 controls: dimensional validation by datum role (heat cannot be temperature; molar flow cannot be mass flow), duplicate CAS identities, self-loop topology, and explicit extraction rules for either possible donor. The pure-species bubble-edge closure finding remains Claude-owned and must be coordinated through the board before claiming initialization parity.

Two distinct reference cases are mandatory: `f25b` rejects the IAPWS-to-mixture material stream with `MOTOR_ENS_REFERENCIAS_INCOMPATIBLES`; `f25c` admits heat conductance between the two packages without moving material. Preserve the archived missing-parameter, missing-UNIFAC-assignment, missing-heat and missing-extraction diagnostics even when their structural count is `listo`. The open-boundary draft has no archived response and is an explicit unsupported negative control, not an expansion of admitted physics. Step (d) must map its strict-reader `ErrorModelo` (`frontera.tipo: rigida_con_presion`) to the native five-code rejection: `MOTOR_ENS_DONANTE_PENDIENTE`, `MOTOR_ENS_FRONTERA`, `MOTOR_ENS_INICIAL`, `MOTOR_ENS_MATERIA` and `MOTOR_ENS_MODELO`; do not parse exception prose or report generic convergence. Present step-(b) evidence and stop before results work.

### Diagnostic and status disposition (V2C-1)

All native wire codes below are preserved. **Mapped** means the adapter translates the named common diagnostic or typed outcome back to that native code, retaining source ownership/path/IDs and native severity; it must not parse English exception text. **Preserved** means the v2 envelope reader or the existing shared journal/package operation remains authoritative. **Deferred c** identifies publication/runtime outcomes whose translation belongs to step (c), not an admission implementation claim. No native diagnostic is declared unreachable merely because the 25-request archive does not exercise it. This table covers the 61 code literals/family prefixes in `backend/motor_ensamblaje_v2.py`; dynamically supplied package and data codes follow it.

| Native code(s) | Disposition and common source |
|---|---|
| `MOTOR_ENS_CAMPO_NO_ADMITIDO`, `MOTOR_ENS_FALTA`, `MOTOR_ENS_FORMA` | Preserved by strict envelope/schema reading; total-form rejection also maps `formulation_forma`. |
| `MOTOR_ENS_REVISION_RETIRADA` | Preserved at the revision discriminator before conversion. |
| `MOTOR_ENS_CATALOGO` | Mapped from reader references, `empty_components` or `invalid_stream_components`. |
| `MOTOR_ENS_COMPONENTES`, `MOTOR_ENS_VOLUMENES` | Mapped from `invalid_component_count`, `invalid_network_size`; retain invalid-empty versus unsupported-size severity. |
| `MOTOR_ENS_IDENTIDAD`, `MOTOR_ENS_IDENTIDAD_DUPLICADA`, `MOTOR_ENS_IDENTIDAD_NO_VERIFICABLE`, `MOTOR_ENS_CAS_INVALIDO` | Mapped from `missing_chemical_identity`, `duplicate_chemical_identity`, `unsupported_chemical_identity`, `invalid_chemical_identity`, respectively. |
| `MOTOR_ENS_MASA_MOLAR`, `MOTOR_ENS_MASA_MOLAR_CONTRADICTORIA` | Mapped from `invalid_molar_mass`, `inconsistent_molar_mass`. |
| `MOTOR_ENS_PAQUETE`, `MOTOR_ENS_MODELO`, `MOTOR_ENS_PAQUETE_NO_APLICABLE` | Preserve reader/package distinction; map `unsupported_package` using its native reason, distinguishing missing package/version from an inapplicable species/package combination. |
| `MOTOR_ENS_ESTUDIO`, `MOTOR_ENS_METODO` | Mapped from study-reader errors, `missing_study`, `invalid_samples`, `invalid_tolerance`, `unsupported_method`; the v2 front door still rejects BDF even though common Solve supports it. |
| `MOTOR_ENS_BALANCES`, `MOTOR_ENS_ESTACIONARIO`, `MOTOR_ENS_FUENTES` | Mapped from `formulation_balances`, `formulation_estacionario`, `formulation_fuentes`. |
| `MOTOR_ENS_DOS_CIERRES`, `MOTOR_ENS_DENSIDAD`, `MOTOR_ENS_TERMINOS` | Mapped from `formulation_dos_cierres`, `formulation_densidad`, `formulation_terminos`; conflicting declarations must not disappear during conversion. |
| `MOTOR_ENS_MATERIAL_REMAINDER`, `MOTOR_ENS_MATERIAL_TRANSPORT` | Mapped from `formulation_material_remainder`, `formulation_material_transport`. |
| `MOTOR_ENS_POLITICA_INVALIDA`, `MOTOR_ENS_POLITICA` | Preserve policy syntax errors; map `formulation_politica` for conflicting assumptions. |
| `MOTOR_ENS_FRONTERA`, `MOTOR_ENS_PRESION_PRESCRITA` | Mapped from `unsupported_boundary`, `formulation_frontera`, `formulation_presion_prescrita`. |
| `MOTOR_ENS_MECANICA`, `MOTOR_ENS_SOBREDETERMINADO` | Preserve absent mechanical relation versus extra rigid-pressure constraint at conversion; common path rejects both unsupported boundary cases. |
| `MOTOR_ENS_BASE`, `MOTOR_ENS_INICIAL`, `MOTOR_ENS_INICIAL_VACIO` | Preserve base-reader rejection; map missing/invalid inventory and energy data, and distinguish zero total inventory as `INICIAL_VACIO`. |
| `MOTOR_ENS_INICIAL_` | Preserve the shared closure reason suffix; map `initialization_<reason>` and its `initializationStatus`. |
| `MOTOR_ENS_TOPOLOGIA`, `MOTOR_ENS_SELECTIVO`, `MOTOR_ENS_MATERIA` | Mapped from `invalid_topology`, `unsupported_stream`, `mixed_flow_signs` or stream-mode/base reader errors. |
| `MOTOR_ENS_REFERENCIAS_INCOMPATIBLES` | Mapped from `incompatible_references`; only material transport requires matching thermodynamic references. |
| `MOTOR_ENS_COMPOSICION_SOBREESPECIFICADA` | Mapped from `overspecified_composition`. |
| `MOTOR_ENS_DONANTE`, `MOTOR_ENS_DONANTE_PENDIENTE` | Mapped from `invalid_external_state`, `missing_external_state`. |
| `MOTOR_ENS_COMPOSICION_EXTERIOR`, `MOTOR_ENS_P_DUPLICADA` | Mapped from `missing_external_composition`/`invalid_composition`, `conflicting_pressure`. |
| `MOTOR_ENS_EXTRACCION` | Mapped from `missing_extraction`/`invalid_extraction`; a monophase policy supplies the sole-phase donor, otherwise extraction must be explicit for every possible donor. |
| `MOTOR_ENS_LEY_CALOR`, `MOTOR_ENS_Q_ADIABATICO`, `MOTOR_ENS_Q_PENDIENTE` | Preserve heat-law reader rejection; map `conflicting_heat`, `missing_heat`. |
| `MOTOR_ENS_FUERA_DE_MAGNITUD` | Mapped from `invalid_physical_value`, `invalid_inventory`, `invalid_horizon`, with the consuming role's source location. |
| `MOTOR_ENS_EQUATION_WORKBENCH`, `MOTOR_ENS_ENERGY_JOURNAL`, `MOTOR_ENS_MATERIAL_JOURNAL`, `MOTOR_ENS_MOMENTUM_JOURNAL`, `MOTOR_ENS_THERMODYNAMIC_JOURNAL` | Preserve failures from the existing shared readers/replay validators; never replace a failed recorded deduction with legacy equations. |
| `MOTOR_ENS_INVENTORY_CONSTRAINT`, `MOTOR_ENS_HYDRAULIC_ROUTE` | Preserve route/scope rejection: a v2 equilibrium request must not silently execute a different physical formulation. |
| `MOTOR_ENS_NO_CONVERGENTE`, `MOTOR_ENS_DETENIDO_` | Deferred c: map integrator failure or typed `Detencion` reason, preserving runtime suffixes and certified prefix. |
| `MOTOR_ENS_MUESTRA_NO_CERTIFICADA`, `MOTOR_ENS_CERTIFICACION_NO_CUMPLE` | Deferred c: preserve unavailable sample versus evaluated physical failure, including first failure and last certified sample. |

The reused datum-reader codes `MOTOR_ENS_REFERENCIA`, `MOTOR_ENS_DATO_FORMA`, `MOTOR_ENS_MAGNITUD`, `MOTOR_ENS_FUNCION_DATO` remain structural/role errors; `MOTOR_ENS_DATO_PENDIENTE`, `MOTOR_ENS_UNIDAD`, `MOTOR_ENS_DEBE_SER_CONSTANTE`, `MOTOR_ENS_EXPRESION` and `MOTOR_ENS_NO_SUAVE` map from `missing_data`, `incompatible_dimension`, `time_dependent_initial_data`, `invalid_data` and `nonsmooth_boundary`. Preserve package-generated `PARAMETRO_AUSENTE`, `UNIFAC_ASIGNACION_AUSENTE`, group/interaction and `SUSTITUCION_*` suffixes from their typed causes; never hide them behind generic convergence. The common diagnostic carries `nativeCode` where available; the adapter fills envelope ownership/status and reader distinctions in step (d).

| Common outcome | Required v2 resolve status |
|---|---|
| Admission missing/invalid/conflicting data, or incompatible/pending initialization | `invalido`, null results. |
| Any unsupported scope/package/method or unsupported initialization | `no_soportado`, null results; preserves native precedence over invalid data. |
| Full numerical completion with published results | `resuelto`; physical `no_cumple` or `no_evaluable` must still be explicit. |
| Typed stop or publication failure after a certified prefix | `parcial`, only the certified prefix. |
| Numerical/closure failure without a publishable prefix | `no_convergente`, null results. |

Initialization maps certified closure to `compatible`, missing data or saturation underdetermination to `pendiente`, unsupported/critical-region closure to `no_soportada`, and invalid inventory, policy or other closure failure to `incompatible`. Aggregate precedence is `incompatible`, then `no_soportada`, then `pendiente`, otherwise `compatible`; no attempted states means `pendiente`. These are four initialization states, separate from five resolve statuses and from structural `recuento.estado`.

### Results and certification gate (step c)

**Science placement (V2C-5).** Reuse or move the existing operations through a coordinated Claude claim: `clasificar_evento`, `firma`, `margenes` and `muestras` in `core/ensamblaje_red.py`; `potenciales`, `evaluacion_volumen` (including its water certification dependency), `_seguir_ids` and `_certificacion` in `backend/motor_ensamblaje_v2.py`. Do not duplicate their science in the adapter or compiler. Chemical potentials and G/A/S continue to come from the shared thermodynamic state. A move from Claude-owned files requires board coordination before editing.

**Identity aliases (V2C-6).** The adapter publishes v2 `VariableV2`/`EcuacionV2` IDs as aliases of common physical quantities and equations. Apply one explicit alias map to series `variableId`, residual `ecuacionId`, certification `referencias` and `catalogoSeries.variableEnsamblajeId`. Preserve v2 consumers without claiming that a converted equation catalog is a recorded Model deduction.

The adapter must populate the existing result fields from shared Python calculations: n, U/H, T/P/V, mass, entropy, boundary work, signed stream molar flow, heat flow and network entropy generation; units and catalog roles; certified states and chemical potentials; residuals, second law, aggregate certification and package provenance. Preserve extensive G/A/S units and null chemical potentials for absent species. Auxiliary integrals remain diagnostics, not additional physical degrees of freedom.

Preserve phase identity across samples and the appearance, disappearance, substitution and supercritical-denomination event distinctions, with before/after phase IDs. Events require certified event-side evidence consistent with the located transition; an unavailable probe must not invent an event. Requested samples, event samples and final points must be sorted and deduplicated, with all published series/states aligned. Sampling-count differences are acceptable only when explained by event replacement/deduplication and tested without losing a requested point or transition; identical adaptive steps are not required.

A closure/certification exception during sample publication publishes only the preceding certified prefix, with `MOTOR_ENS_MUESTRA_NO_CERTIFICADA` and the corresponding partial/failure status. No valid prefix means no invented result. Distinguish that truncation from a calculated conservation, constitutive or second-law violation: retain the evaluated evidence, set the relevant `no_cumple`, and publish its first failing sample and `ultimaMuestraCertificada`. Numerical `resuelto` never implies physical `cumple`. Missing boundary temperature keeps the second law `no_evaluable`. Preserve all four certification aspects and the actual published time scope. Present step-(c) evidence and stop before adapter parity work.

### Frozen comparison set and parity gate (step d)

**Adjunct negative/event manifest (V2C-4, required before step d).** The 25 archived requests do not establish substitution/supercritical-event or negative-certification parity. Freeze the relevant fixtures from `tests/test_thermodynamic_events.py`, `tests/validar_motor_consolidacion_v2.py` and `tests/test_transient_phase_window.py` with input/source digests and expected outcomes: `sustitucion_fase`, `cambio_denominacion`, physical `no_cumple`, second-law `no_evaluable`, and `MOTOR_ENS_MUESTRA_NO_CERTIFICADA`. Store that adjunct in the existing test inventory, not another product example library. This is a remaining step-(d) gate; no adjunct numerical parity is claimed in step (b).

The section-12 list is the complete baseline: **25 requests, 24 sibling responses**; the open-boundary draft has no sibling response. Do not regenerate these references to make the adapter pass. On 24 October the SHA-256 of the manifest is `0931e2c77e83011aead32888d78239fc08e66dabc8dad9cb9fa20a6ea1c9657d`. Reproduce it by selecting `docs/ejemplos/**/*-peticion.json` with top-level `revision == 2`, `volumenes` and `paquetes`, adding each existing sibling `*-respuesta.json`, sorting `[repository-relative POSIX path, SHA-256 of raw file bytes]` pairs, then hashing their UTF-8 JSON with `ensure_ascii=True` and separators `(',', ':')`. A changed reference requires explicit explanation and review, never automatic rebasing.

Run every row through the compatibility adapter: validation requests compare validation (including all diagnostics), supported resolution requests compare full trajectories, and the unsupported draft compares an explicit rejection. Negative cases are passing parity evidence only when rejected for the expected reasons. Compare by stable physical IDs and SI units, not array position or display names. Keep a per-request evidence row with input digest, admission/initialization, numerical and certification statuses, diagnostics, maximum series error, events, elapsed time and reader result. Extend the existing test inventory; do not publish another product example library.

Existing independent-reference thresholds remain binding: vertical-slice and UNIFAC trajectories/events, v1 water references, R5 narrow-window/stage-stop tests, work identities and second-law negative controls must still pass without relaxed tolerances. For series without an existing stricter oracle, require maximum absolute difference divided by `max(max(abs(reference)), 1e-300)` at most `1e-6`; an identically zero reference series must remain zero to its declared physical absolute tolerance, recorded before the adapter run. Event codes/order must agree; time error is at most `1e-6 s`, except the already documented UNIFAC network reference bound of `1e-6 * final_time`. Compare continuous values at shared requested times and compare event sides separately; never interpolate across a discontinuity to hide disagreement. Certificate residuals must satisfy their original thresholds, independently of trajectory agreement. A historical reference that fails a physical oracle is a finding for review, not permission to copy its defect.

Run the section-12 affected suites, strict TypeScript/runtime readers, HTTP tests and network lifecycle/browser checks. Preserve M1 A/B/C counts and hashes. Apply the accepted R6 closure budgets (seeded-step median 0.05 s, TP 1 s, PH 2 s, UV 5 s on the benchmark machine) with unchanged certification; record complete adapter-run timings separately because network volume scaling has no accepted budget yet. Present step-(d) evidence and stop before requesting independent review.

**Step (d) adapter implementation, 27 October 2026.** `backend/v2_compatibility.py` retains the existing strict v2 envelope validator, catalogs, normalized model identity, static wire guards and initialization packaging. Both routes now use `core/compilador/initialization.py` to select the shared certified TP/TV/UV/UP operation; every wire-admitted request additionally passes common admission and initialization. The adapter calls only common `resolver` for integration. Reusing native wire validation is transitional compatibility code, not retirement of that module or a second solver. An explicit fault-injection test makes calls to either native `resolver_v2` or `ensamblaje_red.integrar` fail. No production route changed.

One identity map covers quantities, equations, series catalogs and certificate references. Common `politica_incumplida` maps to native `MOTOR_ENS_DETENIDO_CAMBIO_FASE_PROHIBIDO`; the v2 envelope publishes the located physical transition and omits the duplicate generic policy event at the same time. Datum diagnostics retain the request's source owner/path and variable ID. Typed common initialization failures also replace the preliminary compatible wire state with `pendiente`, `incompatible` or `no_soportada`, clear the failed volume's thermodynamic evidence, preserve aggregate precedence and select the corresponding diagnostic/resolve severity. Three injected typed-failure controls failed before this mapping and pass afterwards; native initialization is never used as a fallback for a failed common initializer. The strict v2 reader retains all five open-boundary draft codes before common conversion. Method text reports the actual common RK45 engine; v2 BDF and implicit Euler remain rejected. Whole-horizon bounds intentionally reject declared singular data earlier than native grid screening; this is a structured admission difference, not an unnoticed runtime fallback.

The archive matrix exposed a publication-bridge defect: raw `datosPuros` substitutions were passed to a package constructor that expects parsed SI values. The bridge now calls the existing catalog substitution parser. The unchanged ethanol liquid-volume-substitution request failed before the fix and passes afterwards, including trajectory, units and fingerprint. No thermodynamic file or scientific threshold changed.

The supplementary manifest `tests/reference_data/v2-parity-adjunct.json` freezes seven request bodies, their input hashes and hashes of the existing event/consolidation/window regression sources. Adapter controls verify supercritical naming, the narrow phase window against independent PH/first-law boundaries, negative second-law evidence, missing boundary temperature, injected work corruption, the small-scale work control and prefix-only publication. The LL-to-LV substitution control is the existing shared typed classifier test; it does not claim an additional integrated substitution trajectory. All seven adapter controls pass. The native small-scale control still gives approximately 2.85% work drift and `resuelto` / `no_cumple`; it is not corrected by changing tolerances.

`tests/test_v2_compatibility.py` compares all 25 immutable requests with fresh native runs, while retaining historical response comparisons. It checks diagnostic code/status/source/IDs, catalogs, initialization, series IDs and SI units, requested/event samples, physical phase IDs and times, G/A/S and chemical potentials (including null absent-species values), provenance fingerprints, residual thresholds, all certificate aspects and failing-sample indices. Limits remain relative 1e-6 for nonzero series and potentials, 1e-6 s for events except 1e-6 times the horizon for the established five-species UNIFAC control. The predeclared zero-series absolute floors are recorded in `tests/v2_parity_cases.py`; no near-zero exception was added. Each evidence row in ignored `.tmp/codex-v2-parity/` records actual source/input digests, timings, native and adapter outputs, historical comparisons and failures. Cache reuse requires an exact execution-source digest; read-only comparison of existing rows does not relabel their execution source. The final integration fixes affect SI substitutions and wire policy/source mapping, each rerun explicitly; older unaffected rows retain their original source digest for review.

**Open strict-parity finding for Claude:** the decantador's native `red.Sgen` is numerical cancellation noise, with maximum magnitude 5.151434834260726e-14 J/K. The adapter differs by 4.618527782440651e-14 J/K. Both physical certificates are `cumple` against the existing 1.2030353996806984e-5 J/K second-law threshold, but the contract's nonzero-series relative limit is only 5.151434834260726e-20 J/K. The matrix deliberately reports failure. Do not clamp entropy, change a solver tolerance or silently treat this near-zero reference as exactly zero. Independent review must resolve the comparison contract before retirement can pass.

**Open event-parity finding for Claude:** the heteroazeotropic water/butanol request completes on both paths with physical `cumple`, identical event codes/phase identities and maximum series difference 5.724e-9. One liquid disappearance is located at 479.75847727394023 s by the adapter and 479.75847847092314 s by fresh native v2: 1.1969829074587324e-6 s, above the unchanged 1e-6 s contract. Potential differences remain below 3.069e-8. The test records the timing failure separately while comparing the corresponding event sides and all requested samples; it does not interpolate across the transition or relax the threshold. This remains a failed retirement gate pending independent review.

**Historical-reference findings retained unchanged:** the monophase UNIFAC stop has `volumen.A.W = [0, 0]` on both current paths, while the frozen response has a final 7.632671373952571e-8 J. The unchanged relative rule therefore fails against that nonzero historical noise, even though both current physical certificates pass. The five-species network's `calor.c.Q` differs from the frozen response by 8.771845526212019e-5 W, or 1.1695794034949358e-5 relative, above 1e-6. Fresh native v2 also differs from that same historical heat series by 1.1712521453925244e-5 relative; adapter versus fresh native is within 3.690e-8 across all series. Thus this is historical baseline drift shared by the current native path, not a hidden adapter-only deviation. Exact attribution to intervening native/thermodynamic changes needs independent review; the archive was not regenerated. Historical and current event times differ by 9.38e-5 s, within the predeclared five-species event bound of 2e-4 s. These are additional failing historical gates, not approved tolerance exceptions.

**Step-(e) review requested from Claude, 27 October 2026.** Independently rerun the final source, whole-horizon negative controls, adapter source/status mappings, all 25 requests and adjunct physical controls. Review the four strict findings above and the eight-species performance finding before claiming parity. The production routes, native solver and immutable archives remain intact. Ordinary `python tests/test_v2_compatibility.py` recomputes any evidence whose execution-source digest differs. `V2_PARITY_REPLAY=1` with the `CompatibilityTests.test_all_25_archives` selection rechecks the recorded execution evidence and explicitly prints each source digest and whether it matches current code; it is not a fresh final-source run. The final replay reports four failing rows. Native/component units, catalogs, initialization, certificate states and aliases agree across all 25; the three historical-series failures and the event-time failure remain visible. No deletion approval is implied.

**Current regression evidence (27 October):** common admission 12 tests (including both common HTTP endpoints); shared initialization 6; common Results 9 without expected failures; UNIFAC layer 82 checks (including the structured phase-identity parser); isolated adapter HTTP/units/methods/no-fallback/draft/initialization-state checks 4; all seven adjunct controls; vertical slice 71 with `--no-write`; native consolidation 128; explicit compiler 27; retired v1 4; common phase windows 4 (RK45/BDF, coarse and finer sampling); stage stops 4; stability margins 4; M1 U1 12 reference/refinement trajectories; frontend network integration 334, certification warning 40 and derived lifecycle 78; typed archived v2 reader 10 pairs/60 states/12 point examples; TypeScript, scoped Checklist ESLint and 1,391 physical-journal checks. The fresh-output TypeScript reader passes all 25 adapter responses and seven adjunct responses (197 volume states), and rejects 19 deliberately misaligned series. The full UNIFAC validator passes 82 checks; the long five-species adapter run completes with 6 samples, relative series difference 3.690e-8 against fresh native and potential difference 6.118e-9. Its native/adapter wall times are 615.24/2392.18 s; heteroazeotrope native/adapter times are 144.63/1919.75 s. Timings were measured during concurrent test work.

**Performance scope:** the species benchmark was rerun with three repeats and unchanged tolerances into ignored `.tmp/codex-v2-parity/benchmark/`. For the measured 2-7 species (the v2 limit), valid warm medians are at most 0.0406 s seeded PH, 0.0553 s TP, 0.4071 s PH and 0.9326 s UV; the two binary UV liquid-volume rejections remain rejections, not speed successes. The eight-species seeded measurements under concurrent test load exceed 0.05 s (approximately 0.07 s); a focused repeat gives 0.0637 s original and 0.0594 s Dortmund. This remains a performance finding for Claude, outside the v2 seven-species limit; this run is not a fresh acceptance of all R6 scopes. Full adapter timing includes duplicated certification/accounting and cold event probes; it is substantially slower than native v2. Network-wide performance has no accepted numeric budget, and the timing difference remains visible for independent review rather than hidden by fallback or relaxed certification.

**Completed per-request matrix: 25/25 executed, 23/25 fresh-native comparisons pass, 21/25 pass both fresh and historical gates.** Errors use the declared normalization above. A rejection passes only when expected codes and source identities agree; historical timing and structural differences remain recorded in each evidence row.

| Request ID | Numerical status | Physical certificate | Maximum fresh series difference | Fresh native | Historical series |
|---|---|---|---:|---|---|
| demo-heteroazeotropo | resuelto | cumple | 5.72e-09 | finding | pass |
| demo-rayleigh | resuelto | cumple | 1.77e-10 | pass | pass |
| f26 | resuelto | cumple | 4.52e-08 | pass | pass |
| v2-acoplado | resuelto | cumple | 1.4e-07 | pass | pass |
| v2-calentamiento | resuelto | cumple | 4.24e-08 | pass | pass |
| n5-cal | resuelto | cumple | 1.89e-09 | pass | pass |
| n4-cal | resuelto | cumple | 6.81e-08 | pass | pass |
| v2-contacto | resuelto | cumple | 4.01e-08 | pass | pass |
| f25c | resuelto | cumple | 1.81e-07 | pass | pass |
| f25 | resuelto | cumple | 1.93e-07 | pass | pass |
| v2-decantador | resuelto | cumple | 0.897 | finding | finding |
| n5-red | resuelto | cumple | 8.6e-08 | pass | pass |
| f24 | resuelto | cumple | 9.27e-15 | pass | pass |
| u2-cal | resuelto | cumple | 1.71e-08 | pass | pass |
| u4-cal | resuelto | cumple | 2.35e-08 | pass | pass |
| d4-cal | resuelto | cumple | 1.55e-08 | pass | pass |
| l2-mez | resuelto | cumple | 1.66e-10 | pass | pass |
| u2-mono | parcial | cumple | 6.28e-10 | pass | finding |
| u5-red | resuelto | cumple | 3.69e-08 | pass | finding |
| v2-calor-pendiente | invalido | — | — | pass | pass |
| v2-decantador-ambiguo | invalido | — | — | pass | pass |
| n4-par | no_soportado | — | — | pass | pass |
| f25b | no_soportado | — | — | pass | pass |
| u4-asig | no_soportado | — | — | pass | pass |
| borrador-olla-abierta | no_soportado | — | — | pass | pass |

### Independent review and current evidence

Step (e) asks Claude to review the adapter and reproduce the parity matrix and physical negative controls independently. Code remains present until a separate user deletion approval and the required ownership coordination. A failed row keeps the migration open; there is no fallback or selective omission of difficult cases.

For step (a), source inspection covered all three routes, the published TypeScript types/readers, native initialization/publication/certification and all 25 archived request envelopes and 24 responses. `node tests/verificar_contrato_ensamblaje_v2.mjs` passes: **10 typed v2 request/response pairs, 60 volume states and 12 point examples**. This verifier covers two archive directories, not the entire 25-request matrix.

**Step (b) delivered for review, 24 October 2026.** `core/compilador/admission.py` supplies shared role-dimension, finite-data, inventory, horizon, topology, identity, package/reference, donor/reversal, extraction, physical-assumption and size checks. It reuses the strict common reader and shared units/packages; it does not call the v2 validator or solver. `SistemaCompilado.inicial` certifies initial TP/TV/UV and now UP states through existing package operations, and reports located initialization failures. Common compilation inspection advertises both actual RK45/BDF methods; v2 remains RK45-only by contract. `_Dato` validates each consuming role even when an ID is shared, so a valid cache entry cannot conceal a conflicting role dimension. `/modelo/resolver` and `/modelo/compilation` return structured 422 rejections for the R7 malformed requests.

Evidence: `tests/test_common_admission.py` (7 tests, including both HTTP endpoints and unit-equivalent independent RHS comparison); `tests/test_v2_initialization.py` (6 tests). The unchanged compiler fails 16 R7 admission assertions, four physical-assumption assertions and all four new UP controls; the repaired path passes. All **25 archived requests** are evaluated: **19 initialize compatibly, six reject** (five archived admission negatives plus the unsupported open-boundary draft). Initial n/T/P/V/U/H match archived values within relative 1e-7; the manifest digest above is unchanged. The simulated missing-UNIFAC-assignment archive is reproduced with the same scoped missing-assignment injection as its generator, not by pretending the otherwise complete request is intrinsically invalid. The monophase `u2-mono` case initializes compatibly; its later phase-policy stop belongs to runtime parity. Pure-data substitution changes both the closure fingerprint and the physical initial state. Separate TP-to-UP controls cover water and ideal benzene/toluene at 101325/200000 Pa, and an independent signed-flow balance checks reversal.

Regression checks: workspace handoffs (8), retired v1 assembly (4, including nine parity cases), hydraulics (14), energy derivation (10), common phase windows (4), stability margins (4), stage stops (2), explicit compiler (27 checks), and frozen M1 U1 acceptance (12 reference/refinement runs). TypeScript, scoped Checklist ESLint, the v2 contract reader (10 pairs/60 states/12 point examples), and 1,391 physical-journal checks also pass. Frozen A/B/C counts and hashes remain unchanged. This establishes the step-(b) admission/initialization scope, not full adapter response/certification parity. No production v2 route, thermodynamics file or v2 solver behavior was changed. Stop here for review before step (c). Claude separately delivered and released the pure-component bracket repair during this work; further thermodynamic changes still require ownership coordination.


**Step (c) implementation, 24 October 2026; independently reviewed by Claude, closure verified on 27 October.** `core/compilador/network_results.py` retains common RK45/BDF integration and the compiled physical RHS (including lowered energy journals). It reuses the existing network's auxiliary accounting for external material/energy, boundary work, V dP and entropy. Auxiliary counts are disclosed in compilation inspection and are not physical degrees of freedom. The former native publication block is shared through `backend/assembly_results.py`; existing phase tracking, potentials, package fingerprints, residual definitions, second-law and aggregate certification operations are called, not reimplemented. Native v2 continues to use its own integrator and this same publisher. No production route was switched and no solver was retired. Absolute tolerances and scientific certification thresholds are unchanged.

Common results retain all shared quantities/catalog roles and per-sample states in `procedencia.equilibrium`, expose `physicalCertification` separately from numerical completion, and retain publication diagnostics. Unavailable publication samples truncate every output array and events to the certified prefix; evaluated conservation/work/second-law violations keep their evidence and `no_cumple`. Missing boundary temperature remains `no_evaluable`. Event classification uses typed event-side states, not candidate names; phase identities and event-time replacement/deduplication reuse the native operations. The v2 wire alias map remains a step-(d) deliverable. Reusing auxiliary accounting adds closure work; these tests do not establish an adapter performance budget or R6 acceptance.

**R7 whole-horizon datum admission, 27 October 2026.** The previous 401-point screen is replaced by conservative interval evaluation of the expression AST on the complete SI-time horizon. Shared role dimensions are checked independently of time; interval operations check real finite domain and required positivity after the SI scale/offset conversion. Subdivision reduces interval dependency, with a finite depth/work budget; unsupported or unresolved bounds reject with located `unbounded_time_data` / `MOTOR_ENS_EXPRESION`, never admission by sampling. Concrete sign/domain witnesses retain `MOTOR_ENS_FUERA_DE_MAGNITUD` or `MOTOR_ENS_EXPRESION`. The linear pressure reaches zero at 50 s by hand; the between-grid pressure dip at 0.125 s reaches -98675 Pa, `sqrt(25-t)` leaves its real domain after 25 s, and `1/(t-0.125)` has an interior pole. All three new controls fail against the preceding admission implementation. Pressure derivatives required by boundary work are also enclosed: `101325+sqrt(t)` has a singular derivative at t=0, and its new regression fails before the check. Bounded `101325+10000*sin(t)` pressure and signed `100*cos(t)` heat remain admissible. Under the latest fail-closed user requirement, a declared heat singularity at 50 s is now rejected at admission rather than deferred to a partial run; this is an explicit compatibility difference. Flow reversal without the other donor's extraction remains rejected. Unexpected-in-advance thermodynamic failures retain a structured certified prefix; initial-probe failures remain located rejections. No solver margin, seed, retry or tolerance rule was changed.

**Supercritical-water control closed, 27 October 2026.** Claude's `328845d` / `52e3bda` fixes make one kg of water at 30 MPa and 630 K heated at 2 kW complete with physical `cumple` and `cambio_denominacion` at 64.4210760097 s. The common regression now passes without an expected-failure marker and checks H = H0 + Q t and monotone temperature. No compiler fallback, seeding or tolerance workaround was added. The six rigid-mixture controls remain unblocked by Claude's accepted TV repair. `validar_capa_unifac.py` now identifies the appearing phase through structured before/after phase IDs and certified composition, instead of parsing the last word of an event description.

The existing small-scale native control still measures about 2.85% boundary-work drift at extensive scale 1e-6 and reports numerical `resuelto` with physical `no_cumple`. Common publication is checked against n = n0 - F t, constant signed flow/heat and W = P(V - V0); injected work corruption and negative second-law generation must retain `no_cumple` and located diagnostics. No tolerance was changed to pass these controls. The 25-request/24-response manifest remains unchanged; frozen archives were not regenerated. The vertical-slice validator now checks structured rejection codes instead of historical Spanish substrings and accepts `--no-write` for verification without replacing the archived result.

Negative controls: the HEAD compiler completes the nominal case without the required physical certificate or work series; the new publication assertions therefore fail on it. The HEAD compiler also raises an unstructured water `FueraDeAlcance` at 647.087 K on the supercritical request, confirming that the subsequently fixed water finding predated this publication bridge. A local copy of admission restored to t=0-only range checking admits the pressure that reaches zero at 50 s; current admission rejects it with the native range code.

Historical verification on 24 October: admission 8; initialization 6; common Results 8 plus the then-open water control; margins 4; stage stops 4; workspace handoffs 8; retired v1 4; common phase windows 4; thermodynamic events 6; native transient windows 2; consolidation 128; common result reader 34; explicit compiler 27; vertical slice 71 without writes; frozen M1 12 trajectories; TypeScript, scoped ESLint, certificate readers and 1,391 physical-journal checks. The water control is now closed; current verification is recorded below.

**Step-(e) independent review (Claude, 27 October 2026).** Fresh final-source run of all 25 requests into an independent evidence directory outside `.tmp/codex-v2-parity/` (no cache reuse; `CompatibilityTests.test_all_25_archives` with `EVIDENCE` redirected, five shards): **25/25 executed, 21/25 rows pass, the same four rows fail with the same numbers** (decanter `red.Sgen` 4.618527782440651e-14 J/K; `u2-mono` historical `volumen.A.W` 7.632671373952571e-08 J; `u5-red` historical `calor.c.Q` 8.784e-05 W; heteroazeotrope event 1.1969829074587324e-6 s). Adapter versus fresh native stays at or below 1.93e-7 relative on every resolved row. The other `test_v2_compatibility.py` tests (adjunct controls, HTTP/units, typed initialization rejection, no native fallback/aliases, open-boundary codes) pass 5/5; `test_common_admission.py` plus `test_v2_initialization.py` 18/18; `test_common_network_results.py` 9/9; `tests/validar_capa_unifac.py` 82/82 checks (its own five-species run took 2644.8 s under load). Adapter wall time remains 2.5-13 times native (heteroazeotrope 1925/149 s, five-species 2612/624 s, under five concurrent shards); this is recorded, not accepted as a budget.

*Negative control (R7 time-dependent data).* In a clean `HEAD` worktree with the current `tests/test_common_admission.py` copied in, the five horizon tests fail (`NoSoportado not raised` for P = 101325 - 2026.5 t reaching zero at 50 s, the between-grid dip, `sqrt(25-t)`, `1/(t-0.125)`, the unbounded `2^sin(t)` enclosure and `101325+sqrt(t)`), while bounded `101325+10000 sin(t)` / `100 cos(t)` is admitted on both. The worktree was removed.

*Adjudication of the four open rows, each against a reference independent of the engine residuals:*

1. **Heteroazeotrope event (real defect in native v2, not in the adapter; tolerance correct).** The volume is closed, at prescribed constant P, with imposed Q = 100 W, so H(t) = H0 + Q t exactly. Bisecting the package's PH phase set on H alone (no integrator, bracket below 1e-11 s) gives the three transition times t* = 70.48187264652807, **479.75847727360076** and 498.94412891556277 s. Adapter errors: 2.4e-11, **3.4e-10** and 1.5e-10 s. Fresh native v2 errors: 1.07e-8, **1.197e-6** and 1.4e-9 s, always late. The 1e-6 s contract is therefore achievable and is kept; the failure belongs to the reference path (`core/ensamblaje_red.py` event location, owner Claude). The adapter passes against the independent reference.
2. **Decanter `red.Sgen` (tolerance wrongly scaled for an analytically zero series).** Adiabatic withdrawal of one equilibrium liquid phase at its own state at constant T and P is reversible: Sgen = 0 exactly. Both paths keep T = 300 K to one ulp; |Sgen| <= 5.2e-14 J/K is a few ulp of the subtracted entropy terms (|S| about 108-120 J/K, eps |S| about 2.7e-14 J/K). Applying a 1e-6 relative limit to roundoff gives 5e-20 J/K, which no floating-point path can meet.
3. **`u2-mono` historical work (archive artifact).** The package's liquid volume is temperature-independent: TP states at 300, 330 and 353 K give V = 3.837106239303157e-05 m3 exactly, and P is constant, so W = -P(V - V0) = 0 exactly. Both current paths publish W = [0, 0]. The frozen 7.632671373952571e-08 J is not even consistent with its own volume series (P dV = 7.31e-7 J); it is historical noise.
4. **`u5-red` historical heat (archive drift amplified by a difference quantity; not an adapter defect).** Q = G (T_A - T_B) with G = 0.5 W/K holds exactly (difference 0.0) in both the frozen and the current trajectories. Every state series of the frozen response agrees with fresh native within 4.7e-7 relative (T_A 2.2e-7, T_B 3.1e-7), inside the binding 1e-6 rule, and t=0 values agree exactly (no thermodynamic-data change). The heat difference is G times a 1.75e-4 K temperature difference; normalizing it by max|Q| = 7.5 W instead of the operand temperatures (about 330 K) tightens the effective limit about 44-fold.

**Verdict.** Step (c): **accepted**. R7 whole-horizon time-dependent admission: **accepted** (fails on HEAD, passes now, bounded controls admitted). Step (d): **parity not yet passed; no adapter defect found.** Remaining repairs, owner Codex in `tests/v2_parity_cases.py` / `tests/test_v2_compatibility.py`, each predeclared and rerun on all 25 rows: (R1) a series whose independent physical value is zero compares absolutely against its already predeclared `zero_tolerance` floor (1e-9 J/K for entropy, `atol.energia` = 1e-6 J for energy), that is |d| <= max(1e-6 max|ref|, floor); 1e-9 J/K is four decades below the 1.2e-5 J/K second-law threshold and five above roundoff, and it must not be applied to a series with a nonzero physical reference; (R2) a conductance heat series compares with the propagated operand limit |dQ| <= G 1e-6 (max|T_A| + max|T_B|) (3.3e-4 W here; observed 8.78e-5 W), recorded per law, not per case; (R3) the heteroazeotrope event row compares both paths with the recorded integrator-free t* above under the unchanged 1e-6 s limit, and records native v2's 1.197e-6 s lateness as a native finding instead of an adapter failure. Native v2 event-location bias is Claude's finding in `core/ensamblaje_red.py`; it is not repaired while v2 is scheduled for retirement unless the user decides otherwise. No route switch, archive regeneration or deletion is authorized by this verdict.

**Assigned comparison repairs (Codex, 28 October 2026; review requested).** R1 applies the existing absolute zero floor only to the two independently proved zero quantities above, tied to immutable request names under the unchanged manifest. It also checks each path against zero, not only the difference between paths; a nonzero control still receives the strict relative limit. R2 selects the conductance law, reads its G in SI and propagates the two reference-temperature limits; the five-species historical heat bound is 0.0003307452083321823 W. This rule is attached to the law, not to the five-species case. R3 retains all three integrator-free reference times and compares both paths against the unchanged 1e-6 s limit. The middle event has adapter error 3.3947e-10 s and native lateness 1.1973224e-6 s, retained under `nativeFindings`, not hidden as adapter success against an inaccurate reference. Every series limit/basis and independent event comparison is retained in the existing ignored evidence records.

Verification command: `V2_PARITY_REPLAY=1 python tests/test_v2_compatibility.py CompatibilityTests.test_all_25_archives` (PowerShell: set the environment variable first). All 25 existing trajectory records now pass fresh-native and historical comparisons, including events, certification, rejections and units. This reruns the comparison policy over exact frozen requests and recorded solver outputs; it does not claim a new final-source integration of all 25 requests. Source digests remain the original digests and `currentSourceMatches=false` stays visible. A redundant fresh full run was stopped after its adjunct controls and first archive; no new complete-run claim replaces Claude's independently recorded fresh 25-request run. The additional policy regression preserves strict relative checks for nonzero quantities and verifies the same conductance bound with G in W/K and kW/K. Initialization-wire rejection, no-native-fallback/aliases, open-boundary five-code mapping and isolated HTTP/unit tests pass. The seven physical adjunct controls also pass in a fresh run (143.788 s), including narrow phase windows, failed work/second-law evidence and publication-prefix truncation. The manifest remains 25 requests/24 responses with its original digest. No adapter, route, thermodynamic source, integration tolerance or archive was changed; no route switch or v2 deletion is authorized. Claude: review R1/R2/R3 and the replay evidence before closing step (d).

**Step-(d) final verdict (Claude, 28 October 2026): parity reached.** R1/R2/R3 match the 27 October adjudication: the zero floor applies only to the two physically proved zero series and each path is also checked against zero; the conductance limit is derived from the law and its SI G (0.0003307452083321823 W here); the heteroazeotrope compares the adapter with the recorded integrator-free t* under the unchanged 1e-6 s limit and stores native v2's 1.1973224e-6 s lateness in `nativeFindings`. A fresh final-source run of all 25 requests (new independent evidence directory, no cache, five shards) passes **25/25**, including events, certification, rejections, units and historical series; adapter wall times were 1103 s (heteroazeotrope) and 1878 s (five species) against native 138 s and 537 s. Steps (a)-(e) are complete. This verdict authorizes neither the route switch nor deleting v2: both still require a separate user approval and ownership coordination. Native v2's event-location lateness remains Claude's recorded finding in `core/ensamblaje_red.py`.


## 14. Native v2 deletion plan — awaiting user decision

**29 October 2026, read-only source audit; decision `dec-v2-native-retirement` is taken: deferred until Claude reviews the route switch in use.** Keep the native fallback and delete nothing. A later retirement requires a new user decision. The heading is retained for existing board links. This is a deletion plan, not permission to execute it. `dec-v2-route-switch` remains in force: HTTP uses the common adapter by default and native execution remains an explicit server fallback. Only this document and the board were edited for this audit. No source, test, example, dependency, running server or frozen output was changed; no commit or push. Sections 12 and 13 retain their dated historical evidence. This section is the current removal inventory.

Primary workspace: **Solve**, with Results publication and Model validation/catalog consumers. Inputs remain the same revision-2 requests, units, package fingerprints and recorded derivations. Outputs remain the same revision-2 validation/resolution envelopes, physical certificates and optional execution provenance. Preserve normalized model identity, stale-response rejection, abort handling, saved-result signatures and invalidation after data/physics/package/Transform changes. This plan adds no physical capability and changes neither M1-A/B/C nor the F3 second/third slices currently in review. Checklist capability status therefore stays unchanged. Unfinished prerequisites are shared-helper extraction, direct-Python caller migration, preservation of native negative controls, an explicit performance-budget verdict, independent review and the user's deletion decision. `core/ensamblaje_red.py` belongs to Claude; its extraction/removal requires Claude ownership coordination even after approval.

### Removal boundary: two files only after shared code has moved

A filename containing v2 is not evidence that it is disposable. The proposed final file deletions are **`backend/motor_ensamblaje_v2.py` and `core/ensamblaje_red.py`**, after the following retained symbols and callers have migrated. No whole test, example or frontend-reader file is proposed for deletion. The shared network equations and certificates are still live on the common path.

| Current owner | Delete after approval | Extract and retain before deleting the file |
|---|---|---|
| `backend/motor_ensamblaje_v2.py` | `resolver_v2`, including its native network construction, initial-state vector assembly, `er.integrar` invocation, failure wrapping and nested `rechazo`; `_funcion_molar` (no caller found). Remove obsolete imports once their retained consumers move. | Every other top-level function and constant, listed below. Validation, initialization, identity and physical publication are not native-only behavior. |
| `core/ensamblaje_red.py` (Claude) | `integrar` and all its local step/event/reintegration callbacks; `Tramo`; `Trayectoria` and `Trayectoria.y`; native-only event-step helpers `margenes`, `_margen_cae`, `_paso_por_margen`, `_prohibido`, `_codigo`; constants `RES_EVENTO`, `MARGEN_CAIDA`, `MARGEN_MIN`, `H_MARGEN_MIN`; its direct SciPy `RK45` import. First replace the test use of `Tramo`/`Trayectoria` with a simple trajectory fixture. | `VolumenSI`, `CorrienteRed`, `IntercambioRed`, `Red`; **all of `Sistema`** (`__init__`, `n_E`, `estado_vol`, `estados`, `_extraer`, `flujos`, `calores`, `__call__`, `_dVdt`); `firma`, `clasificar_evento`, `muestras`. Keep the accounting layout and exact event-time sampling semantics. Moving these is not permission to rewrite their science. |
| `backend/v2_dispatch.py` | The `native` branch in `_dispatch`, its native import and executor mapping, only after explicit fallback retirement. | `_dispatch`, `capabilities`, `validate`, `resolve` or equivalent thin common-only dispatch; provenance stamping and configuration validation. Keep absent/`common` behavior. A lingering `native` setting must fail explicitly with a retirement explanation, never silently run common. Preserve historical `native-v2` provenance in readers. |
| `backend/motor_ensamblaje.py` | Native imports inside `validar` and `resolver`; replace their revision-2 branch with the shared wire/common adapter interface. | The module itself: v1 retirement response, `_es_revision_2`, `capacidades`, `validar`, `resolver`, protocol helpers, units and point-evaluation support. Preserve `validar`'s tuple shape for existing Python callers and avoid recursion through the adapter. |

**Exhaustive retained symbol split from `backend/motor_ensamblaje_v2.py`:**

- Proposed `backend/assembly_capabilities_v2.py`: `REVISION`, `VOLUMENES_VERIFICADOS`, `COMPONENTES_VERIFICADOS`, `TAMANOS`, `EVIDENCIA_UNIFAC`, `_comb`, `_pares_nrtl`, `_pares_nrtl_sin_cerrojo`, `_cobertura_unifac`, `cobertura_unifac`, `capacidades_v2`. Preserve cache/lock behavior, species-size evidence, water gate, finite-search caveats, group coverage and package fingerprints. The names identify a proposed shared owner; no new file is created by this plan.
- Proposed `backend/assembly_protocol_v2.py`: `_comprobar_formulacion`, `validar_v2`, `_ensamblar`, `_canon`, `_modelo_id`, `_ids_fases`, `_inicializar`. Keep journals, all independently reported diagnostics, normalized identity, equation/variable catalogs and certified initialization. Keep `core/compilador/initialization.py:initialize_state`; the wire initialization packaging is not an alternative numerical solver.
- Existing `backend/assembly_results.py`: move in `potenciales`, `evaluacion_volumen`, `_procedencia`, `_DESCRIPCION_EVENTO`, `_certificacion`, `_seguir_ids`; retain `publish`. Import `REVISION` from the capability/contract owner, not the validator, so the validator may reuse state packaging without an import cycle. Physical status, chemical potentials, stable IDs, entropy/work checks and partial certified prefixes must remain identical.
- Move the import-time `cantidad`/`conductancia` registrations in `v1.UNIDADES` and `v1.UNIDAD_SI` to explicit protocol-unit initialization in retained `backend/motor_ensamblaje.py`. Keep `_Diag`, `_Dato`, `_Lector`, `_emparejar`, `_canon`, `evaluar_certificado` and their transitive helpers there; `tests/validar_unidades.py` must no longer depend on importing a deleted module for side effects.
- Proposed `core/network_accounting.py` receives the retained network dataclasses, entire `Sistema`, `firma`, `clasificar_evento`, `muestras`. Both common publication and the temporary native path import it during extraction. Claude owns approval/review of the move from `core/ensamblaje_red.py`; no thermodynamic formula, phase policy or tolerance changes are bundled into retirement.

The standalone common solver, `core/dynamic_common.py` (`Funcion`, `Detencion`), `core/paquetes_volumen.py`, `core/expresiones_motor.py`, `core/unidades/`, `core/termodinamica/`, `core/mezclas.py`, UNIFAC, water, catalog and equilibrium-diagram science all stay. The retired v1 `core/ensamblaje_dinamico.py` is already absent; this is not another v1 deletion.

### Live dependency edges that block immediate deletion

| Consumer | Dependency observed on 29 October | Required migration |
|---|---|---|
| `backend/v2_compatibility.py` | `wire.validar_v2` in `validate`; `wire.capacidades_v2` in `capabilities`. `resolve` goes through `validate` then the common compiler. | Import the retained protocol/capability owners. Keep `_reject`, `_diagnostics`, `_aliases`, `_runtime_codes`, `validate`, `resolve`, `capabilities`; preserve HTTP 200 wire rejections and no fallback. |
| `core/compilador/network_results.py` | `network.VolumenSI`, `CorrienteRed`, `IntercambioRed`, `Red`, `Sistema`, `firma`, `clasificar_evento`. `NetworkExecution.rhs` calls `Sistema.__call__` for auxiliary rates, then replaces physical rates with compiled equations. `NetworkExecution` also uses the accounting state layout and event seeds. `solve` imports `backend.assembly_results.publish`. | Point to the shared accounting owner; retain `BoundaryFunction`, `NetworkExecution`, `solve` and all their methods. A common integration run still needs this accounting even though it never calls native `integrar`. |
| `backend/assembly_results.py` | `er.muestras`, `er.firma`; deferred native imports of `evaluacion_volumen`, `potenciales`, `_seguir_ids`, `_certificacion`, `_procedencia`, `_DESCRIPCION_EVENTO`, `REVISION`. | Move helpers in and import shared accounting/constants. Eliminate all deferred native imports, not only top-level imports. |
| `backend/motor_diagramas.py` | `_pares` calls native `capacidades_v2`; `capacidades` calls `cobertura_unifac`. | Retained capability owner. Point/diagram behavior is preserved. |
| `backend/motor_catalogo.py` | `_operaciones` calls native `capacidades_v2`. | Retained capability owner; compare the complete catalog and evidence fields. |
| `backend/motor_ensamblaje.py`, `backend/v2_dispatch.py` | Direct Python dispatch still reaches native `validar_v2`/`resolver_v2`; only HTTP was switched. | Migrate private callers and retire the explicit branch last. Preserve retired-v1 behavior. |
| `backend/routes_engine.py` | Uses v2 dispatch for the three HTTP operations and legacy helpers for non-v2 bodies. | Keep routes and revision discrimination, including rejection of boolean revision values. No endpoint deletion. |
| `core/modelo/adaptadores.py`, `core/resultados/adaptadores.py`, `core/resultados/formato.py`, `frontend/motores/modelo/*`, `frontend/motores/resultados/*` | Revision-2 persisted-input/output conversion and retained equilibrium payloads. | Keep; deleting the integrator does not retire the serialized format or common result validation. |

Read-only AST import inspection and repository text searches covered `backend/`, `core/`, `tests/`, `frontend/` and tools. Documentation-only references in `backend/motor_mezclas.py` and `core/dynamic_common.py` can be corrected during the later change, without touching science. The audit is a dated inventory: repeat the import scan immediately before implementation, because the workspace contains other agents' ongoing work.

### Tests: remove native execution branches, preserve coverage

No regression file is discarded wholesale. Retain independent laws/references and corrupt-payload controls. A common result compared with the same common result through an adapter is a routing test, not an independent numerical reference.

| Files | What goes / what replaces it |
|---|---|
| `tests/test_v2_compatibility.py` | Remove the fresh `native.resolver_v2` leg in `test_all_25_archives` only after freezing final-source comparison evidence. Keep `compare`, all seven currently enumerated test methods including controls, and `tests/v2_parity_cases.py`'s immutable archive/context/limit/reference policy. Replace references to native state packaging and `network.Sistema`, `muestras`, `clasificar_evento` with shared owners. Replace no-native-call monkeypatches with an import-denial test that works when the modules no longer exist. Do not turn evidence replay into a claimed fresh solve. |
| `tests/test_v2_route_switch.py` | Remove the successful `native` mode leg and direct-native equality checks from both test methods after approval; replace with explicit rejection of retired configuration and a common-only fresh HTTP matrix. Retain default/explicit-common provenance, malformed settings, unchanged validation envelope, injected exception/no-retry controls and historical payload readability. |
| `tests/test_common_network_results.py` | Replace native module/helper monkeypatch targets and the native small-scale-work comparison with preserved failure evidence plus independent work/energy checks. Retain `no_cumple` under corrupted work, negative second-law evidence, singular-heat and probe failures, certified prefixes and supercritical event identity. |
| `tests/test_thermodynamic_events.py` | Route `resolver_v2` calls to the adapter; retarget sampling/accounting patches. Replace `network.Tramo`/`Trayectoria` in `test_exact_event_time_replaces_nearby_output_sample` with a simple test trajectory exposing `y`, events, stop and final time. Keep cached-certificate rejection, scaling/horizon, heating/cooling/LLE, work corruption and exact-event-time tests. Claude-owned thermodynamic regression changes require coordination. |
| `tests/test_transient_phase_window.py` | Replace native resolve with adapter resolve; retain `reference_window`, both narrow/wide-window tests and their independent static-equilibrium reference. Common window/margin tests stay. |
| `tests/validar_motor_ensamblaje_v2.py`, `tests/validar_motor_consolidacion_v2.py` | Migrate direct/shared-dispatch solves, capabilities and `er.Sistema.__call__` corruption hooks; retain all 114/128 historical checks and their physical meaning. Ensure corruption still reaches the retained accounting and compiled physical rates as intended. Do not merely patch an unused native method and count a passing test. |
| `tests/validar_motor_n_componentes.py`, `tests/validar_motor_unifac.py`, `tests/validar_motor_catalogo.py`, `tests/benchmark_unifac.py` | Migrate `me.resolver`, native capabilities and `_cobertura_unifac` cache controls. Keep package/permutation/zero-species/domain/size evidence, independent references and benchmark operations. Benchmark output is not automatically a performance pass. |
| `tests/test_common_admission.py`, `tests/test_dynamic_definition.py`, `tests/test_energy_derivation.py`, `tests/test_material_derivation.py`, `tests/test_momentum_derivation.py`, `tests/test_thermodynamic_derivation.py`, `tests/validar_modelo_comun.py` | Move native `validar_v2` imports to the shared wire validator; preserve tuple-return expectations, journals, five-code rejections, equation catalogs and exact round trips. |
| `tests/test_workspace_handoffs.py`, `tests/validar_capa_agua.py`, `tests/validar_capa_termodinamica.py`, `tests/validar_corte_vertical.py` | Replace direct native solve/validation calls. Keep static/analytic/archived references independently of adapter equality; the two-path comparison alone loses numerical independence after deletion. |
| `tests/validar_unidades.py` | Remove the native import used only for unit registration; assert retained explicit registration and conversions. |
| `tests/test_retired_v1_assembly.py`, `tests/v1_assembly_cases.py`, `tests/test_v2_initialization.py`, `tests/validar_capa_unifac.py` | Keep v1 retirement, nine frozen water references, shared initialization and independent UNIFAC checks. Update imports only if the extracted owner requires it. |
| `tests/verificar_v2_compatibility.mjs`, `tests/verificar_v2_route_switch.mjs` | Keep production-reader controls. Switch the fresh-evidence input contract to common-only after native retirement, while retaining saved native examples for historical provenance checks. Never manufacture a fresh native result from an old record. |
| `tests/verificar_contrato_ensamblaje_v2.mjs`, `tests/verificar_contrato_unifac.mjs`, `tests/verificar_contrato_catalogo.mjs`, `tests/verificar_contrato_ensamblaje.mjs` | Keep frozen v2 and retired-v1 contract/point-state verification. The serializer contracts outlive their integrators. |
| `frontend/verificar_modelo_comun.mjs`, `frontend/verificar_bateria_multifisica.mjs` | Embedded Python calls still use the legacy dispatcher; redirect to common execution and update the comparison meaning, retaining round trips and all model fixtures. These scripts write canonical artifacts: use a disposable validation copy or first add an explicitly reviewed no-write mode. |

### Frontend readers, services and examples: none removed by solver retirement

Keep `frontend/app/motor/contratoEnsamblajeV2.ts`, `lectorEnsamblajeV2.ts`, `servicioEnsamblajeV2.ts`, `resultadoEnsamblajeV2.ts`. Specifically retain `readExecutionProvenance`, `leerCapacidadesV2`, `validarEstadoVolumenV2`, `leerValidacionV2`, `leerResolucionV2`, `esMuestraFronteraEvento`; service `capacidadesV2`, `validarV2`, `resolverV2`; result `repartoComponente`, `nombreSerieV2`, `adaptarResultadoV2`, `seriesFasesV2`, `graficasComponentesV2`, `validarResultadoV2`, `graficasInicialesV2`. Historical native provenance remains valid saved data even after new native execution is unavailable. Removing these readers or translating persisted keys needs a separate format/UI migration decision.

Their live consumers stay: `EspacioRedTermodinamica.tsx`, `estadoResolucionRed.ts`, `redTermodinamica.ts`, `modeloNumerico.ts`, `metadatosRed.ts`, `validarMetadatosRed.ts`, `destinoDiagnosticoRed.ts`, `contextoMuestraEquilibrio.ts`, `verificarEstadoMateriaRed.ts`, `AlcancePaqueteRed.tsx`, `AvisoCertificacionRed.tsx`, `alcanceEdicionPaquete.ts`, `EditorComponentesRed.tsx`, `contratoContribucionGrupos.ts` (all under `frontend/app/motor/`), and the Model material/energy/thermodynamic journal editors. `ModelWorksheet` remains the sole layout owner. Frontend verification inventory in section 12 stays applicable, including editing, coverage, certification, diagram and chart/export checks. Keep `frontend/package.json` regression entry points; change their targets only if a test is deliberately moved.

No archived example goes. Keep `tests/solicitudes_v2.py` and the internal data constructors `hojasDemostracion.ts`, `hojasPruebaMultifasico.ts`, `hojasPruebaNComponentes.ts`, `hojasPruebaUNIFAC.ts`, `materialNetworkTemplates.ts`, `phaseDiscoveryExample.ts`, `frontend/testing/modelFixtures.ts`, and `frontend/examples/heatedFillingVessel.ts`. They are regression/user-model inputs, not a reason to repopulate the product library. Keep `tests/generar_ejemplos_motor_ensamblaje_v2.py`: it calls HTTP and also produces unrelated point-state/ice examples, so it is not a native-only file. Its `casos_v2`, `casos_estaticos`, `pedir` and `main` must not overwrite frozen archives as part of retirement. Any future regeneration needs a separate output destination and explicit authorization. Historical fit evidence such as `tests/ajuste_nrtl_lle_agua_butanol.py` also stays.

### Immutable evidence to retain

`tests/v2_parity_cases.py:archives()` was executed read-only during this audit and verifies **25 requests + 24 sibling responses = 49 files**, manifest SHA-256 `0931e2c77e83011aead32888d78239fc08e66dabc8dad9cb9fa20a6ea1c9657d`. Keep every request below and its same-directory `-respuesta.json` sibling; the open-boundary draft has no sibling response. Responses include validation-only negative cases, not just resolved trajectories. Do not regenerate, normalize or translate their bytes.

| Request, relative to `docs/ejemplos/` | Frozen sibling |
|---|---|
| `borrador-frontera-abierta/olla-abierta-peticion.json` | None; keep unsupported draft |
| `demostracion/demostracion-heteroazeotropo-agua-butanol-peticion.json` | Keep `-respuesta.json` |
| `demostracion/demostracion-rayleigh-etanol-agua-peticion.json` | Keep `-respuesta.json` |
| `motor-catalogo/motor-ensamblaje-v2-resolver-acetona-agua-unifac-peticion.json` | Keep `-respuesta.json` |
| `motor-catalogo/motor-ensamblaje-v2-resolver-contacto-iapws-y-mezcla-peticion.json` | Keep `-respuesta.json` |
| `motor-catalogo/motor-ensamblaje-v2-resolver-corriente-nrtl-a-unifac-peticion.json` | Keep `-respuesta.json` |
| `motor-catalogo/motor-ensamblaje-v2-resolver-sustitucion-vl-etanol-peticion.json` | Keep `-respuesta.json` |
| `motor-catalogo/motor-ensamblaje-v2-validar-rechazo-corriente-iapws-a-mezcla-peticion.json` | Keep `-respuesta.json` |
| `motor-n-componentes/motor-ensamblaje-v2-resolver-calentamiento-ideal-5-peticion.json` | Keep `-respuesta.json` |
| `motor-n-componentes/motor-ensamblaje-v2-resolver-calentamiento-nrtl-4-peticion.json` | Keep `-respuesta.json` |
| `motor-n-componentes/motor-ensamblaje-v2-resolver-red-ideal-5-especie-entrante-peticion.json` | Keep `-respuesta.json` |
| `motor-n-componentes/motor-ensamblaje-v2-validar-nrtl-4-par-ausente-peticion.json` | Keep `-respuesta.json` |
| `motor-unifac/motor-ensamblaje-v2-resolver-unifac-calentamiento-2-peticion.json` | Keep `-respuesta.json` |
| `motor-unifac/motor-ensamblaje-v2-resolver-unifac-calentamiento-4-peticion.json` | Keep `-respuesta.json` |
| `motor-unifac/motor-ensamblaje-v2-resolver-unifac-dortmund-calentamiento-4-peticion.json` | Keep `-respuesta.json` |
| `motor-unifac/motor-ensamblaje-v2-resolver-unifac-lle-mezcla-agua-butanol-peticion.json` | Keep `-respuesta.json` |
| `motor-unifac/motor-ensamblaje-v2-resolver-unifac-monofasico-detenido-peticion.json` | Keep `-respuesta.json` |
| `motor-unifac/motor-ensamblaje-v2-resolver-unifac-red-5-especie-entrante-peticion.json` | Keep `-respuesta.json` |
| `motor-unifac/motor-ensamblaje-v2-validar-rechazo-unifac-simulado-asignacion-ausente-peticion.json` | Keep `-respuesta.json` |
| `motor-v2/motor-ensamblaje-v2-resolver-binario-acoplado-peticion.json` | Keep `-respuesta.json` |
| `motor-v2/motor-ensamblaje-v2-resolver-calentamiento-etanol-agua-peticion.json` | Keep `-respuesta.json` |
| `motor-v2/motor-ensamblaje-v2-resolver-contacto-dos-aguas-peticion.json` | Keep `-respuesta.json` |
| `motor-v2/motor-ensamblaje-v2-resolver-decantador-agua-butanol-peticion.json` | Keep `-respuesta.json` |
| `motor-v2/motor-ensamblaje-v2-validar-calor-pendiente-peticion.json` | Keep `-respuesta.json` |
| `motor-v2/motor-ensamblaje-v2-validar-decantador-sin-criterio-peticion.json` | Keep `-respuesta.json` |

Also keep all capability snapshots and point-state/diagram responses in `docs/ejemplos/motor-v2/`, `motor-n-componentes/`, `motor-unifac/`, `motor-catalogo/`, `demostracion/` and `modelo-comun/`; those are not all included in the 49-file manifest. Keep `docs/contratos/contratoEnsamblajeV2.ts` and the related published contract snapshots. Keep `tests/reference_data/v2-parity-adjunct.json` (including source digests and independent event evidence), `tests/v2_parity_cases.py` (`ZERO_REFERENCES`, `EVENT_REFERENCES`, immutable limits and simulated-missing-assignment context), all frozen v1 `docs/ejemplos/motor-ensamblaje-*` inputs/outputs and `tests/fixtures_ensamblaje/` where present. Keep `tests/reference_data/m1-a.json`, `m1-b.json`, `m1-c.json` byte-for-byte and their law-derived reference definitions.

Before removal, retain final-source native/common/HTTP comparison records and digests from `.tmp/codex-v2-parity/`, `.tmp/codex-v2-http/` and Claude's independent review evidence in a durable, explicitly reviewed reference location. Ignored working directories alone are not a reproducible deletion gate. This future preservation must not overwrite the 49 originals or pretend that old evidence matches new source. Native heteroazeotrope lateness of 1.1973224e-6 s and the small-scale native work failure remain recorded historical findings. Preserve independent physical references; do not adopt those native defects as expected common behavior.

### Ordered implementation, only after the user decides

1. **Freeze the boundary and evidence.** Recheck claims, snapshot the full preservation set, record source/package digests and obtain the specific decision to retire native fallback while keeping the v2 protocol. Resolve the performance gate against the existing R6 budgets; scientific parity alone is insufficient. Keep F3 work and frozen M1 out of scope.
2. **Extract shared behavior without deleting either path.** Move capability/wire/result helpers and explicit unit registration. Claude moves shared network accounting/events/sampling. Use compatibility re-exports temporarily so both executors remain runnable. Compare capabilities/validation/model identities and result certificates before/after, including import-order and cache reset behavior. No tolerance relaxation, duplicate scientific implementation or broad refactor.
3. **Migrate every consumer and regression hook.** Rewire the table above, including catalog/diagrams, deferred imports, private dispatcher callers, embedded Python in frontend verifiers and benchmark paths. Keep protocol tuple shapes. Move corruption hooks to code that the common path actually executes. Preserve independent reference checks when two implementations become one.
4. **Run the last dual-executor gate while native still exists.** Fresh all-25 direct and HTTP comparisons, independent adjuncts, negative controls, frontend reader/round-trip/lifecycle checks and R6 performance measurements. No `V2_PARITY_REPLAY=1` as deletion evidence. Require a complete fresh source digest and Claude's review, with known native findings explicit.
5. **Remove native execution and the two emptied modules.** Remove only the native-only symbols enumerated above, then the emptied files; remove temporary re-exports and imports. Reject retired `native` configuration explicitly. Keep protocol/readers/examples and common scientific behavior. Claude performs or explicitly coordinates removal of its owned file. Do not delete code merely to make an import test pass.
6. **Run the post-removal gate.** Fresh common-only matrix against preserved archives/independent references, full affected regressions, dynamic import-denial/startup checks and archive hashes. Update architecture/roadmap/Checklist/board to the measured scope, without marking F3 done. Review changes independently before closing the retirement milestone. Commit/push remain separate user instructions.

### Regression commands and exit criteria

These are commands for the later approved implementation, **not tests claimed as run for this planning task**. Run from the repository root unless noted. Record exit status, source digest, timing and evidence location. Use isolated test processes; never restart or stop the user's 3000/8004/8005 servers. Tests requiring HTTP use their in-process ASGI app or an explicitly owned server.

**Before final removal, both executors present (PowerShell):**

```powershell
[Environment]::SetEnvironmentVariable('V2_PARITY_REPLAY', $null, 'Process')
[Environment]::SetEnvironmentVariable('V2_HTTP_SHARD', $null, 'Process')
[Environment]::SetEnvironmentVariable('V2_HTTP_SHARDS', $null, 'Process')
[Environment]::SetEnvironmentVariable('RAGE_V2_ASSEMBLY_EXECUTOR', $null, 'Process')
python -B tests/test_v2_compatibility.py -v
python -B tests/test_v2_route_switch.py -v
node tests/verificar_v2_compatibility.mjs
node tests/verificar_v2_route_switch.mjs
```

Require all 25 fresh direct and all 25 fresh HTTP cases, all seven physical adjuncts, unchanged diagnostic/initialization envelopes, and successful reader corruption controls. Reader scripts consume `.tmp` evidence: verify its complete manifest and source digest first, not just their exit codes. After removal, these same test entry points must have the common-only/preserved-reference semantics specified above; do not run obsolete dual-native tests and ignore failures.

**Core and physical regression gate, after import migration:**

```powershell
python -B -m unittest discover -s tests -p 'test_*.py' -v
python -B tests/validar_motor_ensamblaje_v2.py
python -B tests/validar_motor_consolidacion_v2.py
python -B tests/validar_motor_n_componentes.py
python -B tests/validar_motor_unifac.py
python -B tests/validar_motor_catalogo.py
python -B tests/validar_unidades.py
python -B tests/validar_modelo_comun.py
python -B tests/validar_corte_vertical.py --no-write
python -B tests/validar_capa_unifac.py
python -B tests/validar_compilador_explicito.py
python -B tests/benchmark_unifac.py
```

The unittest gate includes admission/horizon, initialization, common publication, stage-stop, narrow-window/margin, v1 retirement, physical journals, handoffs, kernel/M1, transformed/hydraulic and F3 tests. F3 tests are existing regression consumers only: their independent-review status is not changed by retirement. Any pre-existing failure must be recorded against the pre-removal source and adjudicated, not silently skipped. The benchmark must actually route to common execution after migration and be assessed against the canonical F9-R6 budgets; it does not enforce all budgets itself. Run Claude's existing thermodynamic/diagram suites when its extracted helpers affect those consumers; do not certify them through compile/import checks alone.

**Contract and frontend regression gate:**

```powershell
node tests/verificar_contrato_ensamblaje.mjs
node tests/verificar_contrato_ensamblaje_v2.mjs
node tests/verificar_contrato_unifac.mjs
node tests/verificar_contrato_catalogo.mjs
node frontend/verificar_common_certification.mjs
node frontend/verificar_aviso_certificacion.mjs
node frontend/verificar_physical_journals.mjs
node frontend/verificar_model_derivations.mjs
node frontend/verificar_material_journals.mjs
node frontend/verificar_workspace_handoffs.mjs
node frontend/verificar_transform_execution.mjs
node frontend/verificar_derived_lifecycle.mjs
node frontend/verificar_hydraulics.mjs
npm --prefix frontend run test:motor-fundamental
```

From `frontend/`, run `node node_modules/typescript/bin/tsc --noEmit` and scoped ESLint on the changed TS/MJS files. Browser checks must exercise an existing network through Model/Transform/Solve/Results, stale-response and cancellation behavior, certification display, phase/component charts, exports, diagram fingerprint matching and reloading historical native results; no example loader or new UI is authorized.

**Writers require a disposable validation copy or reviewed no-write support:** `python -B tests/validar_capa_agua.py`, `python -B tests/validar_capa_termodinamica.py`, `node frontend/verificar_modelo_comun.mjs`, `node frontend/verificar_bateria_multifisica.mjs`. They currently write canonical example/snapshot files. `validar_modelo_comun.py` can also write missing references; all required inputs must exist before running it. Contract verifiers generate temporary TypeScript files; do not confuse those with permission to regenerate archives. Do not run `generar_ejemplos_motor_ensamblaje_v2.py` or any `--regenerar` / `--update-checklist` option as a substitute for preserved-reference verification.

**Final structural and preservation checks:**

```powershell
rg -n 'motor_ensamblaje_v2|ensamblaje_red|native-v2|RAGE_V2_ASSEMBLY_EXECUTOR' backend core tests frontend --glob '*.py' --glob '*.ts' --glob '*.tsx' --glob '*.mjs'
python -B -c "import sys; sys.path.insert(0,'tests'); from v2_parity_cases import archives; print(len(archives()))"
node tools/roadmap_board/build_board.mjs --check
```

The text scan is an inventory, not a zero-match test: historical provenance strings, explicit retired-setting diagnostics and import-denial controls are allowed. **No executable import/call of either deleted module may remain.** Add a regression that denies both imports in a fresh process and exercises app startup, v2 capabilities/validation/resolve, catalog, diagrams, common network publication and the legacy Python dispatcher. Preserve v1 retirement replies. Check the entire frozen set against the pre-change byte manifest, including M1 and capability/static examples outside the 49-file manifest. Passing tests cover the declared surface; they do not justify deleting unrelated files.

**Decision requested, still open:** approve this staged retirement of the native executor and its explicit fallback, retaining the v2 adapter/protocol/readers and all archived evidence, with shared extraction and independent/performance gates first; or retain the fallback. No implementation begins until the user decides. Claim released after recording this plan. **Board refresh pending.**
