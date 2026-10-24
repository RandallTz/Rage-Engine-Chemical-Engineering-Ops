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
