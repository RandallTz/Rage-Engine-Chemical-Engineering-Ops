# Thermodynamic layer of the common model

18 October 2026. It is step 2 of [ARCHITECTURE.md](../../ARCHITECTURE.md) §10. It puts into practice the principle of §3 of the architecture: **the thermodynamic relations are always present**.

- Code: `core/termodinamica/capa.py`.
- Tests: `tests/validar_capa_termodinamica.py` (mixture) and `tests/validar_capa_agua.py` (pure water).
- Examples: `docs/ejemplos/modelo-comun/capa-calentamiento-benceno-tolueno.json` and `capa-ebullicion-agua.json`.

## 1. What it does

For a volume of the common model with an equilibrium closure:

| Function | Returns |
|---|---|
| `candidatas(modelo, v)` | The package's **fixed** set of candidate phases: `vapor-1`, `liquido-1` and, with activity models (NRTL, UNIFAC) and more than one component, `liquido-2`. An ideal solution does not split into two liquids, so it has no `liquido-2`. Pure water (`agua-iapws95`) has `vapor-1` and `liquido-1` |
| `variables(modelo)` | The state variables of each volume: T, P, V and, for each candidate, its amount, its composition and its tangent-plane distance `tm`. They are the same in any state |
| `cierre(modelo, v, n, ("PH", P, H) \| ("UV", U, V) \| ("TP", T, P))` | The state with **all** the candidates |

Each candidate of the state `cierre` returns carries:

- `presente`, `n`, `beta`;
- `composicion` (if present) or `composicionIncipiente` (that of the first bubble or the first drop);
- `tm`.

The state also carries the complementarity residual.

For each phase k:

    beta_k >= 0,    tm_k >= 0,    beta_k · tm_k = 0

- A subcooled liquid has `beta_vapor = 0` and `tm_vapor > 0`: the vapor's equations are there and yield nothing.
- On heating, `tm_vapor` falls to 0 at the bubble point, and from there `beta_vapor` grows.
- At the dew point the same happens with the liquid.

The model is never changed and no mode is switched on. T(H) is continuous at the phase boundary; what changes is its slope: the kink in the properties, which the integrator handles with an event.

The layer **does not duplicate physics**:

- the phase split is that of `core/mezclas.Sistema` (minimization of G);
- `tm` is its own stability test;
- a trial phase that coincides with a present phase is discarded with the package's own rule.

## 2. Guide test

One mole of equimolar benzene and toluene (package `mezcla-ideal`) at 101 325 Pa receives 100 W from 330 K for 500 s.

The assembly engine solves the trajectory from the common model, which it receives as a v2 request through `a_ensamblaje_v2`. The layer reads each sample.

There are two independent references for the flash:

- **R1. Raoult with Poynting in closed form**, using only the package's pure-component data: K_i = Psat_i·exp(v_L,i·(P − Psat_i)/RT)/P. From it come:
  - the bubble point (Σ z_i K_i = 1) and the dew point (Σ z_i/K_i = 1);
  - the `tm` of the absent phase: −ln Σ z_i K_i for the vapor and −ln Σ z_i/K_i for the liquid;
  - the vapor fraction, by Rachford-Rice.
- **R2. Published Antoine**, which does not use the package's data.

Results (179 checks passed):

| Check | Result |
|---|---|
| Bubble and dew points against Antoine | 365.275 K against 365.262 K; 371.919 K against 371.923 K (tolerance 0.5 K) |
| Grid of 25 temperatures between 330 and 390 K | Always the same candidates. `tm` of the absent phase equal to R1 (1e-8). Vapor β equal to Rachford-Rice (1e-8). Complementarity < 1e-9 |
| Trajectory | The vapor appears at R1's bubble T (1e-4 K) and the liquid disappears at its dew T (1e-4 K). H(t) = H(0) + Q t. The layer's T equals the engine's at every sample (1e-6 K) |
| Before, during and after | Before: β_vapor = 0, with `tm` positive and decreasing. During: `tm` = 0 and β grows from 0 to 1. After: vapor only, with the liquid absent and `tm` > 0 |
| Phase boundaries | T(H) continuous (jump < 1e-3 K) and a change of slope (kink) at both transitions |
| Structure | The model's relations are the backend's equations |

## 3. Pure water (IAPWS-95)

The layer wraps `core/agua_iapws95.py` without modifying it: its PH, UV and TP evaluations and its own stability test.

For a pure substance the absent phase has no composition to optimize. Its `tm` is the Helmholtz tangent-plane distance at fixed T on the other branch of the EOS, at its minimum ρ_m, divided by RT and per mass of the trial phase:

    tm = TPD(ρ_m) / (ρ_m R T)

It is the same scale as in mixtures, and it reduces to (g_k(T, P) − g*)/RT when the branch has a root at the state's P.

Above T_c there is only one fluid branch: the liquid cannot appear and its `tm` is `None`, with β = 0.

**Boiling test** (`tests/validar_capa_agua.py`, 161 checks). One mole of water at 101 325 Pa receives 100 W from 330 K for 600 s. The references come from IAPWS-IF97, a different formulation, and from published tables:

| Check | Result |
|---|---|
| IF97 T_sat and h_fg against published values | 373.1243 K (373.124 K); 2256.54 kJ/kg (2256.4) |
| `tm` of the absent vapor in the liquid, from 330 K to T_sat | Equal to (P − Psat)(1/ρ'' − 1/ρ')/RT with IF97 densities (1e-3 relative) |
| `tm` of the absent liquid in the vapor | Positive and increasing, within 3 % of the ideal-gas approximation |
| Trajectory | Boils at IF97's T_sat (5 mK). Plateau heat Q·Δt = m·h_fg (1e-3). Constant T on the plateau (1e-6 K). β_vapor = Q(t − t_b)/(m·h_fg) (1e-3). H(t) = H(0) + Q t. The layer's T equals the engine's (1e-6 K) |
| Boundaries | T(H) continuous with zero slope on the plateau. Above T_c the liquid is listed as a candidate that cannot appear |

## 4. UNIFAC (block A of ARCHITECTURE.md §10, 18 October 2026)

The three UNIFAC packages (`unifac-original-public`, `unifac-dortmund-public`, `unifac-original-lle-public`) go through the layer and the common compiler without any branch of their own. Test: `python tests/validar_capa_unifac.py` (82 checks, ~5 min). It uses the seven dynamic UNIFAC requests the engine publishes (`docs/ejemplos/motor-unifac/`), brought into the common model.

| Case | Package | Against the existing engine | Against an independent reference (`thermo`'s UNIFAC, another implementation) |
|---|---|---|---|
| Ethanol–water heated until it boils | original | state 1e-8; event at the same instant | the vapor appears at the γ-φ bubble T (1e-4 K) |
| Water, ethanol, ethyl acetate, methanol heated | original | same | same |
| The same four species | Dortmund | same | same |
| Water with a butanol feed at 298 K | LLE | same | the second liquid phase appears when the load reaches the binodal by isoactivity (1e-8 in mole fraction), with the conjugate phase (1e-5) |
| Ethanol–water with the "single-phase" policy | original | stops at the engine's instant (1e-6 s) | — |
| Two-volume network, five species, water entering A | original | same state until the appearance | the second liquid phase appears where the LL tangent plane crosses zero: 113.58602 s against the reference, between 113.5860 and 113.5861 s |

In every case:

- the three candidates (vapor-1, liquido-1, liquido-2) are published at every sample, with β = 0 before they appear;
- global conservation of matter and energy stays below 1e-12;
- the complementarity β·tm stays below 1e-8.

**Finding and fix.** This test found that, in the five-species network, the existing engine published the second liquid phase at 141.41 s, 28 s late. After locating it, it accepted the whole step without an event when it did not find it again in the reintegrated state. Fixed on 18 October 2026 (`core/ensamblaje_red.py`); the engine and the common compiler now agree with the independent limit. Details in [docs/engine/engine-map.md](../engine/engine-map.md) §6.

**Phase policy.** `politica.cantidad = "monofasico"`, `cambioInterno = "prohibido"` and `tiposPermitidos` are declared assumptions. The compiler stops the calculation at the instant the set of phases violates them (event `politica_incumplida`) and rejects an initial state that already violates them.

**Performance.** The five-species network takes ~255 s in the common compiler. It is a pending item for polishing thermodynamics: the fast seeded flashes are repeated at every stage.

## 4 bis. The sheet's Thermodynamics panel (18 October 2026)

Every Engine sheet shows four panels: Matter, Energy, Momentum and **Thermodynamics**. Thermodynamics is not switched on or off: it is each volume's state closure, "always present". Its view (`frontend/app/motor/TermodinamicaHoja.tsx`) shows:

1. **The always-present relations:**
   - fundamental relation;
   - UV or PH state closure, depending on the boundary;
   - split among the candidate phases;
   - mixture properties;
   - equilibrium between the present phases;
   - tangent-plane stability;
   - complementarity β·tm = 0.
2. **Each volume's closure**, which the server publishes at `POST /modelo/termodinamica` (`core/termodinamica/descripcion.py`, without calculating states):
   - the package and its phase policy, or the assumption with its reason;
   - the candidate phases, the same ones the layer uses;
   - the state-model family, with its equations: ideal (Raoult with Poynting), activity (γ_i with UNIFAC or NRTL) or IAPWS-95 (Helmholtz);
   - the relations the Engine assembles.
3. **The possible thermodynamic assumptions**, with their effect on the equations, the volumes where they are active, and where they are declared:
   - equilibrium with a package;
   - ideal solution;
   - activity coefficients;
   - ideal vapor;
   - incompressible liquid;
   - restrict to one phase;
   - forbid phase change;
   - linear u(T);
   - state not evaluated.

**The view is a derivation** (19 October 2026, principle 10 of the architecture):

- It starts at the fundamental thermodynamic relations (step 01). Each state assumption is a step with its relation, with undo and redo: one phase, no phase change, constant density, linear u(T).
- Those assumptions are declared **only here**: `frontend/app/motor/recorridoTermodinamico.ts`, stored in the sheet's `recorridoTermodinamico`. The energy derivation keeps only its own steps and uses the effective formulation (`formulacionEnergiaHoja` adds the thermodynamic assumptions).
- With a real closure (IAPWS-95, chosen in State), "one phase" and "no phase change" are its phase policy.
- Sheets saved earlier are migrated when read (`migrarTermoHoja`): the thermodynamic steps of their energy derivation move, in order and with their relations, to the thermodynamics. The effective formulation does not change; the signature does, so it is worth solving again.

The thermodynamic-network sheets (the multiphase, UNIFAC and N-component examples) no longer open another page: they show the same panels. Matter and energy present the equations the Engine assembles for the network; the switches only inform ("Lo fija la red").

Test: `python tests/validar_descripcion_termodinamica.py` (23): ideal, original UNIFAC and LLE, IAPWS-95 water and a volume with an assumed u(T); the candidates equal the layer's.

## 5. Limits

- **Solids:** no dynamic package has them.
- **Volume with an assumed state:** it has no closure to evaluate (`NoSoportado`). That is the case of the TS solver's sheets.
- **Solver:** since step 4 the trajectory is integrated by the common compiler (`core/compilador`, `core/solvers`, [docs/engine/vertical-slice.md](../engine/vertical-slice.md)); the existing assembly engine (path B) stays as the comparison reference.

### Phase discovery and rigid-volume acceptance

Model declares components, constitutive data, mechanical constraints and unrestricted phase policy; it does not select a resulting phase set. Solve must derive phase amounts/compositions from equilibrium and stability, with the existing candidate-phase limit. For a rigid closed volume, temperature and pressure must be recovered from inventories, internal energy and volume (UV); a temperature initializer uses TV consistently. A completely liquid-filled incompressible package cannot determine pressure and must reject that specification.

Newton trial rejection must check finite positive component amounts and the actual inventory bounds before exponentiation/normalization, and honor the package temperature/pressure domain. Invalid exploratory points trigger backtracking or the existing full-flash fallback; no NaN-to-zero replacement, arbitrary composition clipping, warning suppression or relaxed certification is allowed. Verification must cover independent constitutive/stability references, component-order and seed changes, TV/UV recovery, near-boundary states and closed-vessel conservation. These are numerical acceptance checks, not a proof of a global minimum for arbitrary mixtures.

## Recorded thermodynamic choices (19 October 2026)

Model records manual state assumptions separately from first-law assumptions. Equilibrium volumes additionally record the configured package identity/version and exact phase policy through the optional thermodynamic journal defined in [common model §9](common-model.md#9-first-law-and-thermodynamic-operation-journals). Python replays those choices against the actual common volume before compilation. New examples start with fundamental state relations and explicitly select their constitutive model; saved snapshots are never promoted to a fabricated operation history.

The journal exposes fundamental/Legendre identities, phase partition, equilibrium and stability, package-family relations and the final closure. UNIFAC selection remains a constitutive choice with existing empirical data and domains. A successful replay neither proves experimental accuracy nor extends a package's domain. Manual caloric or constant-density assumptions cannot silently override an equilibrium package. Physical priorities remain UNIFAC first; NRTL coverage is preserved without extension. Remaining phase/transfer capabilities are maintained in the existing roadmap and [Engine checklist](../engine/engine-checklist.md).


### Rigid-vessel discovery implementation evidence (19 October 2026)

The generic mixture solver now rejects invalid logarithmic trial amounts before exponentiation, enforces the declared T/P domain, tries small phase additions near a binodal and polishes invariant pressures inside the actual discovery bracket. Equality/stability certification tolerances are unchanged. The ordinary water–1-butanol template and both native/common heating paths verify the unrestricted policy with TV initialization and UV recovery. Nine new tests include an independent UNIFAC implementation, inverse recovery, component permutation, seed changes, near-boundary states and invalid/incompressible specifications. Existing UNIFAC (82), thermodynamics (585) and H3 (3729) checks pass. Numerical validation does not imply experimental accuracy or exhaustive global stability. Inputs and product behavior remain in the [workspace specification](../engine/model-workspaces.md#property-driven-phase-discovery-example-19-october-2026); remaining scope stays in the roadmap.


## Nonspatial consolidation (20 October 2026)

The existing thermodynamic development additionally exposes the homogeneous-phase Euler/Gibbs-Duhem identity, normalized mole fractions, total enthalpy partition and the mixture excess-potential identities. The same gE produces activity coefficients and caloric properties (sE = -d(gE)/dT, hE = gE + T sE); the published pressure-independent excess models have vE = 0. These are descriptions of the existing implementation, not new constitutive data or a new frontend. Centered numerical differentiation independently checks chemical potentials and caloric identities for original, Dortmund and LLE UNIFAC.

The native network integrator preserves the numerical flash context at located phase events. Certified publication freshly evaluates properties, chemical-potential equality, material reconstruction and full stability at the preserved phase amounts, without repeating Newton or trusting cached certificates. It starts from that context and rejects a changed phase signature instead of publishing a contradictory event. The exact located time replaces a nearly coincident scheduled sample. Event resolution is 1e-12 of the horizon with the existing absolute floor; phase-presence, stability, potential-equality and certificate tolerances are unchanged. The auxiliary integral of P dV/dt remains independent of the published algebraic work identity. Existing upstream phase selection is preserved; recertification applies no additional amount cutoff, does not insert or rescale phases, and trusts no cached certificate. Internal event context adds no public JSON field or package-specific branch.

Spatial work is deferred by user decision. The supported packages retain their existing domains and finite-search limits; nonideal vapor, mixture solids, reaction equilibrium and cross-reference package transfers are not implicitly implemented by this consolidation. Former product examples are now internal numerical regression fixtures only.
