# Thermodynamics of the independent engine — delivery H0/H1

14 October 2026. It answers [docs/history/frontend/contract-claude-thermodynamics-engine.md](../history/frontend/contract-claude-thermodynamics-engine.md) (milestones H0 and H1) and [docs/history/frontend/plan-thermodynamics-engine.md](../history/frontend/plan-thermodynamics-engine.md). HTTP contract: revision 1 of `frontend/app/motor/contratoTermodinamica.ts`, **with no changes of shape**.

> **Updated by H3** ([docs/engine/thermodynamics-h3.md](thermodynamics-h3.md)): PH, UP and UV are published, TP saturation offers `alternativas`, and the example `ph-no-soportado` was removed. What this document says about those specifications as "not supported" describes the state of H1. TP does not change.

What it contains: point evaluation of a state of **pure water** at T/P within a verified single-phase domain, with certified stability, and contract diagnostics for everything else (saturation, critical region, solid, mixtures, PH/UV/UP). There is no dynamics, two-phase flash or inverse specification: they are published as not supported.

| Piece | File |
| --- | --- |
| Physics (no HTTP contract) | `core/agua_iapws95.py` |
| Revision 1 contract | `backend/motor_termodinamica.py` |
| Routes (only added) | `backend/main.py`: `GET /motor/termodinamica/capacidades`, `POST /motor/termodinamica/evaluar` |
| Physics and contract tests | `tests/validar_motor_termodinamica.py` (591 checks) |
| Real examples | `tests/generar_ejemplos_motor_termodinamica.py` → `docs/ejemplos/motor-termodinamica-*` |
| Python → JSON → TypeScript | `tests/verificar_contrato_motor_termodinamica.mjs` (the real TS validator on the real responses) |

`thermodynamics/proveedor.py` was not touched (it has someone else's uncommitted change). The new adapter is independent and does not import it.

---

## H0. Foundation

### Fundamental relation and scope

For a simple compressible system in internal equilibrium, without surface (capillarity), electric, magnetic or gravitational terms:

$$dU = T\,dS - P\,dV + \textstyle\sum_i \mu_i\,dn_i$$

$$H = U + PV,\qquad A = U - TS,\qquad G = H - TS = \textstyle\sum_i \mu_i n_i$$

Natural independent variables: U(S,V,n), H(S,P,n), A(T,V,n), G(T,P,n). The equilibrium criterion depends on what is fixed: minimum of G at T, P, n; minimum of A at T, V, n; maximum of S at U, V, n. In H1, T, P and n (one component) are fixed, so the stable state is the one of **minimum G**; that criterion is not applied to other specifications.

IAPWS-95 is explicit in A(T, ρ): the properties come from derivatives of φ = A/(nRT) = φ⁰(δ,τ) + φʳ(δ,τ), with δ = ρ/ρc and τ = Tc/T. What is evaluated, all per kg:

| Property | Expression |
| --- | --- |
| P | ρRT(1 + δφʳ_δ) |
| u | RTτ(φ⁰_τ + φʳ_τ) |
| h | u + P/ρ |
| s | R[τ(φ⁰_τ + φʳ_τ) − φ⁰ − φʳ] |
| f, g | RT(φ⁰ + φʳ);  f + P/ρ |
| c_v | −Rτ²(φ⁰_ττ + φʳ_ττ)  — derivative of u at **constant V and n** |
| c_p | c_v + T(∂P/∂T)²_ρ / (ρ²(∂P/∂ρ)_T)  — derivative of h at **constant P and n** |
| (∂P/∂ρ)_T, (∂P/∂T)_ρ, w | calculated; the two derivatives stay in `Propiedades` for H2 |

The coefficient `c_u` of the engine's manual model is **not** c_p or c_v: it is the slope of an affine relation u(T) declared by the user. Nothing in this module reinterprets it.

### Separation of layers

| Layer | What it is | In this delivery |
| --- | --- | --- |
| Chemical identity | CAS with check digit; name and symbol are presentation | CAS required; `proveedorId` → not verifiable |
| EOS | A(T, ρ) of the fluid | IAPWS-95 |
| Phase properties | u, h, v, s, c_p, c_v of a phase | from the EOS, on the chosen branch |
| Correlations | auxiliary fits | Psat, ρ′, ρ″ from `chemicals` (fits to the multiple-precision solution), **rechecked** with the EOS at every evaluation |
| Activity | G^E of liquid mixtures | not applicable (pure substance) |
| Stability | is there another phase with lower G at the same T, P? | pure-substance TPD (below) |

### Audit of what already exists

| Adapter | What it supplies | What is missing for the engine |
| --- | --- | --- |
| `thermodynamics/proveedor.py` (thermo `Chemical` + UNIFAC) | Psat, ΔHvap, liquid and ideal-gas c_p, ρ_L and σ by correlation, UNIFAC γ, ΔHf°/ΔGf°, ideal-gas vapor density | It requires UNIFAC groups for **all** components (water alone should not need them). `Chemical.calculate(T,P)` mutates state shared between calls. No EOS, no residual properties, no fugacities, no derivatives at constant V, no stability, no inverse specifications. Mixture density by Amagat and ideal vapor. |
| `thermodynamics/entalpia.py` | h_L = Σx∫c_p,L dT; h_V = h_L + ΣyΔHvap (ref. 298.15 K) | An ideal gas/liquid path; no dependence on P, no u or s, no common reference with an EOS. Useful for the lab, not as the engine's closure. |
| `thermodynamics/elv.py`, `ell.py` | Bubble/dew point by modified Raoult; LLE by equality of activities with stability | Both on top of `proveedor.py`; ideal vapor. Outside the scope of H1. |
| `core/vapor_if97.py` | IF97 regions 1, 2, 4: T_sat, P_sat, h′, h″ (verified against IF97 tables) | Only enthalpy at saturation; no region 3, no u/s/v, no U/V flash. Used here only as an **independent cross-check**. |
| `chemicals.iapws` 1.5.2 (IAPWS-95) | φ⁰, φʳ and derivatives up to 2nd order (3rd in φʳ), Psat/ρ′/ρ″ fits, `iapws95_rho(T,P)` | Pure functions, without state. It does **not** certify stability: `iapws95_rho` chooses the branch by comparing P with its Psat. This module does not use that choice or `iapws95_properties`. |
| `thermo.phases.IAPWS95*`, `thermo`'s flashes | Generic phases and flashes | Not audited or used. Their presence is not support. |

### Version, reference and provenance

- Published model: `agua-iapws95`, version `1`. Formulas IAPWS R6-95(2018) / Wagner and Pruß (2002).
- The library must be `chemicals == 1.5.2` (the audited one). If the version changes, or if at start-up it does not reproduce the published values (relative error > 1e-8), **the catalog comes out empty** and every request receives `MOTOR_ESTADO_MODELO_NO_PUBLICADO`. That way a dependency update does not silently change the model's physical identity.
- Energy and entropy reference: that of IAPWS-95, u = 0 and s = 0 of the saturated liquid at the triple point. Id: `iapws95-u0-s0-liquido-saturado-punto-triple`. It **does not match** the reference of the manual model or that of `entalpia.py` (298.15 K): mixing absolute values between models is an error; differences of h or u within one model do not depend on the reference.
- Isolation: everything is a pure function of (T, ρ). The test evaluates A, B, A and requires byte-for-byte identical responses.

---

## H1. Single-phase pure state: physical decisions

### Published domain

T ∈ [273.16, 1073.15] K, P ∈ [100 Pa, 100 MPa], except for the critical band.

- **Solid.** With T ≥ 273.16 K and P ≤ 100 MPa no ice is stable: the melting of ice Ih falls below 273.16 K as P rises, and ices III, V and VI appear above 209.9 MPa (IAPWS R14-08). The solid is left out **by domain**, not by the stability search; that is why `alcance` does not include it and a request at −5 °C comes out `no_soportado` with `MOTOR_ESTADO_FUERA_DE_DOMINIO`, without being reclassified as liquid.
- **Maximum T 1073.15 K**: the limit of IF97's region 2, so that the whole domain has an independent cross-check. IAPWS-95 goes further; it will be extended when needed and checked.
- **Critical band excluded**: T ∈ [0.995, 1.005]·Tc = [643.86, 650.33] K **and** P ∈ [0.95, 1.05]·Pc = [20.96, 23.17] MPa. There the compressibility diverges, the density at T/P is ill-conditioned and the stability margin vanishes. Response: `no_soportado`, `MOTOR_ESTADO_REGION_CRITICA`.

The rectangle of `capacidades.dominio` is an envelope: the critical band and saturation are checked on every request.

### Phase type and regime

| Condition | tipo | regimen |
| --- | --- | --- |
| T < Tc, P > Psat(T) | `liquido` | `ordinario` (also if P > Pc: compressed liquid) |
| T < Tc, P < Psat(T) | `vapor` | `ordinario` |
| T ≥ Tc, P ≤ Pc | `vapor` | `ordinario` |
| T > Tc, P > Pc | `fluido` | `supercritico` |

Above Tc there is no phase transition; calling the low-pressure fluid `vapor` is a convention, declared here. A supercritical state has a single `fluido` phase, without a vapor quality.

### Saturation: T/P undetermined

If |P/Psat(T) − 1| ≤ 1e-6, the point is on the saturation curve: liquid and vapor coexist and T, P do not fix how much there is of each. Response `incompleto`, `MOTOR_ESTADO_SATURACION_INDETERMINADA`, `evaluacion: null`. A vapor fraction of 0, 0.5 or 1 is **not chosen**. The diagnosis carries no `alternativas` because PH/UV/UP are not accepted yet (the contract asks for them "when they are accepted"); it will have them in H3.

The 1e-6 band covers a Psat value typed with 7 digits. Outside it the state is determined and the stability certifies it with margin (at P = Psat·(1 ± 3e-6) the tests require a stable liquid/vapor).

A useful example: 100 °C and 101.325 kPa is **vapor**, because Psat(373.15 K) = 101 418 Pa > 101 325 Pa (water boils at 1 atm at 373.124 K). It is in `docs/ejemplos/motor-termodinamica-vapor-100C-1atm-*`.

### Density

Below Tc there are two single-phase branches: vapor ρ ∈ (0, ρ″] and liquid ρ ∈ [ρ′, ρ(1 GPa)]. The branch is chosen by comparing P with Psat (Maxwell, see below) and P(T, ρ) = P is solved on it with Brent (rtol 1e-15) and three Newton steps that cannot leave the branch. Above Tc, one branch.

### Stability: criterion, scope and tolerance

For a pure substance at fixed T, the tangent-plane distance

$$\mathrm{TPD}(\rho) = \rho\,[f(T,\rho) - g^*] + P^*,\qquad g^* = g(T,\rho^*),\ P^* = P(T,\rho^*)$$

is the Helmholtz energy per volume minus its tangent at the state ρ*. If there is a density with TPD < 0, a phase of that density would have lower G at the same T and P*: the state is not stable. The EOS's P* (not the requested P) is used so that TPD(ρ*) = 0 exactly and the error of solving ρ is not confused with a margin.

- **Scope of the search**: the single-phase branches above, up to ρ(1 GPa) (the validity limit of IAPWS-95), 400 log-spaced points per branch plus ρ*, and a bounded refinement of each local minimum of the grid. About 840 evaluations; ~4 ms per state.
- **Why the dome is not swept**: between ρ″ and ρ′ IAPWS-95 does not represent physical homogeneous states (at 300 K and 300 kg/m³ it gives P ≈ −1.5·10²³ Pa) and a naive sweep returns TPD ≈ −10²² Pa, a false "instability". No homogeneous state of that region is stable against separating into the two saturated phases, so excluding it removes no physical candidates. It is a limitation declared in `metodo`.
- **Tolerance**: residual = max(0, −min TPD)/P* ≤ 1e-9. Also (∂P/∂ρ)_T > 0 at ρ*.
- **It is not a rubber stamp**: the test forces superheated liquid (0.9·Psat) and subcooled vapor (1.05·Psat) at 300, 450 and 600 K and requires the certificate to reject them (residual > 1e-6).
- What is not claimed: a global minimum outside the branches searched, or anything about solid phases (the domain excludes them).

### Phase policy

- `cantidad: monofasico`: H1's stable state always has one phase; it is checked and `politica_fases` is published. At saturation it comes out `incompleto`, not a forced phase.
- `tiposPermitidos`: if the calculated stable state is not in the list → `invalido`, `MOTOR_ESTADO_FASE_INCOMPATIBLE`. The allowed branch alone is **not** searched in order to call it stable.
- `cambioInterno: prohibido`: in a point query without a trajectory, `cambio_interno` is recorded as `no_evaluable` (residual null). It does not imply single-phase.
- No metastable branches are forced.

### Published checks

| id | residual (dimensionless) | tolerance |
| --- | --- | --- |
| `estabilidad` | max(0, −min TPD)/P* | 1e-9 |
| `dominio` | null: a membership check (reason with limits) | null |
| `ecuacion_estado` | \|P(T,ρ) − P\| / max(P, ρ(∂P/∂ρ)_T). It scales with the bulk modulus because the liquid's pressure is stiff | 1e-12 |
| `identidad_h_u_Pv` | \|h − u − Pv\|/(RT), with the specified P | 1e-9 |
| `derivadas` | max(\|c_p − (∂h/∂T)_P\|/c_p, \|c_v − (∂u/∂T)_ρ\|/c_v), analytical against central differences with step 1e-5·T, re-solving ρ on the same branch. `no_evaluable` if at T ± dT the P falls on another branch | 1e-6 |
| `saturacion` (T < Tc) | Maxwell: max(\|g′−g″\|/(RT), \|P(ρ″)−Psat\|/Psat, \|P(ρ′)−Psat\|/(ρ′(∂P/∂ρ)_T′)). The reason gives Psat, ρ′, ρ″ and \|P/Psat − 1\| | 1e-9 |
| `reconstruccion_material` | one phase with the global composition: exactly 0 | 1e-12 |
| `masa_molar` (if declared) | \|M_decl − M\|/M | 1e-7 |
| `politica_fases` (if restricted) | null | null |
| `cambio_interno` (if forbidden) | `no_evaluable`, null | null |

`equilibrio` does not appear because there are never two phases in H1. If a check with a residual fails, the state is not published (`no_convergente`).

### Molar mass and bases

The molar mass used is IAPWS-95's, 18.015268 g/mol, with its source. A declared molar mass that differs by more than 1e-7 relative is rejected as `MOTOR_ESTADO_MASA_MOLAR_CONTRADICTORIA`: it is the same tolerance the client applies, which would otherwise reject the response. Practical consequence: **18.015 g/mol is rejected**. With a single component the phase's molar and mass fractions coincide and equal 1; the volume fraction also equals 1 because there is one phase.

---

## Contract: what the server does with each request

The body is read as free JSON, not with Pydantic, so that each known problem comes out as a contract response with a code and a path instead of a 422. HTTP is always 200 for valid JSON. A rejection always carries `evaluacion: null` and at least one diagnosis; with several problems, the state is the most severe in this order: `invalido` > `no_soportado` > `incompleto` > `no_convergente`. Everything is diagnosed at once (missing data and an unpublished model, for example).

| Code | State | When |
| --- | --- | --- |
| `MOTOR_ESTADO_FORMA_INVALIDA` | invalido | wrong JSON type, ID not a positive integer, empty text |
| `MOTOR_ESTADO_CAMPO_NO_ADMITIDO` | invalido | any unexpected key (they are not ignored) |
| `MOTOR_ESTADO_SOBREESPECIFICADO` | invalido | a field of another specification, e.g. `h` in a TP |
| `MOTOR_ESTADO_REVISION` | invalido | `revision` ≠ 1 |
| `MOTOR_ESTADO_DATO_SIN_DECLARAR` | incompleto | missing field, `valor: null`, missing fraction (an absent species is declared with 0) |
| `MOTOR_ESTADO_DATO_INVALIDO` | invalido | non-numeric, non-finite, negative fraction |
| `MOTOR_ESTADO_UNIDAD_INCOMPATIBLE` | invalido | unit outside the contract's table |
| `MOTOR_ESTADO_FUERA_DE_MAGNITUD` | invalido | T, P, V ≤ 0 (absolute T), negative amount or zero total |
| `MOTOR_ESTADO_COMPOSICION_NO_NORMALIZADA` | invalido | Σ ≠ 1 (tolerance 1e-10); it is not renormalized |
| `MOTOR_ESTADO_COMPONENTE_DESCONOCIDO` | invalido | a fraction or amount for a nonexistent ID |
| `MOTOR_ESTADO_ID_DUPLICADO`, `MOTOR_ESTADO_IDENTIDAD_DUPLICADA` | invalido | repeated ID; two IDs with the same CAS |
| `MOTOR_ESTADO_IDENTIDAD_SIN_DECLARAR` | incompleto | without `identidadQuimica` |
| `MOTOR_ESTADO_CAS_INVALIDO` | invalido | format or check digit |
| `MOTOR_ESTADO_IDENTIDAD_NO_VERIFICABLE` | no_soportado | there is a `proveedorId`: this model only verifies CAS |
| `MOTOR_ESTADO_MASA_MOLAR_CONTRADICTORIA` | invalido | see above |
| `MOTOR_ESTADO_POLITICA_INVALIDA`, `MOTOR_ESTADO_ESPECIFICACION_DESCONOCIDA`, `MOTOR_ESTADO_BASE_INVALIDA` | invalido | values outside the contract's unions |
| `MOTOR_ESTADO_MODELO_NO_PUBLICADO` | no_soportado | id/version not published (or unaudited library) |
| `MOTOR_ESTADO_COMPONENTE_NO_SOPORTADO` | no_soportado | a CAS other than water, **also with fraction 0** |
| `MOTOR_ESTADO_ESPECIFICACION_NO_SOPORTADA` | no_soportado | PH, UV, UP (not yet); `alternativas: [["T","P","composicion"]]` |
| `MOTOR_ESTADO_FUERA_DE_DOMINIO` | no_soportado | T or P outside the rectangle; path to the culprit quantity |
| `MOTOR_ESTADO_REGION_CRITICA` | no_soportado | critical band |
| `MOTOR_ESTADO_SATURACION_INDETERMINADA` | incompleto | T/P on the saturation curve |
| `MOTOR_ESTADO_FASE_INCOMPATIBLE` | invalido | stable state outside `tiposPermitidos` |
| `MOTOR_ESTADO_NO_CONVERGENTE`, `MOTOR_ESTADO_VERIFICACION_FALLIDA` | no_convergente | failed density or certification |

Paths: `declaracion.especificacion.T`, `componentes.<id>.identidadQuimica.cas`, `declaracion.especificacion.composicion.fracciones.<id>`… Component IDs come back intact (a component with id 7 returns `composicionMolar: {"7": 1}`). The phase IDs are `liquido-1`, `vapor-1`, `fluido-1`.

PH/UV/UP are validated all the same (units, amounts, zeros) before being declared not supported, so the interface can prepare the specification already.

---

## Evidence

Run from the root:

```
python tests/validar_motor_termodinamica.py                 # 591 checks
python tests/generar_ejemplos_motor_termodinamica.py        # regenerates docs/ejemplos/motor-termodinamica-*
node tests/verificar_contrato_motor_termodinamica.mjs       # 21 checks with the TS validator
```

| Check | Measured result |
| --- | --- |
| Published IAPWS R6-95(2018) values: table 6 (9 derivatives of φ at 500 K, 838.025 kg/m³), table 7 (P, c_v, w, s in 11 states), table 8 (Psat, ρ′, ρ″, h′, h″, s′, s″ at 275, 450, 625 K) | 74 values, maximum relative error **3.8e-9** (the published values have 9 digits) |
| IF97 as an independent formulation (regions 1, 2 and 3; region 3 verified earlier against IF97's table 33), 187 liquid, vapor and supercritical states over the whole domain | \|Δv/v\| ≤ **4.9e-4**, \|Δh\| ≤ **0.51 kJ/kg**, \|Δs\| ≤ **0.83 J/(kg·K)**; the phase matches the IF97 region in every case. Test tolerances: 1e-3, 1 kJ/kg, 2 J/(kg·K) |
| h = u + Pv, g = h − Ts, the Maxwell relation (∂s/∂ρ)_T = −(∂P/∂T)_ρ/ρ², (∂s/∂T)_P = c_p/T, c_p > c_v > 0 | in 6 states of the three families |
| Stability | rejects the 6 forced metastable states; accepts at Psat·(1 ± 3e-6); rejects Psat·(1, 1 ± 5e-7) as saturation |
| Contract | 29 rejections with state, code, path, owner and echo of the id; the units K/°C/°F and Pa/kPa/bar give the same state; mass basis; null present in the serialization; JSON without NaN |
| 25 °C, 1 bar | ρ = 997.047 kg/m³, h = 104.92 kJ/kg, s = 0.3672 kJ/(kg·K), c_p = 4.1813 kJ/(kg·K) |

The examples in `docs/ejemplos/motor-termodinamica-*` come from running the endpoints; no number is written by hand. Cases: liquid at 25 °C, vapor at 100 °C and 1 atm, compressed liquid 600 K/50 MPa with a single-phase policy, supercritical 900 K/50 MPa, undetermined saturation, incompatible phase, critical region and PH not supported.

The two references are not independent in the strong physical sense: IF97 is fitted to IAPWS-95. What they provide is independence of **implementation and functional form** (another equation, other regions, another density solution), enough to detect errors of branch, units or reference. The experimental validity of IAPWS-95 is what its publication documents.

---

## For Codex

- **Routes**: `GET /motor/termodinamica/capacidades` and `POST /motor/termodinamica/evaluar`, as `servicioTermodinamica.ts` expects. Responses with the exact shape of revision 1; the optional fields (`cp`, `cv`, `motivo`, `alternativas`, `cas`) are **omitted** when they do not apply, never sent as null; `evaluacion: null` and `residuo: null` are explicit.
- **Published capability**: `agua-iapws95` v`1`, `especificaciones: ["TP"]`, `fases: ["liquido","vapor","fluido"]`, `componentesCAS: ["7732-18-5"]`, `dinamica: false`.
- **Finding in `validarRespuestaEstado`**: if the request does not declare `masaMolar`, the validator accepts any `masaMolarKgMol > 0` from the server (it only cross-checks when the user declares it). A response with 0.018 kg/mol for water would pass. Optional: cross-check against a catalog, or at least require consistency with the CAS.
- **18.015 g/mol is rejected** (tolerance 1e-7, yours). If the interface fills in rounded molar masses, it is better not to send them, or to send the model's.
- **`proveedorId`** with this model → `no_soportado`. Send only the CAS.
- **Saturation** without `alternativas` until PH/UV/UP are published; the interface can read `MOTOR_ESTADO_SATURACION_INDETERMINADA` and explain that an energy or volume specification is missing.

## Pending (not published)

- **H2/H4 first need the assembly's `validar`/`resolver` contract** (contract §C): differential and algebraic states, initialization, count. It has not been started; this delivery's evaluation is called locally (`core.agua_iapws95.evaluar_TP`) and is designed so the numerical coordinator can invoke it without HTTP.
- **H3**: saturation with a phase fraction, PH/UV/UP for water (inversion in T, ρ; TPD at the corresponding specification, not G), reconstruction of U/V. Then `alternativas` and the `equilibrio` check will be added.
- Derivatives for H2 already calculated and not published in revision 1: (∂P/∂ρ)_T, (∂P/∂T)_ρ, w. Publishing them requires extending the contract.
- Critical region, T > 1073.15 K and P > 100 MPa: out until there is specific verification.
- Mixtures (H5/H6), solids, reaction and electrolytes: no model; any CAS other than water comes out `no_soportado`.
