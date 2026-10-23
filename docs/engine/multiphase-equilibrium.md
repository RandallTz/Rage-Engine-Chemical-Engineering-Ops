# Multiphase equilibrium engine and assembly v2 (M0–M6)

Delivery of the contract [docs/history/frontend/contract-claude-engine-equilibrium-multiphase.md](../history/frontend/contract-claude-engine-equilibrium-multiphase.md). Backend, core, tests and documentation; the frontend was not touched. No commit or push.

**Reload:** the service must be restarted (`uvicorn backend.main:app`). There are new modules, a new route (`GET /motor/termodinamica/diagrama`) and dispatch by `revision` in `/motor/ensamblajes/*`. `backend/main.py` only receives additions.

## 1. What changes for the integrator

| Surface | Revision 1 (no mandatory changes) | Additive extension |
|---|---|---|
| `GET /motor/termodinamica/capacidades` | `agua-iapws95` stays first and unchanged | + `mezcla-ideal`, `nrtl-chemsep`, `nrtl-lle-agua-butanol`, `agua-iapws95-hielo-ih` |
| `POST /motor/termodinamica/evaluar` | the same for `agua-iapws95` | the same types (`SolicitudEstado`/`RespuestaEstado`) with the new models; `solido` phases and two `liquido` phases |
| `GET /motor/termodinamica/diagrama` | — | new: P–T diagram of the closure with ice |
| `GET /motor/ensamblajes/capacidades` | without a parameter = identical revision 1 | `?revision=2` → `CapacidadesEnsamblajeV2` |
| `POST /motor/ensamblajes/{validar,resolver}` | body with `revision: 1` (or without it) as before | body with `revision: 2` → `SolicitudEnsamblajeV2` |

Revision 2 types: `docs/contratos/contratoEnsamblajeV2.ts` (it imports the frontend's revision 1 types; it does not modify them). The examples in `docs/ejemplos/motor-v2/` (`motor-ensamblaje-v2-*` and `motor-termodinamica-{mezcla,nrtl,lle,hielo}-*`; in a subdirectory so that the revision 1 readers, which walk `docs/ejemplos/motor-ensamblaje-*`, keep seeing only revision 1 responses) come from the endpoints (`python tests/generar_ejemplos_motor_ensamblaje_v2.py`) and are compiled and validated with `node tests/verificar_contrato_ensamblaje_v2.mjs`.

### M0: the `presionPrescrita` inconsistency

In revision 1 (`backend/motor_ensamblaje.py`), `formulacionEnergia.presionPrescrita` must agree with the boundary; when absent, the v1 behaviour is kept. Code `MOTOR_ENS_PRESION_PRESCRITA`: `false` with a `presion_prescrita` boundary; `true` with a rigid boundary without `presionRestriccionId`; `true` without a relation; non-boolean → `invalido`. Tests in `tests/validar_motor_ensamblaje.py` §12.

## 2. Foundation: potentials, references and phases

Each package is built from an explicit Gibbs energy per species and phase; h, s, v and μ come from that function and its derivatives, never from separate sources.

**Mixtures** (`core/mezclas_datos.py`, `core/mezclas.py`):

- Ideal gas per species: `h = s = 0` at 298.15 K and P0 = 1e5 Pa, `cp_ig` from Poling (5th ed.). Ideal-mixture vapor (valid up to 5e5 Pa, the published domain).
- Pure liquid: `g_L = g_ig0(T) + R T ln(Psat/P0) + v_L (P − Psat)` with Wagner's Psat (Poling; McGarry for some) and a constant `v_L` from `thermo` at 298.15 K. That makes g_L consistent with Clapeyron: the heat of vaporization is the one Psat(T) implies, not a separate datum. Incompressible.
- Excess: NRTL with `τ_ij = a_ij + b_ij/T`. `h^E = g^E − T ∂g^E/∂T`, `s^E = −∂g^E/∂T`; the T derivative by complex step (exact to machine precision). The heat of mixing enters h and s: γ is not used only for equilibrium.
- Molar `μ_i` (J/mol); common standard state: pure ideal gas at T and P0. The properties published in `EvaluacionEstado` are still mass-specific, as in revision 1.
- Published reference: `gas-ideal-298.15K-1bar-h0-s0`. IAPWS-95 water uses another one (u = s = 0 of the liquid at the triple point): a stream between volumes with different references is rejected (`MOTOR_ENS_REFERENCIAS_INCOMPATIBLES`); references are not converted.

**Ice** (`core/hielo_ih.py`): the Gibbs energy of IAPWS R10-06(2009) with the "IAPWS-95" constant s0: ice shares the fluid's reference without a shift, so the g of ice and the g of IAPWS-95 are compared directly.

**Phases**: each present phase has an ID (`vapor-1`, `liquido-1`, `liquido-2`, `solido-1`) separate from its type. In point queries the liquids are numbered by decreasing mass density; along a trajectory the IDs are kept by continuity of composition, not by reordering densities. An absent phase has no composition: it is not published and no equality of μ is imposed on it (absent species carry `μ = null`).

## 3. Equilibrium algorithms

**TP** (`Sistema.equilibrio_TP`): the single phase of lowest G → tangent-plane test (vapor by analytical minimum; liquid on a simplex grid with refinement) → if some `tm < −1e-14`, that phase is added and G is minimized (SLSQP) → Newton polishing in `ln n` with the most abundant phase as the remainder → repeat (up to 3 phases). Final certification: `tm ≥ −1e-9` over vapor and liquid with the common μ, `max|μ_i^α − μ_i^β|/(RT) ≤ 1e-10`. If the split does not converge (e.g. 1e-12 K from a boundary the new phase wants to vanish), it is discarded and the earlier set is certified by the tangent-plane test. If nothing certifies, the response is `no_convergente`; an uncertified root is never published.

Robustness added in this delivery: phases that the minimization empties, or brings to the composition of another of the same type, are removed or merged before polishing; if there is no solution with all the phases (three phases of a binary outside its invariant T), the subsets are tried and the one of lowest G that converges is kept.

**PH/UP**: Brent in T along the equilibrium isobar (h and u grow with T). At a jump (pure, exact azeotrope, the LLV of a binary) the plateau is solved: compositions on both sides of the jump, the invariant point polished by Newton in (ln T, compositions) when there are C + 1 phases, and amounts by non-negative least squares with the energy constraint. Certified as in TP.

**TV/UV**: TV by Brent in ln P (with a plateau in P if there is one); UV by a loose search in T with TV and an exact Newton in (T, ln P, ln n^α). An incompressible liquid that fills the volume does not determine P: `no_soportado`.

**Water with ice** (`core/agua_slv.py`): TP = the phase of lowest g; on a curve or at the triple point, TP does not determine the split (`MOTOR_ESTADO_SATURACION_INDETERMINADA`; at the triple point the only alternative is UV). PH/UP follow the sequence of stable phases as T rises, with plateaus by the lever rule. UV = the maximum of S among all the candidates that meet U and V (one phase, two phases on each curve, triple), also certified with minimum g at its T, P. PH at the triple point (three phases, two equations) is underdetermined.

## 4. Packages, data and provenance

| Package | Species | Binary data | Domain | Operations |
|---|---|---|---|---|
| `mezcla-ideal` 1 | water, ethanol, methanol, benzene, toluene, 1-butanol, ethyl acetate | none (Raoult + Poynting) | T envelope of the species (≤ 0.9 Tc), P 100–5e5 Pa | TP, PH, UP, UV (+ internal TV) |
| `nrtl-chemsep` 1 | the same | ChemSep NRTL via `thermo.interaction_parameters.IPDB`; a missing pair → `MOTOR_ESTADO_PARAMETRO_AUSENTE` (not filled with zero) | same | same |
| `nrtl-lle-agua-butanol` 1 | water, 1-butanol | own fit (below) | T 293–373 K | same |
| `agua-iapws95-hielo-ih` 1 (static only) | water | — | T 200–300 K, P 0.1 Pa–100 MPa | TP, PH, UP, UV |

**Water/1-butanol LLE.** No installed parameter set reproduced the mutual solubility; NRTL was fitted (`a12 = 3.0275, b12 = 181.98 K, a21 = 11.653, b21 = −3221.2 K, α = 0.4396`) to the values recommended by the IUPAC-NIST Solubility Data Series vol. 15 (Hefter, evaluator; 1984) at 293, 313, 333, 353 and 373 K. Validation at 298, 323, 343 and 363 K, not used in the fit: maximum error 0.49 g/100 g (fit 0.60). Reproducible: `python tests/ajuste_nrtl_lle_agua_butanol.py`. The package is not offered outside 293–373 K or for other species.

**Ice.** IAPWS R10-06(2009) (coefficients from its Table 2, checked against its Table 6: maximum error 3.8e-10). The melting and sublimation curves are calculated from the closure itself (equal g); the equations of IAPWS R14-08(2011) are used only as an independent cross-check.

## 5. Assembly v2

State per volume: amounts `n_i` (mol) and `U` (rigid) or `H` (prescribed pressure, `dH/dt = J_E + V dP/dt`). The split between phases is algebraic at each evaluation of the right-hand side; phase amounts are not integrated.

- **Streams**: one ID, one transfer per component and energy, added to the receiver and subtracted from the donor as the same number (cancellation by identity). The donor follows the sign of the flow. Modes `total_desde_donante` (the donor's composition) and `por_componente`. Extraction per end: `mezcla_homogenea` or `fase` (`liquido` with two liquids requires `criterio`: `mayor_densidad` | `menor_densidad`; without it, the stop is `fase_ambigua`). An external stream with a TP `estadoExterior` and its own composition.
- **Heat**: `impuesto` or `conductancia` (`Q = G (T_a − T_b)`), one value shared with opposite signs in internal contacts. A non-adiabatic volume without a declared exchange stays `incompleto` (`MOTOR_ENS_Q_PENDIENTE`): a missing heat is not zero.
- **Count**: structural bipartite matching; pending data are matched last, to point out the exact origin of what is pending. The donor relation is split into `transferencia.<s>.composicion` and `.entalpia` (two unknowns, two equations).
- **Integration**: RK45 with seeded flashes at the stages; each sample is certified with the full stability test.

### Events (M6)

The watch is **pointwise, not continuous**: at each accepted step the phase set is checked at 3 interior points and the end; if it changes, the instant is bisected, the integration redone up to it, and restarted. A transition that appears and disappears between two watched points of the same step is not detected; the maximum step limits that risk but does not remove it. The tests compare the bubble and dew times of a closed heating with independent static flashes: agreement < 1e-5 relative, also with 2 samples (events within one step).

### Published residuals

- `global.materia.<c>`: `max_t |Σ_v n_v,i − n_i(0) − ∫ ṅ_ext,i dt| / (atol + rtol · max Σ n)`, tolerance 10. The scale adds only amounts (fixed in this delivery: it used to add energies too).
- `global.energia`: U of the certified states against `∫ E_ext dt − Σ W_v`, with `W_v = [P V] − ∫ V dP`.
- `mecanica.<v>.trabajo`: the integrated work `∫ P dV/dt` (dV/dt by central difference) against the work by parts; tolerance 1e-5 relative (measured agreement ~2e-6).
- `estado.<v>.energia` and `estado.<v>.volumen`.

### Second law (M6)

`S_gen(t) = Σ_v S_v(t) − S(0) − ∫ (Σ ṅ s + Q/T_boundary)_ext dt` over the certified samples: it must be ≥ 0 and non-decreasing. Each external exchange needs `temperaturaFronteraId`; if it is missing, `no_evaluable` (it is not replaced by the fluid's T). Separate from local/global stability and from the balance residuals. The tests include a negative control: heat from a boundary at 400 K entering a vapor that exceeds it (462 K) → `no_cumple`.

## 6. Capability matrix by milestone

| Milestone | Published | Main check (`tests/validar_motor_ensamblaje_v2.py`) |
|---|---|---|
| M0 | `presionPrescrita` guard; typed, additive revision 2 | §0; v1 §12 |
| M1 | ideal mixture TP/PH/UP/UV, potentials, stability | §1: K = Psat e^{v_L(P−Psat)/RT}/P < 1e-9; pure = absent species; traces; order; extensivity; `dH = ∫T dS` |
| M2 | ChemSep NRTL; energy with h^E; dynamics of one volume | §2: thermo.nrtl 1e-12; Gibbs–Duhem; h^E; ethanol–water azeotrope 78.07 °C, x = 0.881 (lit. 78.15 °C, 0.894); §3 events and H = H0 + Q t |
| M3 | several volumes, internal streams, contact | §4: constant total U and growing S; m = m0 ∓ F t; negative matter control; coupled binary |
| M4 | LL and LLV (water/1-butanol), decanter | §5: IUPAC (fit and validation); heteroazeotrope 94.13 °C (lit. 93.0 °C, ±2 K); homogeneous rejected by tm; LLV plateau by PH and UV; continuous IDs; extraction of the organic phase |
| M5 | static ice Ih, SL/SV/triple, diagram | §6: Table 6; R14-08 (sublimation ≤ 6.5e-5, melting ≤ 2.5e-5 relative); triple 273.16 K, 611.6548 Pa; normal melting 273.152519 K; heat of fusion 333.43 kJ/kg; UV at the triple point |
| M6 | documented pointwise events; second law | §3: events with 2 samples; `no_evaluable` without a boundary T; negative control |

Not supported (published in `noSoportado` or rejected with a diagnosis): selective transfer, reaction, electrolytes, membranes, nucleation, capillarity, momentum; streams between packages with different references; pressure with steps; ice in dynamic volumes; solids in mixtures (solubility, SLE, eutectics and solid solutions need packages and data of their own); ices II, III, V… (P > 100 MPa).

## 7. What the reader can check without repeating the EOS

- The frontend's `validarRespuestaEstado` already covers: reconstruction of composition, properties and fraction bases (β, χ, ε), `h = u + Pv`, specifications respected, stability scope against the capability, residuals ≤ tolerance. Every state of the v2 examples (36 per volume and 7 point states) passes it without modifying the reader.
- With the v2 series: `Σ_v n_v,i` against the external streams; `U_A + U_B` in an isolated contact; monotonic `red.Sgen`; continuity of phase IDs; that events coincide with changes in `fases`.
- Stability scope of ice: a phase not evaluable at that T, P (ice above 273.16 K, vapor without a root, liquid below 235 K) appears in `alcance` only if the curves of the same closure leave it outside the stable region; the check's `motivo` says so.

## 8. Known limits

- Bubble or dew point at ~1e-12 K and an almost azeotropic composition: the split is degenerate (x ≈ y) and the engine can refuse to certify (`no_convergente`) rather than publish a doubtful state.
- Water/1-butanol heteroazeotrope ~1.1 K above the literature: the fit is LLE only; the VLE uses the same parameters.
- UV of mixtures: ~0.5–6 s per state (Newton with a prior search); TP 4–7 ms with a seed.
- Ice: static only; T 200–300 K; the subcooled liquid is a candidate only with T ≥ 235 K.
- Ideal vapor: P ≤ 5e5 Pa in mixtures.

## 9. Tests and results

| Test | Result |
|---|---|
| `python tests/validar_motor_ensamblaje_v2.py` (sections 0–6) | OK, 114 checks |
| `python tests/validar_motor_termodinamica.py` (H1) | OK, 585 (catalog updated with the additive models) |
| `python tests/validar_motor_termodinamica_h3.py` (H3) | OK, 3729 |
| `python tests/validar_motor_ensamblaje.py` (v1) | OK, 245 |
| `node tests/verificar_contrato_ensamblaje_v2.mjs` | OK: 6 pairs compiled; 36 states per volume and 7 point states validated |
| `node tests/verificar_contrato_ensamblaje.mjs` (v1) | OK: 13 pairs, 175 states (v1 examples unchanged) |
| `node tests/verificar_contrato_motor_termodinamica.mjs` | OK |
| `npm run test:motor-fundamental` (frontend, unmodified) | OK |

## 10. Files

New: `core/mezclas.py`, `core/mezclas_datos.py`, `core/paquetes_volumen.py`, `core/ensamblaje_red.py`, `core/hielo_ih.py`, `core/agua_slv.py`, `backend/motor_mezclas.py`, `backend/motor_ensamblaje_v2.py`, `backend/motor_hielo.py`, `docs/contratos/contratoEnsamblajeV2.ts`, `tests/solicitudes_v2.py`, `tests/ajuste_nrtl_lle_agua_butanol.py`, `tests/validar_motor_ensamblaje_v2.py`, `tests/generar_ejemplos_motor_ensamblaje_v2.py`, `tests/verificar_contrato_ensamblaje_v2.mjs`, examples.

Modified (additive): `backend/main.py`, `backend/motor_termodinamica.py`, `backend/motor_ensamblaje.py`, `tests/validar_motor_termodinamica.py` (catalog with the new models), `tests/validar_motor_ensamblaje.py`.

## Sources

- IAPWS R6-95(2018), IAPWS-95.
- IAPWS R10-06(2009), Revised Release on the Equation of State 2006 for H2O Ice Ih — https://www.iapws.org/relguide/Ice-Rev2009.pdf
- IAPWS R14-08(2011), Revised Release on the Pressure along the Melting and Sublimation Curves of Ordinary Water Substance — https://www.iapws.org/relguide/MeltSub.html
- IUPAC-NIST Solubility Data Series vol. 15, Alcohols with Water (Barton ed., Hefter evaluator; Pergamon 1984), 1-butanol + water.
- Table of heterogeneous azeotropes (University of Edinburgh) — https://homepages.ed.ac.uk/jwp/Chemeng/azeotrope/hetero.html — water/1-butanol 93.0 °C.
- Gmehling et al., Azeotropic Data: ethanol/water 78.15 °C, x_EtOH ≈ 0.894 at 1 atm.
- ChemSep NRTL via `thermo` (Caleb Bell), `thermo.interaction_parameters.IPDB`; `thermo.nrtl` as a cross-check.
- B. E. Poling, J. M. Prausnitz, J. P. O'Connell, The Properties of Gases and Liquids, 5th ed.
