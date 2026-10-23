# Multiphase consolidation (C0–C4) · 15 October 2026

Answer to [docs/history/frontend/assignment-claude-consolidation-multiphase-2026-10-15.md](../history/frontend/assignment-claude-consolidation-multiphase-2026-10-15.md) and to the points of [docs/history/frontend/integration-multiphase-v2.md](../history/frontend/integration-multiphase-v2.md) ("Límites y seguimiento de Claude"). Backend, core, tests and `docs/`; `frontend/`, `/laboratorio` and `thermodynamics/proveedor.py` were not touched. No commit or push.

**Reload:** restart the service (`uvicorn backend.main:app`); `backend/main.py` does not change in this delivery.

| Part | State | Where |
|---|---|---|
| C0 consistent capabilities | implemented and tested | `capacidades_v2()`; `tests/validar_motor_consolidacion_v2.py` §C0 |
| C1 physical certification | implemented and tested | `resultados.certificacion`; §C1 |
| C2 series and events | implemented and tested; three defects fixed (IDs, cost of PH, integrator without progress) | `resultados.catalogoSeries`, fields of `EventoV2`; §C2 |
| C3 physical cross-checks | implemented and tested; one defect fixed (absent phase without a diagnosis) | §C3 |
| C4 open boundary, water + air | **design only** (not implemented) | [docs/engine/open-boundary-water-air-design.md](open-boundary-water-air-design.md), `docs/contratos/borradorFronteraAbierta.ts` |

Every new field is **optional and additive** in revision 2 (`docs/contratos/contratoEnsamblajeV2.ts`). No existing field changes name or value, except for the two fixes documented in §5.

## 0. What the frontend should do

Suggestions for the integration; no frontend file was touched.

1. **Copy the contract again**: `frontend/app/motor/contratoEnsamblajeV2.ts` is an earlier copy. The new types (`EventoV2`, `SerieCatalogoV2`, `CertificacionV2`, `CombinacionV2`, `EvidenciaV2` and the optional fields of packages and potentials) are in `docs/contratos/contratoEnsamblajeV2.ts`.
2. **Certification**: read `resultados.certificacion.estado` for the "uncertified trajectory" warning, instead of deducing it from `segundaLey` or from the residuals. `no_evaluable` is not `cumple`. `ultimaMuestraCertificada` and `primeraMuestraNoCumple` mark how far the trajectory can be shown as valid. `estado` (resuelto/parcial) is still only numerical.
3. **Series**: units, quantity and role from `resultados.catalogoSeries`, which covers every series. Those with role `derivada` (mass, S, S_gen) have no equation in `validacion.ecuaciones`.
4. **Events**: `faseIds`, `faseIdsAntes` and `faseIdsDespues` identify the real phases. There is a new code, `sustitucion_fase`; `cambio_denominacion` must not be drawn as evaporation or condensation.
5. **Capabilities**: `combinaciones[].id` and `evidencia` allow distinguishing cross-checked, qualitative and impossible in the model. `pares` says which NRTL binaries have data.
6. **Potentials**: G, A and S are extensive (`unidades: {mu: 'J/mol', G: 'J', A: 'J', S: 'J/K'}`).
7. **Fractions**: with a single phase they now reach exactly 1. The reader's eight-epsilon margin is no longer needed for that case; keeping it does no harm.
8. **Examples**: those in `docs/ejemplos/motor-v2/` are regenerated from the endpoints with all the new fields; Codex's v2 reader (`npm run test:motor-fundamental`) accepts them.

## 1. C0 — capabilities

`GET /motor/ensamblajes/capacidades?revision=2`, per package:

- Each combination carries a stable `id` (`una_fase`, `liquido_vapor`, `liquido_liquido`, `solido`, `region_critica`, `liquido_rigido_lleno`) and `evidencia`: `contrastada` | `cualitativa` | `imposible_en_el_modelo` | `sin_modelo` | `excluida`.
- Each package adds `componentesCAS`, `dominio` (the same as in `/motor/termodinamica/capacidades`), `limites` and, in NRTL, `pares` with provenance and evidence per binary.

| Package | one phase | LV | LL/LLV |
|---|---|---|---|
| `agua-iapws95` | cross-checked | cross-checked | — (solid: `sin_modelo`, ice exists only in statics; critical: `excluida`) |
| `mezcla-ideal` | cross-checked | cross-checked | `imposible_en_el_modelo` (g^E = 0), not published |
| `nrtl-chemsep` | cross-checked | qualitative (cross-checked only ethanol–water) | qualitative (VLE parameters) |
| `nrtl-lle-agua-butanol` | cross-checked | qualitative (LLE-only fit) | **cross-checked** (IUPAC SDS-15), published |

ChemSep pairs published: 13 of the 21 possible among the 7 species; those without parameters (e.g. water–benzene) do not appear and using them returns a diagnosis. The text "M5 pendiente" disappears; `noSoportado` says that ice is static only. The consistency test goes through the states of every run example and fails if any uses an unpublished combination of its package.

## 2. C1 — physical certification (`resultados.certificacion`)

`estado` (resuelto/parcial) is still **only** the numerical result. Certification is separate:

```ts
type CertificacionV2 = {estado: 'cumple'|'no_cumple'|'no_evaluable'; motivo: string;
  aspectos: {id: 'estados_termodinamicos'|'conservacion'|'cierre_constitutivo'|'segunda_ley';
             estado: 'cumple'|'no_cumple'|'no_evaluable'; motivo: string; referencias: string[];
             primeraMuestraNoCumple: number|null}[];
  alcance: {tInicial: number; tFinal: number; muestras: number; completa: boolean};
  ultimaMuestraCertificada: number|null};
```

- `conservacion`: the `global.*` residuals; `cierre_constitutivo`: `estado.*` and `mecanica.*`; `segunda_ley`: the existing check; `estados_termodinamicos`: every published sample passed its checks (one that does not pass stops publication and stays in the diagnostics).
- Global: `no_cumple` if any aspect does not comply; otherwise `no_evaluable` if any is not evaluable (second law without a boundary T); otherwise `cumple`. A non-evaluable second law is **not** presented as complied with, and it does not invalidate a correct energy balance.
- With `no_cumple`, the diagnosis `MOTOR_ENS_CERTIFICACION_NO_CUMPLE` (state `invalido`) is added to `validacion.diagnosticos`.
- **The trajectory is not trimmed**: all the evidence is kept; `primeraMuestraNoCumple` (index into `tiempos`) and `ultimaMuestraCertificada` mark the cut. The interface does not need to decide it.

Tests (§C1): nominal closed network → `cumple`; corrupted matter in one volume → `no_cumple` in `conservacion` with `global.materia.1`; corrupted energy (a spurious 1 W) → `global.energia`; 1 kW from a boundary at 300 K into water at 350 K → second law `no_cumple` from sample 1, conservation `cumple`; without a boundary T → `no_evaluable`, with no S_gen published; the same network ×1000 in matter, volume and conductance → the same residuals scaled in order of magnitude, the same T(t) and the same relative corruption detected.

## 3. C2 — series, events and naming

**`resultados.catalogoSeries`**: one entry per series (`variableId`, `propietarioId`, `unidadSI`, `magnitud`, `papel`, `variableEnsamblajeId`, `procedencia`). `papel` describes how the value is obtained: `estado_integrado`, `algebraica`, `dato`, `integral_auxiliar` (accumulated W) or `derivada` (mass, S, S_gen: presentation, with no equation of its own). `variableEnsamblajeId` points to `validacion.variables` or is `null`; the count (DOF) does not change. The role in the count is still in `validacion.variables`.

**Events** (`EventoV2`): `faseIds` = phases that appear or disappear (the volume's real IDs); additive `faseIdsAntes`, `faseIdsDespues`, `descripcion`. Events without a volume (stops) stay with `[]`. Codes:

- `aparicion_fase`, `desaparicion_fase`;
- `sustitucion_fase` (**new**): the same number of phases, one disappears and another appears (e.g. LL → LV at a heteroazeotrope). It used to be classified as `cambio_denominacion`, which was wrong;
- `cambio_denominacion`: only liquid/vapor ↔ supercritical fluid; the description says it is not evaporation, condensation or a first-order transition. Tested with water at 300 bar crossing Tc: H = H0 + Q t and monotonic T, with no plateau.

**Liquid IDs**: continuity by composition, with the assignment of least total distance (it used to be greedy and, when a single liquid was left, took the package's ID again). A liquid that appears receives a number never used before in the volume. Tested: when the dense phase (`liquido-1`) is exhausted by extraction, the organic one keeps `liquido-2` even though it is the only one; a second liquid that appears when feeding water receives a new ID; an absent phase is not published.

## 4. C3 — physical cross-checks

| Cross-check | Result |
|---|---|
| References shifted per species (ideal-gas h, s of ethanol and water) | identical T(t); H and S shift exactly Σ n_i Δh_i = 864.6 J and Σ n_i Δs_i = 5 J/K; events within the bisection's tolerance (1.5e-7 s) |
| h^E of the closure against −R T² Σ x_i ∂ln γ_i/∂T | agreement < 1e-5 relative |
| Partial molar enthalpies (∂(n h)/∂n_i) against h_i° − R T² ∂ln γ_i/∂T | < 1e-6 relative |
| Homogeneous superheated liquid | rejected by the vapor test (tm < 0) |
| TP flash with 4 different seeds (LL, LV, another composition) | the same minimum of G as the full flash |
| LLV plateau in PH with fraction 1e-6, 0.5 and 1 − 1e-6 | components, energy and volume reconstructed |
| Bubble point ± 1e-9 relative | certified on both sides |
| Stream with a negative flow | the donor becomes B and keeps its composition; one transfer with opposite signs |
| rtol 1e-6 / 3 samples against 1e-10 / 10 samples | events and final T agree |
| Limits | pair without parameters, P = 10 bar, liquid filling a rigid vessel, 150 K and extraction of an absent phase: rejected with a diagnosis |

**Defects found and fixed** (each with its regression):

1. Extracting vapor from a volume without vapor ended in `no_convergente` with `MOTOR_ENS_MUESTRA_NO_CERTIFICADA`, without saying why. It is now `invalido` with `MOTOR_ENS_DETENIDO_FASE_AUSENTE` (§C3).
2. Liquid IDs: with fewer liquids than earlier IDs, the assignment only considered the first IDs, and the surviving organic phase inherited `liquido-1` after the aqueous one was exhausted (§C2, decanter).
3. Cost: when bisecting the appearance of a second liquid, the PH flash's fallback searched T over the whole domain with a full TP per step; the LL appearance when feeding water did not finish in more than 30 min. Now `equilibrio_PH/UP` accept the integrator's seed: a local interval that widens ×4 until it brackets the root, and a seeded TP at each evaluation (falling back to the full TP). Root, certification and plateaus are the same: the case takes 3.6 s and the regenerated examples do not change beyond what is stated in §5.
4. Integrator without progress at a phase boundary: the watch saw the change of the phase set in the step's interpolant and the bisection placed it at t_e, but the state reintegrated up to t_e had not changed yet (they differ by ~rtol right at the boundary). No event was recorded, it restarted at t_e and detected the same thing again indefinitely: the decanter that exhausts the dense phase did not finish (> 35 min). Now, if the reintegrated state does not change at t_e, it advances with doubling steps from the bisection's resolution to the first instant at which it changes (or the step is accepted without an event if it does not change within it). The decanter finishes in 13 s with the event at the same instant (509.801 s) and certification `cumple`.

The limit of the event watch is still explicit in `metodo`: pointwise (3 interior points and the end of each step), not continuous.

## 5. Corrections of published values (compared with the earlier examples)

The examples in `docs/ejemplos/motor-v2/` were regenerated and compared field by field with the earlier version:

- After the C0–C2 changes: series, times, events and states **identical** (relative difference 0); only the scaled energy residuals change (the point after this group).
- After the seeded PH search (defect 3): only the ethanol–water heating changes. The event instants move by 5e-11 s and 7e-8 s (bisection tolerance 4.5e-7 s); the series by at most 2.5e-7 relative (U and W at the event's sample); the rest are residuals and tm of order 1e-16. The other examples only gain the field `potenciales.unidades`.
- After fixing the integrator (defect 4): every example **identical** to the earlier version.
- `residuos[].maximoEscalado` of `global.energia` and `estado.<v>.energia`: they change (≈ −11 % in the heating) because the energy scale goes from `max|ΣU|` to `max(|ΣU|, |∫E_ext|, |ΣW|)`. |U| depends on the reference's zero and can pass through 0; the new scale cannot. The tolerances do not change.
- Earlier, in this same series of deliveries, the scale of `global.materia.*` also added energies of the state vector (which made it insensitive); that is already fixed and documented.
- **Phase fractions** (Codex's incident, `binario-editado`): with a single phase, exactly 1 is published (identity) instead of a quotient that could give `1.0000000000000002`. Reproduced with Codex's request: maximum 1.0. The reader needs no margin for this case.
- **`PotencialesV2`** (Codex's incident): `base: 'molar'` and `unidad: 'J/mol'` refer only to μ. G, A and S have always been extensive quantities of the volume (J, J, J/K); `unidades: {mu, G, A, S}` and an erratum in the type are added. The values do not change.

## 6. C4 — design (not implemented)

See [docs/engine/open-boundary-water-air-design.md](open-boundary-water-air-design.md): why pure water at 10 °C cannot be at 1 atm with a vapor space; the proposed package (IAPWS-95 for water in both phases, gas with a truncated virial, air declared insoluble) and why the ideal gas is not enough (Z_sat − 1 of −1.5 % at 100 °C); initialization by P0 that calculates the air; sealed; the open boundary as an index-2 DAE with explicit F after differentiating the constraint, projection and residual `mecanica.<v>.presion`; reversal regime; the data needed, with sources; test plan. The typed draft compiles against revision 2 and its example request (`docs/ejemplos/borrador-frontera-abierta/olla-abierta-peticion.json`) **is rejected** by the current service, checked in §C0.

## 7. Tests

| Test | Result |
|---|---|
| `python tests/validar_motor_consolidacion_v2.py` | OK: C0 56, C1 14, C2 31, C3 27 |
| `python tests/validar_motor_ensamblaje_v2.py` | OK, 114 |
| H1 / H3 / assembly v1 | OK, 585 / 3729 / 245 |
| `node tests/verificar_contrato_ensamblaje_v2.mjs` (includes the C4 draft) | OK |
| `node tests/verificar_contrato_ensamblaje.mjs`, `verificar_contrato_motor_termodinamica.mjs` | OK |
| `npm run test:motor-fundamental` (frontend, unmodified; includes Codex's v2 reader) | OK |

No complete frontend regression is claimed while its integration is in progress (`npm test` and `tsc` belong to Codex).

## 8. Files touched

`backend/motor_ensamblaje_v2.py`, `backend/motor_mezclas.py`, `core/ensamblaje_red.py` (classification of events and progress at boundaries), `core/mezclas.py` (seeded PH/UP), `docs/contratos/contratoEnsamblajeV2.ts`, `tests/validar_motor_consolidacion_v2.py` (new), `tests/verificar_contrato_ensamblaje_v2.mjs`, `docs/ejemplos/motor-v2/*` (regenerated), `docs/ejemplos/motor-termodinamica-capacidades.json` (regenerated, unchanged), this document, [docs/engine/open-boundary-water-air-design.md](open-boundary-water-air-design.md), `docs/contratos/borradorFronteraAbierta.ts`, `docs/ejemplos/borrador-frontera-abierta/olla-abierta-peticion.json`.

## 9. Remaining incidents

- Almost-azeotropic bubble/dew points at ~1e-12 K: the engine can refuse to certify (`no_convergente`).
- The stability test is a grid with refinement, not a proof of the global minimum; it publishes the candidates explored and the number of tests.
- Pointwise event watch: a transition that appears and disappears between two watched points of a step is not detected.
- All of C4 (water + air package, initial state by pressure, flow by constraint).
