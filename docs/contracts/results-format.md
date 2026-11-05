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

Derived runs with a package closure (31 October 2026) add the following results:
- `procedencia.thermodynamicClosures`, the closure rows of the compilation report;
- `procedencia.reactionEquilibrium`, the equilibrium-limit details of kinetic volumes;
- `closure.<volumeId>.<quantityId>` series for the closure outputs (T, P or V, phase amounts, compositions, molar h/u/v/M, presence, liquid volume);
- the checks `thermodynamics.closure.<volumeId>` and `reactions.equilibrium_limit.<volumeId>`.

Phase-set changes are published as `aparicion_fase` and `desaparicion_fase` events with `propietarioId: "volumen:<id>"`. The client result reader accepts these as ordinary series, checks and provenance. The existing Results Numerical diagnostics lists published time events with their description and owner (including `volumen:<id>`), reusing assembly event labels. Time charts show markers at the published event times on the selected y axis; spatial profiles and plots against another variable do not receive time markers. No events are reconstructed from series or inferred between samples.

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

Kinetic zero-accumulation publications optionally declare `compilation.kineticDiagnostics = {version: 1, volumeIds: [...]}`. Identities are unique, nonempty and refer to package-closure volumes with a formation anchor. Exactly one finite nonnegative `reactions.equilibrium_limit.<volumeId>` verification with tolerance `1e-3` is required for each declared volume. It reports distance to the chemical-equilibrium limit and may exceed its tolerance at a continuously driven operating point; it does not relax numerical residuals, mass conservation, physical domains or closure certificates. For open volumes the reference uses the current element inventory, because material transport changes the initial inventory. Readers reject missing/duplicate diagnostics, unknown owners/fields, wrong versions, negative/nonfinite values and changed diagnostic tolerances. Reports without this optional record retain the previous exact verification set. No existing persisted key is renamed.

A successful v5 derived solve publishes motor `rage.compilador.steady`, method `damped_newton`, `estado:"resuelto"`, `ejes:[]`, no events and finite **numeric scalar** series. IDs are `steady.<quantityId>` for free unknowns, explicit invariants and reconstructions, and `steady.residual.<equationId>` for original SI residuals. No fake time samples, temporal budget integral or partial iterate is published. Rejections use HTTP 422 and the separate rejected-attempt store.

`procedencia.compilation` is the strict steady version-2 report. Required `steadyDiagnostics` fields are `version:1`, `verdict:"local_regular_root"`, `globalUniqueness:"not_proved"`, `method:"damped_newton"`, source/formulation/data/settings/compilation signatures, ordered `quantityIds`/`equationIds`, `variableScales`/`residualScales`, `smallestSingularValue`, `conditionThreshold`/`inverseThreshold` (both `1e-8`), `relativeAmplification`, `inverseAmplification`, `initialResidualNorm`, `solver`, `scope`, `resultSignature`. The solver object retains `iterations`, `evaluations`, `backtracks`, `residualNorm`, `stepNorm`, `conditionInfinity`, `terminationReason`, `completedProbes`, `uniqueness`. Counters describe the primary iterations/backtracks and total attempted evaluations including probes; failed probes prove nothing. Neither numerical regularity nor completed finite probes certify global uniqueness, physical equilibrium or dynamic stability.

Checks include `steady.scaled_residual` at the requested Newton residual tolerance, `conservation.<equationId>` and `invariant.<quantityId>` at `1e-6`. Python and TypeScript readers enforce exact field sets, version/selection/signature/order agreement, finite scalar values, declared units/bounds/invariants, residual scaling, both convergence criteria and fixed conditioning gates. The result fingerprint uses the steady binary64 normalization defined in common-model.md, covering the entire result except `procedencia.assessment` and the fingerprint field itself. F0 assessment remains independently attached and cannot turn numerical completion into physical certification.

The saved Engine wrapper is explicitly **version 2**, `modo:"steady"`, with the complete common result and matching compilation/checks. Compatibility fields `tiempos`, `x`, `valores` and `componentes` are empty; no values are interpreted as a trajectory. Version-1 temporal wrappers remain readable. Existing Results renders a scalar quantity/unit/value table, numerical diagnostics, original residuals and a CSV with no time column. Storage validates the wrapper and common publication on save and reload. Selection/data/source changes invalidate old results; cancellation and rejected attempts use the existing shared lifecycle.

Inverse steady publication is admitted through the same HTTP routes (1 November 2026). The strict compilation adds paired `specificationSignature` and `inverseSpecification` fields over the unchanged forward v5 selection (see common-model.md). `steadyDiagnostics.inverseSpecification = {specificationSignature,freedInputs,specificationRows,seedRegularity}` must match the report exactly. Unknowns and scales follow forward unknowns then freed inputs; residual rows/scales follow original rows then `specification.<id>`. Finite scalar series add `steady.<freedInput>` and `steady.residual.specification.<id>`. Each specification residual must equal its published output minus the declared SI target within `8*epsilon*max(1,abs(output),abs(target))`. The report also validates targets, appended scales, guesses and bounds against the carried declarations. The whole result signature includes this evidence; re-signing does not bypass these semantic checks. Seed regularity is compared with the diagnostics, not recomputed without the model. Existing Results shows solved freed inputs and specification residuals in its scalar table and CSV, with the inverse targets and freed-input context in the existing compilation summary. Errors and reachability evidence use the existing rejected-attempt store; a failed attempt never becomes an accepted scalar result.

Steady package closures (RT-1, 2 November 2026): the v2 compilation closure output list determines the required scalar `closure.<id>` series and their units. `steadyDiagnostics.thermodynamicClosures` retains the package diagnostic row plus `phaseSet`; its ordered volume identities and package/mode/specification/anchor/liquidOnly must agree with compilation. Each volume requires `thermodynamics.closure.<volumeId>` verification with tolerance 1 for equilibrium certificates or 1e-9 for a declared single phase. Missing, extra or mismatched evidence is rejected.


## Optional versioned result chart layout (Demo 0.3 groundwork, 2 November 2026)

A saved model may carry optional `resultCharts: {format:"rage.result-charts",version:1,charts:[...]}`. This is presentation metadata, not a new scientific result format. Each chart is `{id,title,type,series:[{source:"current"|"reference",id}],x?,y:{unit},events:boolean}`. `type` is exactly `time_series`, `xy`, `parametric`, `bar` or `table`. `id` is a stable unique chart identity; series selections use exact common result series IDs, never display labels. A layout has at most 100 charts, each with 1..100 unique series selections. Unknown keys, versions and types reject at every record level. An absent record leaves existing `graficas` layouts untouched. The explicit versioned reader never guesses a migration from an old layout or silently drops an invalid new layout. The Results opt-in action creates a new v1 record from published metadata and retains the old layout for switching back.

Line/phase charts require `x:{kind:"axis"|"series",id,unit}`; bar/table forbid x. Time-series charts require a published time axis; parametric plots require a sampled x series. X and Y must share the same published sampling axis and sample count; no interpolation, resampling or inferred trajectory is performed. `xy` accepts either aligned axis or series X. Bars show the final published sample (or the scalar steady value), including null as undefined; tables show the published samples independently for each selected series. All curves retain null gaps. In v1, a chart uses one Y unit: incompatible dimensions reject through the shared Python units service rather than plotting misleading axes.

`events:true` is admitted only for time-series charts. Markers retain the published event coordinate, code, description and physical owner and use the same converted X unit. No synthetic event time or interpolated crossing is computed. Parametric plots use matching composition series, such as liquid x_i and vapour y_i; absent-phase nulls remain undefined.

An explicit `chartReference:{version:1,result:<strict common result>}` pins an overlay reference. Its versioned reader validates the result; pinning never replaces the current simulation result or marks old evidence current. Source labels and result identity remain visible. `series[].source` selects current or reference data. A scalar steady series overlaid on a sampled time plot is rendered as a constant reference across the sampled X extent, not as a simulated trajectory. A standalone steady result uses bar/table. A time plot consisting only of scalars rejects. Dynamic reference trajectories retain their own published samples. Missing reference IDs, mismatched axes and incompatible units reject visibly. Saved layout edits and explicit references are presentation-only and do not invalidate physical solves; structural/data changes continue to invalidate actual results through their existing signatures.

`POST /modelo/chart-data` is presentation conversion, not result certification. It accepts `{format:"rage.chart-data.request",version:1,resultId,requests:[{kind:"axis"|"series",id,unit,sourceUnit,values,events}]}` from the strict TS result reader's selected rows. Python validates the payload and calls the single `core.unidades` service for both source and target units, including affine K/degC. Values are finite scalars, null or one-dimensional lists; nested arrays reject. Only axis selections carry events. The response is `{format:"rage.chart-data",version:1,resultId,rows:[{kind,id,unit,dimension,values,events}]}`. The client checks selection identities, shape and finite data before rendering. The original result, units, certificates and signatures are unchanged; converted display values are not persisted as scientific results.

Scope: scalar and nonspatial sampled results. Coordinate axes, multi-axis series, meshes and spatial chart types reject in v1. A later explicit chart version may add mesh/topology references; no dormant spatial renderer or inferred mesh is introduced now. Existing Results/TableroMotor owns rendering and controls; there is no new page.

Assessment result fingerprints (2 November 2026): optional `resultSignatureVersion: 2` on `rage.model-assessment` v1 uses a recursively type-tagged canonical tree: objects sorted by key, arrays in order, numbers as finite binary64 hexadecimal bytes with zero normalized to positive zero, and other scalars unchanged. SHA-256 covers the result excluding `procedencia.assessment`. New publications declare version 2. An absent field preserves legacy version-1 decimal-JSON validation; explicit 1 is also admitted. Unknown versions and a version without a result signature reject. This changes transport identity only, not physical certification; changes to any published value or evidence still invalidate the signature.

## Indexed network publication (optional versions 1 and 2)

The existing `rage.resultados` v0 may carry `indexedNetwork`. Absence preserves every existing result. An explicit null, unknown fields or unknown extension version rejects. The extension is `{version:1,indexSetId,count,mode,stageAxisId,stages,endPorts,profiles}`. `count` is a positive safe integer; `mode` is `dynamic` or `steady`. It describes published data, not a deduction, expansion request or permission to execute a network.

`stages` has exactly n ordered rows `{index,ownerId,seriesIds,closures}`. Index j starts at 1. Its canonical owner is `<indexSetId>.stage.<j>`. Every referenced series ID begins with that owner followed by a dot and has the same `propietarioId`. Stage series IDs are distinct and nonempty. This namespaces quantities from arbitrary templates without equipment-specific identifiers. Steady stage series are scalar; dynamic series retain the ordinary published axes and samples. Events retain their existing time coordinate and stage-qualified owner; the extension does not invent or interpolate events.

Each stage's `closures` lists `{volumeId,mode,verificationId}`. `volumeId` starts with `<stageOwner>.volume.` and is unique within the stage. `mode` is `equilibrium` or `single_phase`. `verificationId` references the existing common verification `thermodynamics.closure.<volumeId>`, preserving its fresh package certificate summary. The ratio is finite and nonnegative; tolerance is 1 for equilibrium and 1e-9 for a single-phase energy reconstruction. A resolved result cannot carry a failing closure summary. Empty closures mean the stage has no package closure; publishers must not omit an executed closure. This reference retains the existing certificate semantics, not a new physical proof or predictive-validity claim. Full package details remain the existing closure adapter's responsibility.

`endPorts` contains distinct `{portId,stage,kind,direction,variables}` rows, attached only to stage 1 or n. Kinds are `material`, `heat`, `work`; directions are `inlet`, `outlet`. Material variables are `{flow,composition:[seriesId,...],temperature,pressure,specificEnthalpy}`. Power ports use `{power:seriesId}`. All bindings refer to distinct published series owned by that stage. SI units are respectively kg/s or mol/s, 1, K, Pa, J/kg or J/mol; flow and specific enthalpy must use the same mass/mole basis. Power uses W. These are exposed boundaries only; internal links are not republished as end ports. No client evaluates a stream law.

Version 2 retains every version-1 field and requires an additional `sidePorts` array. Its rows have the same strict structure and SI rules as `endPorts`, but their integer stage must satisfy 1 < j < n. Port identities are unique across both arrays; bindings must belong to the indicated stage. This exposes side withdrawals and heat/work boundaries of interior stages without mislabelling them as ends. For n=1 or n=2 the array is empty. Version 1 continues to reject `sidePorts`; there is no implicit migration. Stage-profile and certificate rules are unchanged.

For dynamic results `stageAxisId` is null and `profiles` is empty. For steady results `stageAxisId` names an existing dimensionless axis with role `parametro`, unit `1` and values exactly `[1,...,n]`. Each profile `{seriesId,stageSeriesIds}` references one distinct index-set-owned series over that axis and exactly one scalar source from each stage in index order. Its values, units and dimensions must equal those sources exactly, including null values. Thus T_j, x_ij and y_ij are ordinary series; the existing version-1 `xy` chart selects the j axis and profile ID. This is not a spatial mesh and needs no chart-layout migration. Source signatures and assessments must be computed after this extension is attached; it is covered by the existing whole-result fingerprints.

Contract tests assemble temperature publications from the shared-authored thermal chain and exercise both strict readers and the existing x-y chart reader. Actual connected-network publication uses the same extension: per-stage quantities come from the global trajectory or zero-accumulation root, with fresh certificates evaluated at those states. The recorded discharge relations are now available; enabling the common HTTP route still requires the complete network selection and compilation evidence.

Boundary values without an authored binding remain null, following the common result contract. In particular, the current drum discharge path provides component flow and specific enthalpy but does not determine a downstream temperature and pressure pair. Publication must not copy the donor temperature across that path or perform an undeclared flash. Such missing series are listed in the internal publisher's version-1 `procedencia.networkEvidence.unresolvedPortSeries`; this diagnostic is not a replacement for compilation evidence. Stage temperature and composition profiles use the closure outputs of each stage volume and remain available.
