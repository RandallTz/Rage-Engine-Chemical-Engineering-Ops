# Common results format and charting engine

18 October 2026. Step 3 of [ARCHITECTURE.md](../../ARCHITECTURE.md) §10. Every calculation engine publishes its results in this format, and the single charting engine draws them without knowing where they come from.

## 1. The format (`rage.resultados`, v0)

```ts
{ formato: "rage.resultados", version: 0, id, nombre, modeloId | null,
  estado: "resuelto" | "parcial" | "fallido",
  procedencia: { motor, metodo | null, firma | null, mensaje?, pasos?, rechazos? },
  ejes:   [{ id, nombre, rol: "tiempo" | "coordenada" | "parametro" | "otro", unidadSI, dimension, valores }],
  series: [{ id, nombre, unidadSI, dimension, magnitudes, ejes: [ejeId…], valores,
             propietarioId?, componenteId?, faseId? }],
  eventos: [{ codigo, ejeId, valor, descripcion, propietarioId? }],
  verificaciones: [{ id, valor, tolerancia, descripcion }] }
```

Field names are part of the published JSON format and stay in Spanish ([docs/repository-cleanup/README.md](../repository-cleanup/README.md) §7, D3).

**Equilibrium evidence (24 October 2026, v2 migration step c).** Common equilibrium runs add three optional provenance fields without changing existing v0 keys: `physicalCertification`, `equilibrium` and `diagnostics`. `equilibrium` retains the shared revision-2 result payload: aligned sample times, series and catalog roles, certified states/potentials, phase identities and event sides, residuals, second law, aggregate certificate and package fingerprints. `physicalCertification` is the same certificate, exposed directly for consumers. `diagnostics` retains typed native publication/stop codes. Other common result families need not supply these fields.

`estado: resuelto` describes numerical completion only. Physical status is independently `cumple`, `no_cumple` or `no_evaluable`; a failed work or second-law check remains visible with its first failure and last certified sample. Missing boundary temperature does not certify the second law. A closure exception truncates publication to the available certified prefix (`parcial`); no publishable sample yields `fallido`, empty series and a null certificate. Python and TypeScript readers check certificate aggregation, actual time scope and exact agreement between the common series and their retained evidence. They do not recalculate physics in the browser.

The shared publisher is `backend/assembly_results.py`, reused by native v2 and `core/compilador/network_results.py`; the latter integrates through common RK45/BDF. Native routes and their existing certificate warning remain unchanged until the compatibility-adapter step. Full adapter identity aliases and the remaining supercritical-water parity finding are tracked in [the migration contract](../engine/dynamic-assembly.md#13-v2-compatibility-adapter-contract).

- **Axis (`eje`):** any independent variable: time, a coordinate, the parameter of a continuation, a wave number…
- **Series:** depends on 0, 1 or 2 axes. Its `valores` have the shape of those axes (the first one is the outer index), and `null` means "not defined", never an invented number.
- **Units:** SI, with their exact dimension, given by the units service ([docs/contracts/units-service.md](units-service.md)).
- **No bias:** no field knows about tanks, columns or reactors. The physical origin of a series is stated by `propietarioId`, `componenteId` and `faseId`, as data.

**Code**

- Python: `core/resultados/` (`formato.py`: construction and strict reader; `adaptadores.py`).
- TypeScript: `frontend/motores/resultados/` (`contrato.ts`, `lector.ts`, `desdeMotor.ts`).

**Who publishes it today**

| Engine | How |
|---|---|
| Simulation of the nondimensionalization core | Directly, in `estudio.simulacion.resultados`: the dimensionless formulation (τ, ξ, unit 1) and the original variables in SI with their unit |
| Thermodynamic assembly v2 | Adapter `core.resultados.desde_ensamblaje_v2`, without loss |
| The engine's TS solver | Adapter `resultadosDesdeMotor`, without loss; it asks the units service for the dimensions |
| Common compiler (`POST /modelo/resolver`) | Directly; the Engine's Resolver reads it ([docs/engine/vertical-slice.md](../engine/vertical-slice.md)) |

## 2. Charting engine (`frontend/componentes/graficas/`)

- **`datos.ts` (pure):** `datosGrafica(conjunto, especificacion)` produces curves, and `especificacionesPorOmision(conjunto)` groups by dimension and axes. The specification is `{x: {eje} | {serie}, y: [series], fijar?: {eje, indice}}`. Generic rules:
  - one dimension per y axis;
  - a series of two axes needs one of them fixed (a profile at an instant, or the evolution at a point);
  - one series against another works as a phase diagram if they share an axis.
- **`Grafica.tsx`:** the project's only SVG renderer. Nondimensionalization's simulation and stability views use it.
- **`GraficaResultados.tsx`:** joins the two pieces above. Axis titles come from the published quantity and unit, for example "densidad (kg/m^3)".

The old `GraficoXY.tsx` of nondimensionalization is archived in `docs/history/archive/nondimensionalization-2026-10-18/`. The existing Engine dashboard (`frontend/app/motor/TableroMotor.tsx`) retains its renderer until the common renderer migration. For evaluated-series results, its initial charts now group the actually published variable IDs by group/unit metadata; they do not assume `U`/`T` or another physical family exists. Saved chart specifications remain user preferences. Model source-history navigation preserves those preferences while invalidating scientific execution when required.

### Nonlinear algebraic execution evidence (F3, 28 October 2026)

Derived-execution version-3 runs add optional `procedencia.nonlinearDiagnostics` with `{version:1, method:"damped_newton", sourceSignature, settings, evaluatedSolves, lastEvaluation, failures, publishedSamples, scope}`. `settings` equals the selected nonlinear settings in the compilation report. `lastEvaluation` and each failure retain the equation/quantity IDs, stage, path, model/source/formulation signatures, time, iterations/evaluations/backtracks, residual/step norms, condition estimate and termination reason; unavailable numerical measures are `null`, never nonfinite JSON. Failures additionally require matching `code`/termination reason and a message. The scope explicitly states that finite deterministic probes are not global uniqueness certification.

Python and TypeScript readers reject unknown envelope/diagnostic fields, invalid counters or nonfinite metrics, mismatched selection/settings/signatures, inconsistent publication sample counts and failures attached to `resuelto`. The common optional F0 result signature still binds all evidence and values. Existing v0 results without this field remain readable. This metadata does not alter revision-2 `executionProvenance` or thermodynamic certification.

Each publishable sample contains freshly solved `observable.<algebraicQuantityId>` values and `algebraic.residual.<equationId>` series in the original row's SI unit. `algebraic.scaled_residual` checks the maximum original residual divided by the declared dimensioned row scale against the requested Newton tolerance. Conservation retains the existing inventory/net-rate verification. Publication failure truncates all aligned series to the verified numerical prefix; zero publishable samples yield `fallido`. A converged algebraic residual supplies no equilibrium, uniqueness or physical certificate.

## 3. Verification

### Optional staged assessment (F0 step 2)

New common Solve requests may opt into `procedencia.assessment`, the `rage.model-assessment` v1 envelope defined in [common-model.md](common-model.md#staged-model-assessment-f0-step-2-28-october-2026). Existing Results v0 keys and `estado` are unchanged. Structure, initialization and certification are independent verdicts: `resuelto` still means numerical completion, including when the physical certificate says `no_cumple` or `no_evaluable`.

`physicalCertification`, when present, is authoritative: `cumple`, `no_cumple` and `no_evaluable` map to typed certification `passed`, `failed` and `not_evaluable`. Failed or unavailable aspects retain located diagnostics. Without physical evidence, successful initialization and numerical checks never imply a physical pass; failed published numerical checks yield `failed`, otherwise certification is `not_evaluable`. Before execution it is `not_evaluated`. Scope records numerical status, completion, sample count and the actual first/last published time. A partial trajectory certifies at most its published prefix.

`resultSignature` is SHA-256 of the complete result's canonical sorted-key UTF-8 JSON excluding only `procedencia.assessment`. The Python result reader validates the envelope's version, typed pairs, common model/stage identities, result signature and certification against actual published evidence. Editing a sample or substituting a successful certificate therefore invalidates the attachment. Existing records without an assessment remain valid and carry no inferred stage pass. Frontend typed assessment readers and rejected-attempt storage are deferred to approved F0 step 3; the native v2 adapter is unchanged.

`tests/test_model_assessment.py` exercises the audit's missing-data, missing-equation, out-of-domain and conflicting-initialization cases; it also checks source/result staleness, HTTP transport, partial scope, optional legacy-compatible metadata and the same initialized network with three distinct physical certificates.

- `python tests/validar_resultados.py` (34 checks):
  - the four v2 assemblies keep times, values, metadata, events and residuals;
  - the core simulation publishes identical fields and restitution;
  - six reader rejections.
- `node verificar_resultados_graficas.mjs` (175 checks):
  - the TS solver's 8 results, the assembly's 4 and the core's one pass the TS and Python readers;
  - they are drawn with the same code, and each curve is exactly the series;
  - the generic rules hold.

### Optional index-one DAE evidence (F3)

Version-4 derived runs require `procedencia.daeDiagnostics` with exactly `{version:1, method:"scipy_bdf_nested_newton", acceptedChecks, maxResidual, maxConservation, driftTolerance, scope}`. Counters are nonnegative integers; numerical metrics are finite and nonnegative. The tolerance matches the pinned selection. The maximum accepted scaled algebraic residual cannot exceed it, and the accepted conservation maximum cannot exceed `1e-6`. A completed run needs at least one accepted-state check. Python and TypeScript readers reject missing, malformed or inconsistent evidence.

The existing `nonlinearDiagnostics` remains required by the producer and supports selections 3 and 4; its failures locate DAE drift/domain failures as well as nonlinear stops. The compilation attachment contains the exact index certificate, state box and fixed-state initialization strategy. Existing physical state, algebraic observable, SI residual and conservation series are reused. The F0 result signature covers the new evidence. No executionProvenance key, physical certificate or legacy result status changes.

`maxResidual` covers successful RHS and publication checks as well as accepted endpoints; `maxConservation` covers checked internal endpoints and published samples. These are scoped numerical checks, not a proof of global branch uniqueness, continuous between-sample bounds or physical equilibrium. A rejected endpoint never enters the retained trajectory. Publication solves algebraic variables afresh on the differential interpolant and truncates on failure; zero publishable samples are `fallido`.

### Optional steady-state evidence (F3, 29 October 2026; in review)

A successful v5 derived solve publishes motor `rage.compilador.steady`, method `damped_newton`, `estado:"resuelto"`, `ejes:[]`, no events and finite **numeric scalar** series. IDs are `steady.<quantityId>` for free unknowns, explicit invariants and reconstructions, and `steady.residual.<equationId>` for original SI residuals. No fake time samples, temporal budget integral or partial iterate is published. Rejections use HTTP 422 and the separate rejected-attempt store.

`procedencia.compilation` is the strict steady version-2 report. Required `steadyDiagnostics` fields are `version:1`, `verdict:"local_regular_root"`, `globalUniqueness:"not_proved"`, `method:"damped_newton"`, source/formulation/data/settings/compilation signatures, ordered `quantityIds`/`equationIds`, `variableScales`/`residualScales`, `smallestSingularValue`, `conditionThreshold`/`inverseThreshold` (both `1e-8`), `relativeAmplification`, `inverseAmplification`, `initialResidualNorm`, `solver`, `scope`, `resultSignature`. The solver object retains `iterations`, `evaluations`, `backtracks`, `residualNorm`, `stepNorm`, `conditionInfinity`, `terminationReason`, `completedProbes`, `uniqueness`. Counters describe the primary iterations/backtracks and total attempted evaluations including probes; failed probes prove nothing. Neither numerical regularity nor completed finite probes certify global uniqueness, physical equilibrium or dynamic stability.

Checks include `steady.scaled_residual` at the requested Newton residual tolerance, `conservation.<equationId>` and `invariant.<quantityId>` at `1e-6`. Python and TypeScript readers enforce exact field sets, version/selection/signature/order agreement, finite scalar values, declared units/bounds/invariants, residual scaling, both convergence criteria and fixed conditioning gates. The result fingerprint uses the steady binary64 normalization defined in common-model.md, covering the entire result except `procedencia.assessment` and the fingerprint field itself. F0 assessment remains independently attached and cannot turn numerical completion into physical certification.

The saved Engine wrapper is explicitly **version 2**, `modo:"steady"`, with the complete common result and matching compilation/checks. Compatibility fields `tiempos`, `x`, `valores` and `componentes` are empty; no values are interpreted as a trajectory. Version-1 temporal wrappers remain readable. Existing Results renders a scalar quantity/unit/value table, numerical diagnostics, original residuals and a CSV with no time column. Storage validates the wrapper and common publication on save and reload. Selection/data/source changes invalidate old results; cancellation and rejected attempts use the existing shared lifecycle.
