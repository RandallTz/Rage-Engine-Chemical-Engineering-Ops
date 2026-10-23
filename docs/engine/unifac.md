# UNIFAC in the engine (F0, U0–U8)

Delivery of [docs/history/frontend/contract-claude-unifac-engine.md](../history/frontend/contract-claude-unifac-engine.md), in the format of [docs/history/frontend/coordination-claude-codex-engine.md](../history/frontend/coordination-claude-codex-engine.md). Changes in core, backend, tests, canonical contracts and `docs/`. `frontend/`, `/laboratorio` and `thermodynamics/proveedor.py` were not touched. No commit, push or deployment. No dependency was updated and no data file was modified.

**Reload:** restart the service (`uvicorn backend.main:app`). Afterwards, `GET /motor/termodinamica/capacidades` must list `unifac-original-public`, `unifac-dortmund-public` and `unifac-original-lle-public`, and `GET /motor/ensamblajes/capacidades?revision=2` must include those three packages with the field `coberturaGrupos`. The routes do not change.

## 1. State by milestone

| Milestone | State | Evidence |
|---|---|---|
| F0 concurrent start-up | **Backend verifiable** | Failure reproduced (7 of 8 cold start-ups with threads) and fixed; 0 failures in the suite's rounds (§2) |
| U0 audit | **Backend verifiable** | Coverage of the 7 species and the 21 pairs in both variants; data decisions (§3) |
| U1 original adapter | **Backend verifiable** | ln γ against thermo ≤ 3e-15; h^E, s^E, Cp^E; identities (§4) |
| U2 TP and stability | **Backend verifiable** | L–V against an independent γ–φ flash with N = 2, 4, 5 and 7; L–L with N = 2 and 4; L–L–V with N = 5 (§5) |
| U3 energy and inversions | **Backend verifiable** | PH/UP/UV with N = 2, 5 and 7; L–L–V plateau; UV of a full liquid rejected (§6) |
| U4 dynamics | **Backend verifiable** | Heating with N = 2, 4 and 5; rigid; network with reversal and an incoming species; adiabatic mixing; per-phase extraction; single-phase policy; missing data (§7) |
| U5 API, diagrams and metadata | **Backend verifiable** | Three routes, `coberturaGrupos`, codes of its own, fingerprint, concurrency (§8) |
| U6 Dortmund | **Backend verifiable** | A package of its own; tests U1–U5 repeated where they apply (§9) |
| U7 table dedicated to LLE | **Backend verifiable**, with partial coverage | 6 of 7 species. **Methanol stays blocked by data**: the table has no CH3OH group (§10) |
| U8 delivery | this document, examples, verifier, benchmark and regression (§11–§14) | |

No row moves to "Integrated and checked": Codex's integration is missing. (The roadmap records F1A/F1B as integrated and F1C as integrated with partial coverage: [docs/engine/multiphysics-roadmap.md](multiphysics-roadmap.md).)

## 2. F0 · Concurrent start-up

**Reproduction.** With 8 threads and a freshly started process, 7 of 8 start-ups failed. The errors were:

- `PiecewiseHeatCapacity ... append`, when lazily loading `chemicals`' tables;
- `KeyError: 'ChemSep NRTL'`, when lazily loading `thermo`'s IPDB.

Those loaders fill global variables and are not thread-safe.

**Fix.** The reentrant lock `core/mezclas_datos.CARGA_DATOS` was added. It is taken by:

- `especie(cas)`;
- `parametros_nrtl`;
- `_pares_nrtl` (in the v2 capabilities);
- loading and querying the UNIFAC tables (`core/unifac.tablas` and `asignacion`).

No value changes: it only orders the first load.

**Verification:**

- three rounds of 12 threads without errors;
- in `tests/validar_motor_unifac.py`, section 5: a new process, 12 threads with 12 different mixtures (UNIFAC and NRTL), two rounds. The concurrent results are **bit-for-bit equal** to those obtained in isolation in the same process.

## 3. U0 · Audit and decisions

### 3.1 Pinned data

| Variant | Equations | Subgroups (R, Q) | Interactions | Assignments |
|---|---|---|---|---|
| `original` | Fredenslund, Jones and Prausnitz (1975). Staverman–Guggenheim combinatorial with z = 10; Ψ = exp(−a_mn/T) | `UFSG` (thermo 0.6.1) | `UNIFAC original interaction parameters.tsv`, sha256 `2599fa3a…` | DDBST (`DDBST UNIFAC assignments.tsv`, sha256 `2ce711b9…`), model `UNIFAC` |
| `dortmund` | Weidlich and Gmehling (1987). Combinatorial with r^(3/4); Ψ = exp(−(a + bT + cT²)/T) | `DOUFSG` | `UNIFAC modified Dortmund interaction parameters.tsv` (DOUFIP2016), sha256 `0826be…` | DDBST, model `MODIFIED_UNIFAC` |
| `lle` | Magnussen, Rasmussen and Fredenslund (1981): the same equations as the original | `LLEUFSG` | `UNIFAC LLE interaction parameters.tsv` | Translation of the original DDBST assignment (§10) |

Everything comes from the files `thermo` 0.6.1 distributes. The full sha256 values are in `coberturaGrupos.datos` and in the fingerprint.

**Use of `thermo`.** Its tables are read, but its `UNIFAC` objects are not used for calculating: they mutate T and x internally and are not thread-safe. The project's own implementation (`core/unifac.py`) is vectorized and immutable, and accepts complex T for complex-step differentiation. `thermo`'s implementation is used as an **independent cross-check** in the tests.

**Discarded data:**

- `thermo` also loads UNIFAC 2.0 (`UF2IP`), whose parameters come from "matrix completion". It is not used, as the contract asks.
- Nor is UNIFAC used to complete missing NRTL pairs.

### 3.2 Coverage of the catalog (7 species)

| Species | original | dortmund | lle |
|---|---|---|---|
| water | H2O | H2O | H2O (17) |
| ethanol | CH3 + CH2 + OH | CH3 + CH2 + OH(P) | CH3 + CH2 + OH |
| benzene | 6 ACH | 6 ACH | 6 ACH |
| toluene | 5 ACH + ACCH3 | 5 ACH + ACCH3 | 5 ACH + ACCH3 |
| 1-butanol | CH3 + 3 CH2 + OH | CH3 + 3 CH2 + OH(P) | CH3 + 3 CH2 + OH |
| ethyl acetate | CH3 + CH2 + CH3COO | same | CH3 + CH2 + CH3COO (25) |
| methanol | CH3OH | CH3OH | **no group** (§10) |

Among the main groups present, no directed interaction is missing in any of the three variants. So any subset of species with an assignment is covered. This is published as a datum and checked: `coberturaGrupos.interaccionesDirigidasFaltantes` is an empty list.

### 3.3 Decisions

- **Package IDs:** `unifac-original-public`, `unifac-dortmund-public` and `unifac-original-lle-public`, version `1` (the ones the contract proposed). The version is the package's. The edition of the data goes in the fingerprint.
- **Variant, tables and assignments are inseparable.** Each package fixes its variant. The assignments of one variant are not used with the tables of another.
- **Missing data:** a missing interaction between two present main groups is a diagnosis, never a zero. Within one main group a = 0 by definition of the model. An a_mn = 0 published in the table is a datum and is used as such (section 5 of the suite).
- **Evidence:** L–V and L–L are published as `cualitativa` in the three packages. They are group-contribution predictions and no parameter was fitted here, even if some point matches the literature. This also applies to the LLE table.

## 4. U1 · Adapter and local consistency

`core/unifac.LiquidoUNIFAC(cas, variante)`:

- `lngamma`, `lngamma_lote` and `gE_RT` are finite at infinite dilution (x_i = 0), with the pure components' lnΓ precalculated;
- `subconjunto(idx)` reuses tables and assignments;
- `identidad()` goes into the fingerprint: variant, sha256 of the tables, assignments by sorted CAS, R and Q of the subgroups used and the values of the interactions used.

`core/mezclas.Sistema` integrates the adapter:

- `_modelo_sub` uses `subconjunto` for the active species;
- `dgE_dT` (complex step) is the same as for NRTL;
- with a single species the ideal liquid is used (g^E = 0).

| Test | Result |
|---|---|
| ln γ against `thermo.unifac.UNIFAC.from_subgroups` (same tables), N = 2 to 7, 15 points per variant | ≤ 3e-15 (original and Dortmund); 3.8e-15 (LLE, N = 6) |
| h^E by complex step against thermo's `HE()` | ≤ 1e-8 relative |
| s^E against `SE()` and Cp^E = −T ∂²g^E/∂T² against `CpE()` (N = 4) | ≤ 1e-7 and 1e-5 relative |
| Gibbs–Duhem, N = 7, random directions | < 1e-7 |
| ∂g^E/∂T by complex step against central differences | < 1e-6 relative |
| ln γ_i = 0 in the pure species; read-only arrays; a subset equal to rebuilding | exact |

## 5. U2 · TP, stability and split

Independent reference: a γ–φ flash by successive substitution with Rachford–Rice, using `thermo`'s γ and the package's same Psat and Poynting; for L–L, isoactivity with `thermo`'s γ. The engine, instead, minimizes G and certifies with the tangent-plane test.

| Case (1 atm) | Result |
|---|---|
| ethanol–water at 352 and 355 K | L–V against the reference to 1e-8 in β, x and y; the single-phase states coincide |
| N = 4 (benzene, toluene, ethanol, methanol) at 346 K; N = 5 at 344 K; N = 7 at 351 K, equimolar | L–V to 1e-8 |
| N = 5 (benzene, toluene, ethanol, methanol, water) at 341 K | **L–L–V** certified (tm and μ ≤ tolerances) |
| water/1-butanol at 293–353 K | L–L against isoactivity to 1e-8 |
| N = 4 (water, ethanol, acetate, methanol), 300 K, z = (0.7, 0.04, 0.24, 0.02) | L–L against isoactivity to 1e-8 |
| Absences, traces (1e-6, 1e-9, 1e-12), scale (1e-6 and 1e6), 3 permutations, flash seeds | the same as with NRTL: same state and same fingerprint; reconstruction per species < 1e-9 relative |
| General stability (N ≥ 4) | deterministic with the fixed seed; the homogeneous L–L is rejected with tm < 0 |
| Phase cap and T outside the common domain | rejections `tope_fases` and `fuera_de_dominio` |

**Experimental cross-check (prediction, without fitting).** Mutual solubility of water/1-butanol in g/100 g (butanol in the aqueous phase / water in the organic phase) against IUPAC-NIST SDS vol. 15:

| T (K) | IUPAC | original | Dortmund | LLE |
|---|---|---|---|---|
| 293.15 | 7.8 / 20.0 | 7.33 / 20.56 | 11.19 / 11.67 | 6.92 / 21.62 |
| 298.15 | 7.4 / 20.3 | 7.62 / 20.69 | 11.01 / 11.82 | 7.21 / 21.76 |
| 313.15 | 6.6 / 21.4 | 8.49 / 21.12 | 10.67 / 12.50 | 8.12 / 22.21 |
| 323.15 | 6.4 / 22.4 | 9.10 / 21.43 | 10.57 / 13.12 | outside the domain |
| 353.15 | 7.0 / 27.5 | 10.93 / 22.42 | 10.77 / 15.81 | outside the domain |

- The **original** gets it right at 293–298 K, with an error below 0.6 g/100 g, and worsens with T.
- **Dortmund** brings the phases too close together.
- The **LLE table** does not improve this pair.

It is published as is; nothing is refitted.

### 5.1 Shared fix: retrying the TP next to an invariant point

When sweeping water/butanol with original UNIFAC, a strip of about 1e-6 K appeared, just above the heteroazeotrope (366.1793 K at 1 atm with z = 0.75), in which `equilibrio_TP` did not certify (tm = −3.8e-8). The phase-addition sequence started from the vapor and stopped at V + L_org: the aqueous trial phase had a tm of order 1e-8 and the 3-phase minimization cancelled it.

Now, **only if certification fails**, the sequence is repeated from the other single candidate phases and only a certified state is accepted. With that the strip is resolved: L–L up to T_het and V–L from there. The normal path does not change: it certifies at the first attempt and gives the same numbers (§13).

### 5.2 Shared fix: split seeds when the new phase is incipient

Case: LLE table, N = 6 equimolar at 300 K. The stability test gave tm = −0.012, but `_minimizar_G` went back to the trivial solution, in which the new phase merges with the existing one. The equilibrium split is small (the aqueous phase takes 0.5 % of the inventory) and the 10 % seed oversizes it.

Now, **only if the first attempt collapses**, it retries with the new phase already formed:

- fractions β = 1e-3, 1e-4, 0.05, 0.2 and 0.5 of the inventory, with the trial composition;
- without exceeding 90 % of the donor phase.

The case is certified (tm and μ ≈ 3e-15) and matches the independent isoactivity. The normal path does not change.

## 6. U3 · Energy and inversions

| Test | Result |
|---|---|
| g = h − T s = Σ x μ (N = 4) | < 1e-9 relative |
| Partial molar enthalpies against h_i − R T² ∂ln γ_i/∂T (differences of H·n) | < 1e-6 relative |
| h^E, s^E and Cp^E of the phase against thermo | see §4 |
| PH, UP and UV with N = 2 (355 K), 5 (341 K, L–L–V) and 7 (351 K) | T < 1e-6 K; H, V and composition of a single split; the same set of phases |
| water/butanol PH between 360 and 380 K (the heteroazeotrope's plateau) | exact H and a stable state |
| UV of the full incompressible liquid (N = 5) | rejection `no_soportado`: the pressure is not identifiable |

The heat of mixing enters only once: it is in the phase's h (h_i^pure + h^E).

## 7. U4 · Dynamics

The same `Sistema` and the same coordinator as with ideal and NRTL. There is no branch per package.

| Case | Result |
|---|---|
| Heating at prescribed P (100 W) with N = 2, 4 and 5 | H = H0 + Q t; bubble point against the static flash to 1e-5 relative; certified; `procedenciaModelo` with the UNIFAC fingerprint |
| Rigid L–V with N = 4 | U = U0 + Q t, constant V, certified |
| Two volumes with N = 5: a stream with negative flow (the donor is B), thermal contact, water entering A from zero | conservation per species < 1e-10; the donor's composition kept; second law met |
| Adiabatic isobaric ethanol/water mixing | constant total H; the heat of mixing changes T; S_gen ≥ 0 |
| Vapor extraction until it runs out | terminal stop `fase_ausente` |
| Single-phase policy | stop at the bubble point (`MOTOR_ENS_DETENIDO_CAMBIO_FASE_PROHIBIDO`), nascent vapor < 1e-8 and a **certified** trajectory (see §7.1) |
| Simulated missing assignment | `MOTOR_ENS_UNIFAC_ASIGNACION_AUSENTE`, without results |

### 7.1 Shared fix: dV/dt at a phase-change kink

With the single-phase policy, the trajectories that stopped at the bubble point came out "not certified", also with ideal and NRTL (the defect already existed): `mecanica.A.trabajo` gave 726 against a tolerance of 1.

**Cause.** The work is integrated with dV/dt calculated by a central difference of V(H, P, n). Within ε of the kink, V(t + ε) already contains vapor, and the incompressible liquid seemed to expand. When the trajectory crosses the kink, that error was compensated by the strip on the other side; when it stops at it, it is not.

**Fix** (`core/ensamblaje_red._dVdt`). If any of the difference's points has a different phase set from that of the **stretch being integrated** (`firmas_tramo`), the three-point difference on the side that keeps that set is used.

| Package | Residual before | Residual now |
|---|---|---|
| ideal | 726 | certifies |
| UNIFAC | 726 | certifies |
| NRTL | 726 | ~1.1, still above the tolerance of 1 |

**What remains.** The remaining residual is P·Δv·n of the nascent phase between the real kink and t_e. The location has a resolution of 1e-9·tf (`core/ensamblaje_red.RES_EVENTO`).

**Attempt to refine it to 1e-12·tf.** With NRTL it does bring the residual down to 0.06. But the sample published at t_e sometimes lacks the nascent phase (about 1e-11 mol) and the event comes out without `faseIds`. It happens when crossing the kink and, with ideal and UNIFAC, also when stopping at it.

**Measured cause.** The bisection and the publication evaluate the same y with the same seeded flash, but with different seeds (the state at the start of the step against the previous sample). For nascent phases of that size they do not decide the same way. It was reverted to 1e-9. A correct fix requires the bisection to use the same criterion as the publication.

That was the historical limit (§15). The following correction supersedes this specific incident.

**Nonspatial consolidation, 20 October 2026.** Located native-network phase events now retain the numerical flash context used to find them. Certified publication starts from that event state and rejects a phase-signature disagreement instead of publishing an event without the corresponding phase IDs. A nearly coincident scheduled sample is replaced by the exact located event time. With that consistent context, event localization can use 1e-12 of the horizon (existing absolute floor 1e-12 s), without changing phase-presence, stability, chemical-potential or work-certificate tolerances. The independent auxiliary integral of P dV/dt is retained.

| Package | Original scaled work residual | Corrected residual over HTTP | Certificate |
|---|---:|---:|---|
| NRTL | 1.1051195827 | 0.0534933144 | passes |
| Original UNIFAC | 0.6301143844 | 0.0174497900 | passes |
| Ideal mixture | 0.0944209054 | 0.0275875410 | passes |

The tolerance remains 1. The same original requests, frontend strict reader and phase-event IDs are used; NRTL parameters/coverage are unchanged. Backend 8004 was restarted with explicit user authorization and the corrected requests checked live. Regression coverage includes Dortmund, the LLE table within its T/P domain, cooling, inventory scaling, output sampling/horizon changes, exact event sample times and deliberately corrupted auxiliary work that still fails certification. This resolves the reproduced F9-R1 seed/publication/work defect within that scope, not the general problem of phases appearing and disappearing between watched points. Broader search reliability and performance remain in the existing roadmap.

## 8. U5 · API, diagrams and metadata

### 8.1 Routes and fields

There are no new routes. Everything is additive.

- **`GET /motor/termodinamica/capacidades`**: three more models, with `componentesCAS` equal to the species with an assignment in that variant. The LLE package publishes `dominio.T = [283.15, 313.15]`.
- **`GET /motor/ensamblajes/capacidades?revision=2`**:
  - the three packages, with L–V and L–L combinations `cualitativa`;
  - **without `pares`**: no molecular pairs are published because the model does not use them;
  - with **`coberturaGrupos`**, of type `CoberturaGrupos` (`docs/contratos/contratoContribucionGrupos.ts`): variant, data with sha256, subgroups per species (id, name, main group, count, provenance), `especiesSinAsignacion` and `interaccionesDirigidasFaltantes`;
  - `tamanos.contrastados` with the sizes actually tested per package.
- **`GET /motor/termodinamica/diagramas/capacidades`**: the same packages, with `pares: null` and the same `coberturaGrupos`.
- **Evaluation, assembly and diagram responses**: no new fields. The model's fingerprint (`huellaModelo`, `procedenciaModelo[].huella`) includes the UNIFAC identity.

### 8.2 Diagnostics of missing data

| Situation | Point | Assembly | Diagrams |
|---|---|---|---|
| Species without a group assignment in the variant | `MOTOR_ESTADO_UNIFAC_ASIGNACION_AUSENTE` | `MOTOR_ENS_UNIFAC_ASIGNACION_AUSENTE` | `MOTOR_DIAG_UNIFAC_ASIGNACION_AUSENTE` |
| An assigned subgroup that does not exist in the table | `MOTOR_ESTADO_UNIFAC_GRUPO_DESCONOCIDO` | `MOTOR_ENS_…` | `MOTOR_DIAG_…` |
| Missing directed interaction | `MOTOR_ESTADO_UNIFAC_INTERACCION_AUSENTE` | `MOTOR_ENS_…` | `MOTOR_DIAG_…` |

All three are `no_soportado`, without state or results. The message names the species, subgroup or main groups. `PARAMETRO_AUSENTE` is kept for NRTL. A species with groups but without pure-component data (e.g. acetone, which has a DDBST assignment) is rejected as before: there is no Psat or cp.

### 8.3 Fingerprint

The fingerprint changes if any of these change:

- the sha256 of a table;
- a value of an interaction used;
- the variant.

It does not change with:

- the order of the species;
- the names or symbols of the components;
- the request's units (P in bar against Pa).

All of this is checked in sections 0 and 5 of the suite.

### 8.4 Diagrams (Txy of ethanol–water at 1 atm)

| Package | Azeotrope | Literature | Pure ends |
|---|---|---|---|
| original | 78.04 °C, x = 0.896 | 78.15 °C, x = 0.894 | 100.01 °C and 78.29 °C (the catalog's Psat) |
| Dortmund | 78.13 °C, x = 0.899 | 78.15 °C, x = 0.894 | 100.01 °C and 78.29 °C |

## 9. U6 · Dortmund

Package `unifac-dortmund-public` with its own assignments (primary alcohols with OH(P)) and its DOUFIP2016 table.

**Tests U1 to U5 repeated:**

- adapter against thermo (`version=1`), 2.1e-15;
- L–V with N = 2, 4 and 7 against the independent flash;
- water/butanol L–L against isoactivity;
- diagram with an azeotrope;
- point service with N = 4;
- heatings with N = 2 and 4, certified;
- a fingerprint different from the original's with the same species.

**Comparison with the original on the same declared data:**

- azeotrope: §8.4;
- water/butanol LLE: §5. Dortmund predicts this pair much worse. It does not replace or change the original.

## 10. U7 · Table dedicated to LLE (Magnussen et al., 1981)

**Audit.**

- `thermo` distributes the subgroup table `LLEUFSG` and the interactions `UNIFAC LLE interaction parameters.tsv` (Magnussen, Rasmussen and Fredenslund, *Ind. Eng. Chem. Process Des. Dev.* 20 (1981) 331, doi:10.1021/i200013a024).
- **There are no DDBST assignments for this table**, and its subgroup numbering is different: H2O is 16 in the original and 17 in LLE; 15 is CH3OH in the original and P1 (1-propanol) in LLE.

**Decision: a generic translation, not per mixture.** Each subgroup of the original DDBST assignment is replaced by the **only** LLE subgroup with the same name and the same R and Q, that is, the same chemical definition. If it does not exist or is not unique, there is no assignment.

**Result:**

- 6 of 7 species translated;
- **methanol blocked by data**: the LLE table has no CH3OH group, and it is not approximated as CH3 + OH;
- no missing interaction among the groups of the 6 species.

**Domain.** The table was fitted with LLE data between 10 and 40 °C. The package declares T ∈ [283.15, 313.15] K as its domain, through the same mechanism as the NRTL-LLE package. Outside that interval it answers `fuera_de_dominio`.

| Test | Result |
|---|---|
| ln γ against thermo with `LLEUFSG`/`LLEUFIP`, N = 6 | 3.8e-15 |
| water/butanol at 293, 298 and 313 K | L–L against isoactivity to 1e-8; against IUPAC, §5 |
| N = 4 (water, ethanol, acetate, butanol) at 300 K | L–L against isoactivity |
| N = 6 equimolar at 300 K | incipient aqueous phase (0.5 %), certified (§5.2) |
| L–V within the domain: Pxy of ethanol–water at 298.15 K | complete; between 3 and 8 % below the original; **without the azeotrope** that the original (x = 0.969) and NRTL (x = 0.890) predict |
| Dynamics: butanol entering water at 298 K (adiabatic, constant P) | the second liquid appears; constant H; certified |
| Methanol | `MOTOR_ESTADO_UNIFAC_ASIGNACION_AUSENTE` (a real rejection, not simulated) |

**Limits.**

- There is no experimental cross-check of L–V within the domain.
- The package is not used to "correct" the split of another package: each state uses a single table in all its phases, L–L–V included.

## 11. Contract

- **New** `docs/contratos/contratoContribucionGrupos.ts`, with the types `CoberturaGrupos`, `DatosContribucionGrupos`, `VarianteUNIFAC` and `CodigoDatoAusente`. It is specific to the UNIFAC family: the other packages do not publish this field.
- `contratoEnsamblajeV2.ts`: `paquetes[].coberturaGrupos?` (additive, without a new revision).
- `contratoDiagramasEquilibrio.ts`: `paquetes[].coberturaGrupos?`. It is made explicit that `pares: null` also corresponds to a group-contribution package.

**Implemented and published:** all of the above. **Proposed and not implemented:** nothing.

## 12. Examples and verifier

`docs/ejemplos/motor-unifac/` is generated by `python tests/generar_ejemplos_motor_unifac.py` from the real routes (ASGI). It contains:

- **capabilities** of the three routes;
- **point states:**
  - original: L–V with N = 2, water/butanol L–L, L–L with N = 4, L–L–V with N = 5, L–V with N = 7;
  - Dortmund: N = 4;
  - LLE: N = 2 and N = 6;
- **assemblies:**
  - heating with N = 2 and N = 4;
  - a network with N = 5 and an incoming species;
  - a stopped single-phase policy;
  - Dortmund with N = 4;
  - LLE mixing of water and butanol;
- **diagrams:** Txy and Pxy of ethanol–water; Txy of water–butanol; Dortmund Txy; LLE Pxy;
- **rejections** (with `rechazo` in the name):
  - real: methanol with the LLE table; T outside the LLE domain;
  - **simulated** (with `simulado` in the name): missing assignment and missing interaction. The catalog is complete and there is no real case; they are provoked within the generator's process by temporarily replacing the assignment or the table, without touching data files.

`node tests/verificar_contrato_unifac.mjs`:

- compiles every example against the canonical types, with negative controls;
- runs each state (point, and per volume and sample) through the frontend's `validarRespuestaEstado`;
- checks that the coverage is the same in both routes, that `componentesCAS` matches the assigned species, the LLE domain, the `cualitativa` evidence, the rejection codes and the fingerprint in `procedenciaModelo`.

## 13. Published changes and comparison with the earlier examples

**18 October 2026.** `motor-ensamblaje-v2-resolver-unifac-red-5-especie-entrante-respuesta.json` was regenerated. A's second liquid phase moves from 141.41 s to 113.58592 s, the independent stability limit, after fixing the acceptance of a step without an event in `core/ensamblaje_red.py` ([docs/engine/engine-map.md](engine-map.md) §6). No other UNIFAC example changed.

`docs/ejemplos/` was copied before the changes and regenerated with the engine's four generators:

- `generar_ejemplos_motor_termodinamica`;
- `generar_ejemplos_motor_ensamblaje_v2`;
- `generar_ejemplos_motor_n_componentes`;
- `generar_ejemplos_motor_diagramas`.

Then they were compared number by number.

**Capabilities.** Only additive changes:

- 3 more packages in v2, in diagrams and in the point service;
- `tamanos.contrastados` for them.

In `motor-termodinamica-capacidades.json`, the UNIFAC models are inserted before `agua-iapws95-hielo-ih`, which moves from position 4 to 7. A reader that looks up by `id` is not affected.

**Point states and diagrams.** No numerical changes, except:

- `tmMinimo` of order 1e-16 to 1e-15 (rounding of the certificate, always far below TOL_TM);
- `cobertura.presupuesto.segundos` (wall time).

**Trajectories that cross a phase kink.** They change only because of the fix in §7.1:

| Example | Work W at the end | Residual `mecanica.A.trabajo` | Other series | Events |
|---|---|---|---|---|
| v2: ethanol–water heating | 3291.7467 → 3291.7532 J (2e-6 relative) | 0.198 → 0.0023 | ≤ 5e-7 relative | shift ≤ 2e-7 s |
| N: NRTL with 4 species | 2246.47328 → 2246.47317 J | 0.029 → 0.011 | ≤ 2e-7 relative | ≤ 2e-7 s |
| N: ideal with 5 species | 2150.12465 → 2150.12461 J | 0.026 → 9.5e-5 | ≤ 2e-7 relative | ≤ 2e-7 s |

The energy residuals stay several orders of magnitude below their tolerance: the largest is 1.4e-5 against 10, in NRTL with 4 species, previously 3.4e-7.

The other two shared fixes (§5.1 and §5.2) act only when the first attempt does not certify, and change no example.

## 14. Performance

`python tests/benchmark_unifac.py`. Machine: AMD64 Family 25 Model 120, Python 3.12.10, numpy 1.26.4. Median of 5 repetitions (3 in PH and UV), at 1 atm, with 1 mol equimolar (except the L–L with N = 4: z = 0.7/0.04/0.24/0.02 at 300 K).

**Cold start** (import, load the UNIFAC tables and do the first ethanol–water TP): 1.77 s.

| Package | N | Phases | TP (s) | Stability (s) | PH (s) | UV (s) |
|---|---|---|---|---|---|---|
| UNIFAC original | 2 | V+L | 0.016 | 0.005 | 0.19 | 2.1 |
| NRTL | 2 | V+L | 0.009 | 0.002 | 0.09 | 1.0 |
| UNIFAC original | 4 | L+L | 0.058 | 0.008 | — | — |
| NRTL | 4 | L+L | 0.31 | 0.12 | — | — |
| UNIFAC original | 4 | V+L | 0.031 | 0.008 | 0.40 | 3.2 |
| NRTL | 4 | V+L | 0.025 | 0.007 | 0.24 | 2.2 |
| UNIFAC original | 5 | V+L+L | 0.23 | 0.012 | 2.2 | 25 |
| UNIFAC original | 7 | V+L | 0.058 | 0.24 | 2.2 | 33 |
| UNIFAC Dortmund | 7 | V+L | 0.045 | 0.018 | 1.8 | 21 |

**Trajectory** (heating with 100 W from 330 K, 300 s, 6 samples, rtol 1e-8):

| Package | N = 2 | N = 4 |
|---|---|---|
| UNIFAC | 27 s | 34 s |
| NRTL | 8.5 s | 23 s |

UV is the expensive operation: it nests TV and TP. With N = 5 and 7 it takes 20 to 33 s per state.

**After the benchmark** a cache of the last real T was added to `LiquidoUNIFAC`: Ψ(T) and the pure components' lnΓ depend only on T. The cache is not used with complex T. Effects:

- bit-for-bit identical results;
- ln γ with N = 7: from ~55 µs to 27 µs per call;
- profiled ethanol–water heating trajectory: from 22 s to 18.9 s.

**Why UNIFAC takes about 3 times longer than NRTL in trajectories:**

- the cost of ln γ: ~175 000 evaluations per trajectory;
- about 180 of the ~1 100 seeded Newtons do not converge and fall back to the full flash.

The chord method was tried in that Newton (reusing the Jacobian). It gained only 5 % and changed the numbers in the last bit, so it was discarded.

## 15. Limits (what must not be read as a general capability)

- **Evidence.** The three variants are predictions. `cualitativa` does not mean "validated". The measured errors are in §5, §8.4 and §10.
- **Range of the cross-check.** The experimental cross-check is limited to the ethanol–water azeotrope and the water/butanol LLE. For the other combinations there is only a numerical cross-check, against another implementation with the same tables.
- **Ideal vapor and incompressible liquid**, as in the other mixture packages. P ≤ 5 bar.
- **Cross-checked sizes** (`tamanos.contrastados`):

  | Package | Static | Dynamic |
  |---|---|---|
  | original | 2, 3, 4, 5, 7 | 2, 4, 5 |
  | Dortmund | 2, 3, 4, 5, 7 | 2, 4 |
  | LLE | 2, 4, 6 | 2 |

- **LLE table:** only between 10 and 40 °C. Methanol blocked.
- **Work residual with NRTL** in a trajectory stopped at the kink: it stays at ~1.1 against 1 (§7.1).
- **Diagrams:** binary and L–V. L–L is identified as meeting another phase, but it is not plotted.

## 16. Regression, comparison of examples and performance

Run from the root on 16 October 2026, after all the changes:

| Command | Result | Exit | Time |
|---|---|---|---|
| `python tests/validar_motor_unifac.py` | OK, 136 | 0 | 613 s |
| `python tests/validar_motor_termodinamica.py` | OK, 585 | 0 | 7 s |
| `python tests/validar_motor_termodinamica_h3.py` | OK, 3729 | 0 | 26 s |
| `python tests/validar_motor_ensamblaje.py` | OK, 245 | 0 | 99 s |
| `python tests/validar_motor_ensamblaje_v2.py` | OK, 114 | 0 | 126 s |
| `python tests/validar_motor_consolidacion_v2.py` | OK, 128 | 0 | 133 s |
| `python tests/validar_motor_n_componentes.py` | OK, 82 | 0 | 267 s |
| `python tests/validar_motor_diagramas_equilibrio.py` | OK, 78 | 0 | 31 s |
| `node tests/verificar_contrato_unifac.mjs` | OK: 7 assemblies (47 states), 12 point states, 6 diagrams | 0 | |
| `node tests/verificar_contrato_ensamblaje_v2.mjs` | OK: 10 pairs, 60 states, 12 point states | 0 | |
| `node tests/verificar_contrato_diagramas.mjs` | OK: 11 pairs, 285 points | 0 | |
| `node tests/verificar_contrato_motor_termodinamica.mjs` | OK, 35 | 0 | |
| `node tests/verificar_contrato_ensamblaje.mjs` | OK: 13 pairs, 175 states | 0 | |
| `npm run test:motor-fundamental` (in `frontend/`) | OK; the output includes "101 comprobaciones de cobertura de grupos" from the reader Codex already prepared | 0 | |

The Python suites were run in parallel with the final code, which already includes the T cache. The TS and npm verifiers use the regenerated examples, which the final code reproduces: the cache gives bit-for-bit identical results.

**Note on two failures already fixed.** In an earlier run, the simulated rejections of a missing assignment and an unknown group reached the diagram tracer with `MOTOR_DIAG_COMPONENTE_NO_SOPORTADO` instead of the UNIFAC code. The reason is that the capabilities already filter `componentesCAS` by assignment (§10). Fix in `backend/motor_diagramas.py`: in a group-contribution package, if a species is in the catalog, the rejection is left to the `Sistema`, which gives the precise code. Section 5 and the diagram suite were then repeated (above).

The 40 historical suites (`tests/validar_*.py` outside `validar_motor_*`) were not repeated. None imports `core/mezclas`, `core/unifac`, `core/ensamblaje_red` or the `backend/motor_*` services; this was checked with grep. Those that import `backend.main` only see routes added in earlier sessions, without changes in this one.

### File manifest

**New:**

- `core/unifac.py`
- `docs/contratos/contratoContribucionGrupos.ts`
- this document
- `docs/ejemplos/motor-unifac/` (53 JSON)
- `tests/validar_motor_unifac.py`
- `tests/generar_ejemplos_motor_unifac.py`
- `tests/verificar_contrato_unifac.mjs`
- `tests/benchmark_unifac.py`

**Modified:**

| File | Change |
|---|---|
| `core/mezclas.py` | UNIFAC packages, `FaltaParametro.codigo`, F0 lock, TP retry (§5.1), split seeds (§5.2), fingerprint, LLE domain |
| `core/mezclas_datos.py` | F0 lock |
| `core/ensamblaje_red.py` | one-sided dV/dt (§7.1) |
| `backend/motor_mezclas.py` | Models, codes, domain and species per variant |
| `backend/motor_ensamblaje_v2.py` | Evidence, `coberturaGrupos`, sizes, codes, lock |
| `backend/motor_diagramas.py` | `coberturaGrupos`, codes, membership in group packages |
| `docs/contratos/contratoEnsamblajeV2.ts` | `coberturaGrupos?` |
| `docs/contratos/contratoDiagramasEquilibrio.ts` | `coberturaGrupos?` |
| `tests/validar_motor_termodinamica.py`, `tests/validar_motor_ensamblaje_v2.py`, `tests/validar_motor_diagramas_equilibrio.py` | List of published models extended with the three packages |
| `docs/ejemplos/` (root, `motor-v2/`, `motor-n-componentes/`, `motor-diagramas/`) | Regenerated (§13) |

`backend/main.py` was not modified in this delivery. Its diff against `main` is the diagram routes added in the earlier delivery.

## 17. Work for Codex

1. Synchronize the copy of `contratoContribucionGrupos.ts` and the `coberturaGrupos?` fields of the assembly v2 and diagram contracts.
2. Strict reading:
   - `coberturaGrupos` can only appear in `unifac-*` packages;
   - `pares` is `undefined` in v2 and `null` in diagrams for those packages;
   - the L–V and L–L evidence is `cualitativa`.
3. Show the groups and the data (sha256, source) in the package's details, not on the main screen. A species in `especiesSinAsignacion` is not offered with that package; methanol with LLE must be shown as "no group in the table", not as a generic error.
4. Explicit choice of variant. Cache and diagram markers are invalidated by fingerprint, never by ID.
5. The diagnostics `*_UNIFAC_ASIGNACION_AUSENTE`, `*_UNIFAC_GRUPO_DESCONOCIDO` and `*_UNIFAC_INTERACCION_AUSENTE` as a missing datum, separate from the variable count.
6. Domain of the LLE package: 283.15–313.15 K. Do not offer T outside that interval with that package.
7. Integration verifier with `docs/ejemplos/motor-unifac/`. The `simulado` examples cannot be reproduced against the real service.


## 18. Property-driven rigid-vessel regression (19 October 2026)

An ordinary input-only water–1-butanol example now exercises original UNIFAC through TV initialization and UV heating, with unrestricted phase policy. One constitutive package produces the changing phase set; the template never chooses an LL, LV or LLV result. The independent `thermo.unifac` reference checks the same public tables, isoactivity, phase amounts, pressure and internal energy. This verifies numerical implementation rather than experimental accuracy.

Generic fixes reject nonfinite/inventory-exceeding logarithmic trials, enforce actual package domains, seed small emerging phases and use the discovered pressure bracket for invariant polishing. No activity model, table, package domain or certificate tolerance is altered. Nine reference/adverse tests and the existing 82-check UNIFAC suite pass. See [workspace inputs, connected outputs and limits](model-workspaces.md#property-driven-phase-discovery-example-19-october-2026); remaining physics is maintained in the existing roadmap.
