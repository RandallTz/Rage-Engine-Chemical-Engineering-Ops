# N-component thermodynamics and dynamic assembly (N0–N4)

Delivery of [docs/history/frontend/assignment-claude-thermodynamics-n-components.md](../history/frontend/assignment-claude-thermodynamics-n-components.md). Core, backend, tests and `docs/`. The frontend, `/laboratorio` and `thermodynamics/proveedor.py` were not touched. No commit, push or deployment.

**Reload:** restart the service (`uvicorn backend.main:app`). Afterwards, `GET /motor/ensamblajes/capacidades?revision=2` must show `componentesMaximos` equal to 7 and a new field, `tamanos`. The routes do not change.

## 1. State

| Milestone | State |
|---|---|
| N0 audit | done (§2) |
| N1 stability and split in general dimension | done: multi-seed Michelsen for N ≥ 4, cross-checked against the specialized routes for N = 2 and 3 |
| N2 inversions and static cross-checks | done: ideal with N = 4, 5 and 7 against Rachford–Rice; NRTL with N = 4 (L–V and L–L) against an independent solver with `thermo` |
| N3 dynamics | done: heatings at prescribed P with N = 4 (NRTL), 5 and 7 (ideal); rigid with vapor (N = 4); a two-volume network (N = 5) with an incoming species and sign reversal; vapor extraction until it runs out |
| N4 contract, performance and regression | done (§6–§8) |
| NRTL with 5 or more species | **blocked by data**: no set of 5 species of the catalog has all its ChemSep pairs (§2.3) |

## 2. N0 · Audit

### 2.1 Catalog, volume and active species

- **Global catalog**: `solicitud.componentes` (revision 2). The global index `gidx` is used for the balances and the residuals `global.materia.<id>`.
- **Components of each volume**: `volumenes[].componenteIds`. Each volume builds its `Sistema(package, CAS of the volume)`. The limit `componentesMaximos` applies per volume, to **declared** components.
- **Active species of a state**: `idx = [i for i in n if n[i] > 0]` within `core/mezclas.py`.
  - A species with an amount of exactly zero leaves the active problem and keeps its ID: x = 0 in every phase and an undefined μ (`null` in `potenciales`).
  - A positive trace is never turned into zero.

### 2.2 Fixed-dimension dependencies found

| Place | Before | Now |
|---|---|---|
| `prueba_estabilidad` | branches for 1, 2 and 3 species; with more, `no_soportado` | 1 to 3: specialized routes unchanged. ≥ 4: `_estabilidad_general` (§3) |
| `_softmax3` | ternary refinement | unchanged (N = 3 only) |
| `_minimizar_G`, `_pulir`, `flash_rapido/_newton`, `_meseta_general`, `_pulir_invariante` | already general in dimension | no dimension changes; `_pulir` now uses a decoupled Jacobian (§3.3) |
| `MAX_FASES = 3` | on reaching the cap, a generic failure was published | kept at 3. If a competing phase is left without room: an explicit rejection `tope_fases` (§3.4) |
| `COMPONENTES_VERIFICADOS` (assembly v2) | 3 per volume | 7 per volume: the whole mixture catalog, with the cross-checked sizes in `tamanos` |
| `VOLUMENES_VERIFICADOS` | 3 | 3 (out of scope) |
| Diagrams | binary | binary (unchanged: the tracer's own limit) |
| Residuals, series, events, series catalog | per component and volume | already general |
| Assembly v1 | pure water | unchanged |

### 2.3 NRTL pairs and complete sets

Every subset of the catalog's 7 species was gone through, requiring ChemSep's `bij` and `alphaij` (via `thermo` IPDB) for each pair. There are 13 pairs with data. Complete sets:

- **4 species**: {ethanol, benzene, toluene, methanol} and {water, ethanol, ethyl acetate, methanol}. b_ij was checked in both directions, and a symmetric α.
- **5, 6 or 7 species**: none. For example, water–benzene, acetate–benzene and butanol with ethanol, benzene, toluene or acetate have no parameters.

No coefficients were invented or filled with zero. A set with a missing pair returns `MOTOR_ESTADO_PARAMETRO_AUSENTE` in the point service or `MOTOR_ENS_PARAMETRO_AUSENTE` (`no_soportado`) in the assembly.

### 2.4 Common domain and phases

The domain is the **intersection** of each species' ranges (Psat, cp, T ≤ 0.9 Tc), never the union:

| Set | T [K] |
|---|---|
| 7 species (ideal) | 298.0–461.38 |
| {water, ethanol, acetate, methanol} | 298.0–461.38 (acetate limits it to 298 K) |
| {ethanol, benzene, toluene, methanol} | 278.68–461.38 |

P goes from 100 Pa to 5 bar (ideal vapor, unchanged). Phases: liquid and vapor, up to 3 at a time. The catalog has no set with an empty intersection; a T outside the intersection (e.g. 290 K with acetate) is rejected even if other species admit it.

### 2.5 Identifiable operations

TP, PH and UP whenever there is a domain. UV and TV only if there is vapor: an incompressible liquid that fills a volume does not determine P, and it is still rejected with `no_soportado` for any N.

## 3. N1 · Stability and split

### 3.1 Foundation

At given T and P, equilibrium minimizes G = Σ_α Σ_i n_i^α μ_i^α with n_i = Σ_α n_i^α and n_i^α ≥ 0. A state's stability is checked with the tangent-plane distance, with the same reference and the same package:

```
tm(w) = Σ_i w_i [μ_i^trial(T, P, w) − μ_i^ref] / (R T),   w_i ≥ 0,  Σ w_i = 1
```

### 3.2 Method for N ≥ 4 (`Sistema._estabilidad_general`)

Michelsen, in amount variables W_i:

```
tm*(W) = 1 + Σ_i W_i (ln W_i + ln γ_i(w) − d_i − 1),   d_i = (μ_i^ref − g_L,i)/(R T)
```

Its stationary points coincide with those of tm(w), and tm* < 0 if and only if tm < 0.

- **Deterministic starts**:
  - the N pure vertices;
  - the ideal estimate (γ = 1);
  - 2^⌈log₂(8N)⌉ Sobol points of the simplex (`scipy.stats.qmc`, randomization with a **fixed seed 12345**).
  - In total: 37 starts with N = 4 and 72 with N = 7. The cost grows as ~8N, not as a tensor grid.
- **Successive substitution** (`ln W_i = d_i − ln γ_i(w)`) of all the starts at once, with batched ln γ.
- **Polishing** of the distinct candidates with L-BFGS-B in β_i = 2√W_i ≥ 0. W_i = 0 belongs to the domain, so the **faces and vertices of the simplex** are reached and a trial species can vanish without evaluating `log 0`.
- **Vapor trial phase**: the usual analytical minimum (ideal vapor).

A finite multi-seed search **does not prove the global minimum**; the published method and the capabilities say so.

**Cross-check against the specialized routes** (where both apply, same states):

| Case | Specialized | General |
|---|---|---|
| Binary water/1-butanol, L–L (x = 0.75, 320 K) | tm −3.6595637e-02 | −3.6595637e-02 |
| Stable binary (x = 0.4 and 0.99) | ≥ −1e-16 | ≥ −1e-16 |
| Ternary water–ethanol–acetate, L–L (0.7/0.05/0.25, 300 K) | −1.5652028e-03, same composition | −1.5652028e-03 |
| Stable ternaries | ≥ −5e-16 | ≥ −9e-17 |

### 3.3 Split: a Jacobian decoupled by phase (fix)

With a tiny phase (e.g. 3.7e-9 mol of vapor 1e-12 K from the bubble point with 5 species), the global finite difference of 1e-7 in ln n moves the remainder phase less than the rounding noise of its μ. The direction of the total amount ends up dominated by noise and Newton stalled at a residual of 5.7e-10, above the 1e-10 tolerance. The TP ended in `no_convergente`.

Now `_jacobiano_reparto` differentiates each phase only with respect to its own amounts. The remainder phase is differentiated with respect to its own, with a step proportional to its amount, and both are combined by the chain rule. The same case converges with a residual of 1.2e-15 and a vapor amount that matches exact Rachford–Rice (3.7346256e-9 against 3.7346264e-9 mol).

### 3.4 Phase cap

If the state already has `MAX_FASES` phases and the stability test finds a phase that lowers the tangent plane, the state is **not** published as stable. It is rejected like this:

- `FueraDeAlcance('no_soportado', tope_fases=True)` in the core;
- `MOTOR_ESTADO_TOPE_FASES` in the point service;
- the stop `tope_fases` (`MOTOR_ENS_DETENIDO_TOPE_FASES`) in the assembly.

## 4. N2 · Inversions

PH, UP, UV and TV already used the same TP, and therefore the same stability and the same split. After each inversion, T, H, V and the composition of **a single phase split** are checked.

A UV defect was fixed. The search in T evaluated the domain's ceiling first: with 7 species (461 K) and fixed V the pressure exceeds 5 bar, and the exception aborted everything. Now the search is bounded to the highest evaluable T, as was already done at the cold end. If the requested U lies above, the response is `fuera_de_dominio` with `P_fuera`.

## 5. Evidence

| Type | Case | Result |
|---|---|---|
| Independent numerical reference | Ideal N = 4, 5 and 7, three Dirichlet compositions each, against Raoult + Poynting + Rachford–Rice written in the test | β and compositions < 1e-9 |
| Another implementation with the same parameters | NRTL N = 4 {ethanol, benzene, toluene, methanol} (345 and 350 K) and {water, ethanol, acetate, methanol} (345 K), L–V, against a γ-φ flash by successive substitution + Rachford–Rice with `thermo.nrtl.NRTL` | β, x and y < 1e-8 |
| Another implementation with the same parameters | NRTL N = 4 L–L {water, ethanol, acetate, methanol} at 300 K (0.7/0.04/0.24/0.02), against an independent isoactivity with `thermo` | compositions and split < 1e-8 |
| Internal consistency | Gibbs–Duhem N = 4 in random directions (< 1e-7); g = h − Ts = Σ x μ; partial molar enthalpies against h_i − R T² ∂ln γ_i/∂T (< 1e-6) | complies |
| Experimental evidence | **none new** | The ChemSep parameters come from binary VLE fits; the 4-species mixtures are predictions of the model (evidence `cualitativa`). In particular, the predicted L–L split for water–acetate is far from the experimental solubility (the real aqueous phase has ~98 % water) |

**Controls and properties** (`tests/validar_motor_n_componentes.py`):

- **Absences**: a 7-species catalog with 3 at exactly zero, against the reduced 4-species system: same state (G to 1e-9), x = 0 and undefined μ in the absent ones, IDs kept.
- **Traces** of 1e-6, 1e-9 and 1e-12: reconstruction **per species** relative to its own inventory < 1e-9; equality of μ ≤ 1e-10.
- **Extensivity**: ×1e-6, ×1 and ×1e6.
- **Permutations** of species: same equilibrium and same fingerprint.
- **Different phase and composition seeds** in the seeded flash: the same minimum as the full flash.
- **Determinism** of the general stability with the fixed seed.
- **Negatives**:
  - missing pair;
  - T outside the intersection of domains;
  - phase cap forced (`MAX_FASES = 1`) in the core and in the point service;
  - UV of a full liquid.

## 6. N3 · Dynamics

The same coordinator: states n_i and U/H, with thermodynamics rebuilding the state without touching amounts or flows. Cases (`tests/validar_motor_n_componentes.py` §N3):

1. **Heating at prescribed P** with N = 5 (ideal), 4 (NRTL) and 7 (ideal):
   - H = H0 + Q t;
   - each species constant;
   - bubble instant against an independent static flash < 1e-5 relative, with `faseIds = ['vapor-1']`;
   - certification `cumple`.
2. **Rigid with vapor** (N = 4 NRTL): U = U0 + Q t, constant V and certified.
3. **Two volumes** (N = 5 ideal) with a negative-flow stream and thermal contact:
   - conservation per species;
   - donor B with its composition;
   - water enters A from zero, without a fictitious inventory and with its ID kept;
   - second law `cumple`.
4. **Vapor extraction** from an adiabatic L–V volume: the global composition changes; when the vapor runs out the event `desaparicion_fase` and the stop `MOTOR_ENS_DETENIDO_FASE_AUSENTE` occur.
5. **Sensitivity**: rtol 1e-6 with 3 samples against 1e-10 with 9 samples; the events coincide < 1e-5 relative.

**Defect found in case 3** (C1 certification detected it while regenerating the example): the total derivative of V for the boundary work divided each species' rate by its amount. With water at zero that is /1e-30, and the step ended up at ~1e-33, lost in rounding: residual `mecanica.A.trabajo` 22 against tolerance 1. Now a species at zero is scaled with the volume's total amount. If the backward step would give a negative amount, a three-point forward difference, also of second order, is used. The residual falls to 1.8e-5 and the network is certified.

The event watch is still **pointwise** (3 interior points and the end of each step), not continuous.

## 7. Contract (additive)

- `CapacidadesEnsamblajeV2.componentesMaximos`: **7** (declared components per volume; previously 3). It does not change name or unit; its value reflects what the assembly accepts and tests.
- `CapacidadesEnsamblajeV2.tamanos?` (new, optional):

```ts
tamanos?: {cuenta: string; componentesMaximosPorVolumen: number; fasesMaximas: number;
  contrastados: Record<string, {estatico: number[]; dinamico: number[]}>;
  estabilidad: Record<string, string>; presupuesto: string};
```

  Published values: `contrastados` = mezcla-ideal static [2, 3, 4, 5, 7], dynamic [2, 4, 5, 7]; nrtl-chemsep static [2, 3, 4], dynamic [2, 4]; nrtl-lle-agua-butanol [2]; agua-iapws95 [1].
- New codes: `MOTOR_ESTADO_TOPE_FASES` (point service) and the stop `tope_fases` (`MOTOR_ENS_DETENIDO_TOPE_FASES`).
- The mixtures point service already accepted any number of components; now the core solves them. Diagrams are still binary.
- **Fingerprints**: they do not change with the order of components (tested with permutations), names or units. The numerical configuration (seed 12345, number of starts) goes in the published method, not in the physical fingerprint.

**For the frontend:** the copy `frontend/app/motor/contratoEnsamblajeV2.ts` is already identical to the canonical contract, `tamanos` field included. It was checked with `diff` at the close: Codex synchronized it during this delivery, and the copy verifier of `npm run test:motor-fundamental` passes.

## 8. Performance (`python tests/benchmark_n_componentes.py`)

Seed of the general stability: 12345. Tolerances: |Δμ|/RT ≤ 1e-10, tm ≥ −1e-9. Times on this machine, minimum of three repetitions; "cold" = a new `Sistema` without caches.

**Specialized and general routes, where both apply (same state):**

| N | specialized | general (starts) | min tm (both) |
|---|---|---|---|
| 2 (water/1-butanol, L–L) | 6.8 ms | 22.9 ms (19) | −3.6596e-02 |
| 3 (water–ethanol–acetate, L–L) | 105.5 ms | 72.4 ms (36) | −1.5652e-03 |

The specialized routes for N = 2 and 3 are kept: they are the same problem and give the same minimum. The general one is used only for N ≥ 4.

**States:**

| Package, N | single-phase TP (cold) | L–V TP | TP at +1e-6 K from the bubble point | PH | UV | peak memory |
|---|---|---|---|---|---|---|
| NRTL, 4 | 47 ms (124 ms) | 23 ms | 61 ms | 0.47 s | 6.8 s | 0.1 MB |
| ideal, 4 | 3 ms (11 ms) | 10 ms | 35 ms | 0.10 s | 1.8 s | < 0.1 MB |
| ideal, 5 | 3 ms (14 ms) | 15 ms | 36 ms | 0.12 s | 2.2 s | < 0.1 MB |
| ideal, 7 | 5 ms (17 ms) | 19 ms | 47 ms | 0.15 s | 1.8 s | 0.1 MB |

Before vectorizing the successive substitution, UV with a 4-species NRTL took **31–35 s**: 329 general stability tests of ~0.1 s each. Now, 6.8 s.

**Complete trajectories** (heating at prescribed P, 300 s, 7 samples, rtol 1e-8):

| Case | time | steps |
|---|---|---|
| ideal, N = 5 | 21.6 s | 24 |
| NRTL, N = 4 | 36.3 s | 19 |
| ideal, N = 7 | 29.9 s | 22 |

Budget per state: at most 3 phases and N + 1 + 2^⌈log₂(8N)⌉ stability starts. The caches (`_g_puros` by (T, P) and submodels by set of active species) are pure functions of each `Sistema`, which is tied to a fingerprint. A flash seed is only a starting point and every state passes the full stability test.

## 9. Tests, examples and files

**Commands run and exit codes** (final state of the code):

| Command | Result |
|---|---|
| `python tests/validar_motor_n_componentes.py` | 0 · OK, 82 checks (N0–N2: 61; N3: 21, repeated after the last fix) |
| `python tests/validar_motor_ensamblaje_v2.py` | 0 · OK, 114 (the check of `componentesMaximos` goes from 3 to 7: a deliberate change of capability) |
| `python tests/validar_motor_consolidacion_v2.py 0 1 2 3` | 0 · OK, 56 / 14 / 31 / 27 |
| `python tests/validar_motor_diagramas_equilibrio.py` | 0 · OK, 78 |
| `python tests/validar_motor_ensamblaje.py` (v1) | 0 · OK, 245 |
| `python tests/validar_motor_termodinamica.py` (H1) | 0 · OK, 585 |
| `python tests/validar_motor_termodinamica_h3.py` (H3) | 0 · OK, 3729 |
| historical battery `tests/validar_*.py` (40 suites) | 0 in all 40 |
| `node tests/verificar_contrato_ensamblaje_v2.mjs` | 0 · 10 v2 pairs compiled (including `motor-n-componentes`), 60 states per volume and 12 point examples through the frontend's validator |
| `node tests/verificar_contrato_ensamblaje.mjs` | 0 · 13 pairs, 175 states |
| `node tests/verificar_contrato_diagramas.mjs` | 0 · 11 pairs, 285 points |
| `node tests/verificar_contrato_motor_termodinamica.mjs` | 0 |
| `npm run test:motor-fundamental` (frontend, unmodified) | 0 · the 24 verifiers pass on the original copy of the frontend |

The frontend's trials with 5, 8 and 12 components are algebraic reading checks: they do not count as thermodynamic validation of this delivery.

### 9.1 Historical battery

The 40 suites `tests/validar_*.py` that are not the engine's end with exit code 0 with the final code.

### 9.2 Examples generated from endpoints

`docs/ejemplos/motor-n-componentes/` (`python tests/generar_ejemplos_motor_n_componentes.py`), in a directory of its own so as not to alter what the revision 1 verifiers or Codex's read:

- Point service:
  - ideal with 5 and 7 species (L–V);
  - NRTL with 4 species in L–V and in L–L;
  - NRTL with a missing pair (`MOTOR_ESTADO_PARAMETRO_AUSENTE`).
- Assembly v2:
  - ideal heating with 5 species and NRTL with 4 (both `cumple`);
  - 5-species network with an incoming species (`cumple`);
  - validation with a missing pair (`MOTOR_ENS_PARAMETRO_AUSENTE`, `no_soportado`; the structural count stays `listo` and the solution is rejected).

**Comparison with the earlier examples:**

- `docs/ejemplos/motor-v2/`:
  - Capabilities: `componentesMaximos` goes from 3 to 7 and `tamanos` appears (deliberate).
  - Water–butanol decanter: only residuals and tm of order 1e-16 change, and the scaled `global.energia` (2.05e-8 → 1.60e-8, tolerance 10), because of the decoupled split Jacobian. Series, times and events identical.
  - The other examples: identical.
- `docs/ejemplos/motor-n-componentes/`, network with an incoming species:
  - Before the fix of the V derivative, certification came out `no_cumple` (`mecanica.A.trabajo` 22).
  - After, `cumple`: A's W changes by 9.5e-4 relative (it was wrong before) and the other series change ≤ 7.6e-9 relative (step control, rtol 1e-8).
  - The other N examples, identical.

### 9.3 Files touched

- **Core**:
  - `core/mezclas.py`: `_estabilidad_general`, phase cap, `_jacobiano_reparto`, UV search in T bounded at the hot end;
  - `core/ensamblaje_red.py`: scaling and forward difference in `_dVdt`; stop `tope_fases`.
- **Backend**:
  - `backend/motor_ensamblaje_v2.py`: `componentesMaximos` 7 and `tamanos`;
  - `backend/motor_mezclas.py`: `MOTOR_ESTADO_TOPE_FASES`.
- **Contract**: `docs/contratos/contratoEnsamblajeV2.ts` (`tamanos?`; documentation of `componentesMaximos`).
- **Tests**:
  - new: `tests/validar_motor_n_componentes.py`, `tests/benchmark_n_componentes.py`, `tests/generar_ejemplos_motor_n_componentes.py`;
  - modified: `tests/verificar_contrato_ensamblaje_v2.mjs` (it also walks `motor-n-componentes`) and `tests/validar_motor_ensamblaje_v2.py` (`componentesMaximos` 7).
- **Examples**: `docs/ejemplos/motor-n-componentes/*` (new); `docs/ejemplos/motor-v2/*` (regenerated).
- **Documentation**: this document.

## 10. Limits that remain

- **NRTL with 5 or more species**: no data (§2.3). Parameters are not invented.
- **Evidence**: the 4-species mixtures are predictions from binary VLE parameters, without an experimental cross-check (`cualitativa`). The predicted L–L split for water–acetate does not reproduce the real solubility.
- **Stability**: a finite multi-seed search, not a proof of the global minimum.
- **Phases**: 3 at most. A state that would need a fourth is rejected (`tope_fases`), never published as stable.
- **Domain**: ideal vapor up to 5 bar, incompressible liquid, no critical region; common domain = intersection.
- **Performance**: UV with a 4-species NRTL, ~7 s per state; trajectories of 20–40 s.
- **Events**: pointwise watch. When the extraction itself makes the extracted phase disappear, the terminal event is the stop `fase_ausente`, without a separate `desaparicion_fase`: no step can cross that boundary. The last sample keeps the residual phase (8e-11 in the case tested).
- **Diagrams**: still binary. **Volumes**: 3.
- Extending N does not imply universal thermodynamics, high pressures or more phases.
