# Common model contract · v0

18 October 2026. It is the base piece of [ARCHITECTURE.md](../../ARCHITECTURE.md) §4: the only language all the engines speak.

v0 is **a representation, not a new engine**: it defines the document, its strict reader and the always-present structural relations. It checks that the three existing formats fit in it without loss. Since then the Engine's Resolver and the balance engine consume it (ARCHITECTURE.md §10, step 5).

- **Python, canonical:** `core/modelo/` (`lector.py`, `relaciones.py`, `adaptadores.py`).
- **TypeScript:** `frontend/motores/modelo/` (types, reader and adapter from the engine's sheets).
- **Tests:** `tests/validar_modelo_comun.py` and `frontend/verificar_modelo_comun.mjs`.
- **Examples:** `docs/ejemplos/modelo-comun/`.

Field names are part of the published JSON format (`rage.modelo`) and stay in Spanish ([docs/repository-cleanup/README.md](../repository-cleanup/README.md) §7, D3).

## 1. Document

```ts
type Modelo = {
  formato: "rage.modelo"; version: 0;
  id: string; nombre: string;
  componentes: Componente[];                 // chemical identity; no properties
  termodinamica: { paquetes: Paquete[] };    // packages configured by local id
  volumenes: Volumen[];                      // regions with conserved quantities
  corrientes: Corriente[];                   // transport of matter (and its enthalpy)
  intercambios: Intercambio[];               // heat between volumes or with the surroundings
  datos: Record<string, Dato>;               // every physical value, with unit and origin
  matematico: ModeloMatematico | null;       // explicit equations (typed tree)
  estudio: Estudio | null;                   // which calculation is requested and with which settings
  motores: Record<string, unknown>;          // each engine's own configuration, by namespace
  procedencia: Procedencia;                  // where this model comes from
};
```

### Physical pieces

- **`Componente`**: `{id: integer, nombre, simbolo, identidadQuimica?: {cas?, proveedorId?}, masaMolar?}`. The same as in the engine.
- **`Paquete`**: `{id, modelo: {id, version}, datosPuros?}`. `modelo` names a package published by `/motor/termodinamica/capacidades`; `datosPuros` carries the accepted substitutions (v_L, ideal Cp, Psat).
- **`Volumen`**:
  - `id`, `componenteIds`;
  - `balances: {materia, energia, momento}`;
  - `supuestos: {materia: FormulacionMateria, energia: FormulacionEnergia | null}`: the engine's reduction flags, which are the input of the assumptions engine;
  - `frontera`: `rigida`, `presion_prescrita`, `sin_relacion` or `malla_1d`;
  - `inicial`: initial amounts and energy by data id, or `{tipo: "por_datos"}` when the initial values are field data;
  - **`termodinamica: Cierre`, required** (§2).
- **`Corriente`**:
  - the shape of revision 2 of the assembly: `id`, `desde`, `hasta` (null = surroundings), `componenteIds`, `mecanismo`, `materia`, `estadoExterior?`, `extraccion?`;
  - plus `constante?` (ports of the TS engine), a `volumetrica` basis (dV/dt = Q) and `datoIds` per component.
- **`Intercambio`**: `{id, desde, hasta, ley: {tipo: "impuesto", potenciaId} | {tipo: "conductancia", conductanciaId, temperaturaExteriorId?}, temperaturaFronteraId?}`.
- **`Dato`**: `{magnitud, funcion: "inicial" | "frontera" | "geometria" | "estudio" | "parametro", declaracion: {texto, unidad}, origen: {propietarioId, ruta}}`. `texto` accepts a number or an engine expression; the unit applies to the result.

### Everything else

- **`ModeloMatematico`**: exactly the `modelo` of the nondimensionalization v2 document: `{id, revision, simbolos, funciones, ecuaciones, dominios, condiciones}`, with the `Expresion` tree of `frontend/app/adimensionalizacion/contrato.ts`. It is validated with `core.adimensionalizacion.lector.leer_modelo(version=2)`. It is `null` when an engine generates the equations from the structure (the assembly case, §3).
- **`Estudio`**:
  - transient: `tipo: "temporal"`, `tiempoId`, `metodoSolicitado`, `muestras`, `rtol`, `atol: {cantidad, energia?}`;
  - optional: `espacial?: {celdas, frontera}` and `cierreMasico?`.
- **`motores`**: each engine's configuration under its name. Today only `adimensionalizacion: {version, formas, activaId, exploracion?, execution?}`. An engine never writes outside its namespace. Optional `execution` explicitly selects scaled execution; its absence preserves the physical execution path. See §7.
- **`restricciones?`** (optional, 18 October 2026): `[{simboloId, tipo: "no_negativo"}]` on field variables of `matematico`. The calculation stops at the instant one of them would leave its domain (code `agotamiento`); it is never clipped. Without a declared restriction the equation continues: the domain belongs to the model, not to a hidden solver rule.
- **Values of `matematico`**: each parameter or constant of the tree takes its value from `datos["matematico.<id>"]` (`funcion: "parametro"`, `origen: {propietarioId: "matematico", ruta: "matematico.simbolos.<id>"}`), in any unit compatible with the symbol's dimension. They used to travel in `procedencia.valoresMatematico`, which no longer exists.
- **Balance engine** (optional fields, 18 October 2026; see [docs/engine/balance-engine.md](../engine/balance-engine.md)):
  - volume: `terminos` (`"generacion.<id>"`, `"consumo.<id>"`, `"resto.<id>"`, `"calor"`, `"trabajo_viscoso"`, `"fuerzas"`, `"fuente"` → datum);
  - volume: `volumenDatoId`;
  - volume: `inicial.energia`, optional without an energy balance;
  - assumed closure `u_lineal`: `parametros: {cId, uRefId, TRefId, TMinId, TMaxId, rhoId?}`;
  - stream: `materia.modo = "total_y_composicion"` with `caudalId` and `fracciones`;
  - `restricciones`: besides `{simboloId, tipo}`, the form `{expresion, tipo: "no_negativo", descripcion}`, an expression of the variables that must stay ≥ 0 (the validity domain of an assumption).
  - A model with assumed-state volumes and `matematico: null` is solved by `POST /modelo/resolver`, which first generates its equations with the balance engine.
- **`observables?`** and **`verificaciones?`** (optional, on the variables of `matematico`):
  - `observables: [{id, nombre, unidadSI, expresion}]` are published as series `observable.<id>`;
  - `verificaciones: [{id, descripcion, expresion, escala, tolerancia?}]` are published in the result's `verificaciones`, with value max|expresion| / max|escala| over the samples;
  - the balance engine generates both: temperature, flows and donor enthalpies; budget closures per state and global.
- **`Procedencia`**: `{tipo: "documento_adimensional" | "ensamblaje_v2" | "hoja_motor_materia" | "nuevo", ...}` with the identifiers of the origin (`solicitudId`, `hojaId`, `documentoId`), its `version`, and what is not physics but must be kept (`derivacion`, steps of the path).

## 2. Always-present thermodynamics

Every volume declares its closure. Not declaring it is a **read error**, not a default value:

```ts
type Cierre =
  | { tipo: "equilibrio"; paqueteId: string; politica: PoliticaEstado }
  | { tipo: "supuesto"; supuesto: "fase_no_evaluada" | "u_lineal"; motivo: string };
```

- **`equilibrio`**: the state comes from the package at every evaluation, through the UV closure (rigid boundary) or the PH closure (prescribed pressure). The phases are obtained as a result, and the one that is not present has zero amount with the same equations (see the architecture, §3).
- **`supuesto`**: the engine that generated the model does not evaluate the state (for example, the browser's matter solver) or uses a manual relation. It is written down with its reason and appears as a relation of family `estado` marked `supuesta`, so that the gap is visible and not forgotten.

`relaciones(modelo)` (`core/modelo/relaciones.py`) generates the structural list of relations of a physical model, always the same for the same structure:

| For | Relations (id · family) |
|---|---|
| volume with `equilibrio` | `estado.V.energia` · estado (UV or PH closure), `estado.V.volumen` · estado, `equilibrio.V` · equilibrio; with prescribed pressure, also `estado.V.U` · estado and `mecanica.V.trabajo` · mecanica |
| volume with `supuesto` | `estado.V.supuesto` · estado (assumed) |
| stream S | `transferencia.S.composicion`, `transferencia.S.entalpia`, `transferencia.S.caudal` · transferencia |
| exchange by conductance Q | `transferencia.calor.Q` · transferencia |
| volume V, component i | `materia.V.i` · materia; `energia.V` · energia if the energy balance is active |
| network | `global.materia.i` and `global.energia` · verification |

For the v2 assemblies, this list matches one to one (id, family, owner and order) the equations `/motor/ensamblajes/validar` publishes in all of its examples. It is the check that the common model describes the same thing the backend solves.

## 3. The three starting cases

| Case | There | Back | "Without loss" criterion |
|---|---|---|---|
| Nondimensionalization document (v1 or v2) | `desde_documento_adimensional` | `a_documento_adimensional` | The document comes back identical; `matematico` carries the model and `motores.adimensionalizacion` the forms |
| The engine's v2 assembly request | `desde_ensamblaje_v2` | `a_ensamblaje_v2` | The request comes back identical, and `relaciones()` matches the backend's equations |
| The engine's matter sheet (TS solver) | `modeloDesdeHojaMotor` (TS) | `hojaDesdeModelo` (TS) | Active formulation, components and configuration come back identical. `matematico` contains the equations the engine runs, the same ones nondimensionalization imports, and the Python reader accepts the model |

### Evidence (18 October 2026)

- `python tests/validar_modelo_comun.py`: **102 checks**.
  - The 20 nondimensionalization example documents come back identical.
  - The 6 example v2 requests come back identical, and their relations match the published example and a live `validar_v2`.
  - In the ethanol–water heating, the vapor appears and the liquid disappears with the same set of relations.
  - Ten rejections, among them one for a volume without a thermodynamic closure.
- `node verificar_modelo_comun.mjs` (from `frontend/`): **117 checks**.
  - The engine's 9 matter sheets, one of them incomplete: exact round trip, accepted by the TS and Python readers, `matematico` equal to what nondimensionalization imports, and the state declared as assumed.
  - The 17 real v2 requests of the multiphase, N-component, UNIFAC and demonstration sheets: exact round trip and relations equal to those of the live backend.
- Examples: `docs/ejemplos/modelo-comun/`. The Python ones are regenerated with `--regenerar`; the sheet one is written by the TypeScript verification.

## 4. Rules

- Strict reading: unknown keys, repeated ids and references to nothing are errors with their path (`volumenes[0].termodinamica.paqueteId: referencia inexistente`).
- Units: each `Dato` carries its own. The model does not convert; the units engine does.
- The model is **data**. It contains no functions, code or LaTeX as a source of truth; the generated relations carry a readable description, not a formula that has to be interpreted.
- Version: an incompatible change raises `version`. A new optional field is added without raising it and is documented here.

## 5. Outside v0

- Explicit equations (tree) for the assemblies with thermodynamics.
- General assumption journals for energy and thermodynamics. Material operations now have the optional versioned journal in §8; legacy inputs without it still carry effective flags.
- Constitutive laws and momentum.

All of that belongs to steps 2 to 5 of the architecture. (The consumption of the model by the solvers and the interface, listed here originally, arrived in step 5.1.)

## 6. Proposed equation-to-solver boundary

**Architectural design; the implemented first increment is specified in §7.** This section addresses the connection between derivations, assumptions and numerical systems. It does not publish a general residual/DAE payload or claim a general DAE solver.

### One physical problem, several numerical representations

The authoritative object is a typed equation/dependency graph with stable symbols, equations, terms, domains, conditions, closure calls and provenance. Conservation-law templates supply general term families; there is no fixed matrix layout per equipment or scenario. The active problem is derived from the declared physics, components, topology, assumptions and data.

Continuous spatial operators remain in this representation until a declared Transform discretization produces finite-dimensional equations. For a finite-dimensional transient problem, the general numerical boundary is

$$
F(t,y,\dot y;p)=0,
$$

with differential/algebraic unknown classification, units, initialization requirements and separate domain/inequality/complementarity constraints. This includes explicit ODEs as the special case $F=\dot y-f(t,y;p)$ and algebraic problems as residuals independent of $\dot y$. It does not assert that arbitrary DAEs, PDEs or complementarity problems are executable by the current solvers.

The compiler can expose an explicit right-hand side when a valid reduction permits it. Matrix assembly and factorization belong to a compatible execution plan. A linear model may expose $M\dot y=Ay+b$; nonlinear models generally require residual evaluation and derivatives instead of one constant coefficient matrix.

### Assumptions and zero terms

| Change | Numerical consequence | Required trace/check |
|---|---|---|
| An additive source or flux is identically zero under an assumption | Remove that contribution; the balance and its unknown may remain | Original term ID, assumption and validity |
| A coefficient happens to be zero at the current state | Do not infer that the dependency is absent for other states | Structural dependency versus evaluated value |
| A declared datum is specialized to zero during compilation | Simplification is tied to that datum/version and must be invalidated if it changes | Compilation assumptions and data signature |
| A variable is determined by a valid explicit substitution | It may be eliminated with its defining relation; retain a reconstruction map | Domain, branch, units and effects on all equations/conditions |
| A balance becomes $\dot y_i=0$ | Retain a constant differential state, or explicitly eliminate it using its specified initial value | Its physical inventory and couplings still exist |
| An assumption removes accumulation | The balance becomes algebraic; keep the remaining constraint | Reclassify the problem and check consistent initialization |
| A relation reduces to the identity $0=0$ | It supplies no independent constraint | Check remaining unknowns and constraints before removing the identity |

Do not allocate placeholder equations solely for removed physical terms. Do not delete rows or columns merely because their values are zero at one evaluation. Sparse storage omits known zero entries; matrix dimension follows the retained numerical unknowns and independent equations, not the number of written additive terms. Any reduction preserves the original model and a map to the retained/reconstructed variables.

### Total balances and spatial fields

A total balance already gives an ODE or algebraic equation for aggregate variables; it needs no fictitious spatial grid. One lumped volume can have many states and algebraic unknowns. Its numerical size comes from those retained unknowns and closures. A field creates additional degrees of freedom only through the declared spatial discretization; boundary constraints, eliminated variables and auxiliary states also affect the final count.

For an implicit transient method, the linearized system is typically

$$
J\,\Delta y=-F,\qquad J=F_y+\alpha F_{\dot y},
$$

at the current step/iteration, with the method-dependent derivative approximation understood in $F$. The coefficient $\alpha$ depends on the integration formula and step history. For backward Euler applied to $\dot y=f(t,y)$, $J=I/\Delta t-f_y$. An explicit Runge–Kutta method need not assemble this matrix. These are different numerical representations of the same mathematical problem, not different physical models.

See [SUNDIALS IDA mathematical considerations](https://sundials.readthedocs.io/en/latest/ida/Mathematics_link.html) and [PETSc time integration](https://petsc.org/release/manual/ts/). Consistent initial conditions and supported DAE index remain explicit requirements; equation counting alone does not establish well-posedness.

### Thermodynamic equations: coupled or locally eliminated

Use $x$ for retained dynamic quantities, such as component amounts and internal energy, and $z$ for algebraic state quantities, such as temperature, pressure and phase compositions. A representative semi-explicit formulation is

$$
\dot x=f(t,x,z;p),\qquad 0=g(t,x,z;p).
$$

- **Coupled execution:** retain $x$ and $z$ and solve their residuals together. For this semi-explicit form, the implicit linearization has blocks $[\alpha I-f_x,\,-f_z;\,g_x,\,g_z]$. The cross blocks express physical coupling.
- **Nested closure:** solve the thermodynamic subsystem for $z=z(t,x;p)$ within evaluations of the dynamic equations. The outer problem is smaller, but thermodynamics remains active. Local flash solves may have their own matrices or minimization subproblems.
- **Derivative consistency:** within a smooth regime and where $g_z$ is nonsingular, implicit differentiation gives $z_x=-g_z^{-1}g_x$ and $d f(t,x,z(t,x))/dx=f_x-f_zg_z^{-1}g_x$. An implementation solves the corresponding linear systems; it need not form a matrix inverse. Analytic derivatives, numerical differentiation of the complete closure-coupled residual, or suitable derivative-vector products must account for this coupling.
- **Phase boundaries:** the smooth elimination formula is not a global guarantee across phase changes or singular closures. Declare validity, phase events and the supported active-set/complementarity strategy. Absent phases do not impose every present-phase equality; complementarity and stability conditions require their proper treatment.
- **Independent equations only:** definitions evaluated as functions, derived observables, redundant identities and verification certificates are not automatically additional residual rows. All constitutive/thermodynamic constraints required by the chosen formulation must be represented or accounted for through valid elimination. The package determines the relevant relations, not an arbitrary inclusion of every formula in a catalog.

Both execution strategies must derive from the same model and expose which relations were retained, locally solved or eliminated. Neither is universally the best choice. Nested closures reuse the current packages; coupled/block execution is a future option for suitable problems and solver capabilities.

### Required compilation report and incremental adoption

The proposed compiler report identifies: source model/formulation signatures; retained differential and algebraic unknowns; input data and observables; independent residual rows; term and assumption provenance; eliminated variables and reconstruction maps; domain/phase constraints; initialization requirements; dimensions and numerical scaling; structural dependency/sparsity information; and compatible numerical methods. Stable IDs map displayed derivation steps to residual rows and matrix row/column labels, independently of numerical ordering.

Model displays the physical derivation and formulation. Transform extends that same model with admissible derived formulations and discretizations. The compiler consumes the selected transformation chain's output, or the physical formulation through an identity path when no transformation is selected. Its report identifies the source physical revision, selected derived formulation and transformation-chain signature; unsupported execution must not silently fall back to another formulation. Solve inspects the resulting compiled unknowns, residuals, closure strategy and method-dependent matrices or operators. Results records that execution provenance, reconstructs physical variables and checks the original equations. Auxiliary conservation integrals are identified separately from physical state variables. See the [connected formulation and execution rules](../engine/model-workspaces.md#connected-formulation-and-execution) for dependency invalidation and workspace behavior.

**Current implementation:** the common integrator consumes `rhs(t,y)`. The structural thermodynamic compiler evaluates UV/PH closures inside that right-hand side and uses the default RK45 path; the explicit-equation compiler supports RK45/BDF for its admitted ODEs and rejects algebraic residuals. The existing BDF wrapper does not supply an analytical Jacobian or sparsity pattern; SciPy estimates its Jacobian numerically ([SciPy BDF](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.BDF.html)). Thermodynamic assemblies do not yet have explicit equation trees in common model v0 (§5).

The first implementation increment should make existing ODE/closure compilation inspectable and traceable, preserving current results, before adding a general residual/DAE executor. Tests must cover zero-term simplification without unintended state deletion, valid variable reconstruction, consistent initialization, invalid reductions, total versus discretized models, and coupled-versus-reduced equivalence in their shared validity domain.

## 7. Implemented Transform execution and compilation report

**Scope:** the first connected increment executes a selected, certified, constant multiplicative scaling of explicit first-order ODEs. It uses the common Python integrator (RK45 or BDF), the existing nondimensionalization algebra and the common results format. The frontend adapter currently exposes this for its supported single-domain matter models. Existing physical execution and spatial mesh settings remain compatible.

### Selection contract

The optional field `motores.adimensionalizacion.execution` is an additive extension of common model v0:

```ts
type TransformExecution = {
  version: 1;
  objectives: string[];
  freeScales: Record<string, { value: number; unit: string }>;
};
```

`formas` contains the core's base form and `activaId` selects it. `objectives` records the selected automatic formulation's published `objetivosAplicados` term IDs; normalization preserves coefficient signs. These IDs are validated against the current term inventory, without rerunning the combinatorial search or relying on a page-local formulation number. `freeScales` supplies exactly the remaining free scales, with positive finite values and compatible linear units. Offset temperature units are rejected for scale magnitudes; they require a difference unit. Both common-model readers validate the selection structure; Python validates form revision, dimensions, units, domains and numerical admissibility.

On `POST /modelo/resolver`, the compiler regenerates the selected formulation from the current physical mathematical model and these choices. It requires the inverse equivalence certificate and resolved objectives. It integrates the regenerated transformed equations, maps initial values and componentwise absolute tolerances, and reconstructs physical variables and time. Additional diagnostic states integrate the original physical equations; their reconstructed budgets are checked against physical state changes. Existing physical restrictions and event times pass through the reconstruction. These budget checks are numerical diagnostics, not a proof of experimental validity.

The physical definition remains the source. Selected execution cannot silently fall back to a physical formulation. Unsupported maps, coordinates, closures, missing scales and stale revisions produce a reason. With `execution` absent, the existing physical dispatch remains unchanged.

### Compilation and result provenance

`POST /modelo/compilation` accepts `{modelo}` or `{solicitudV2}` for the existing thermodynamic-network adapter. It compiles without integrating and returns `rage.compilation` version 1. The report contains the executed formulation, method, source model/revision and SHA-256 signature; retained differential variables and physical units; evaluated scales and mapped tolerances; time mapping; equations or structural relations; conditions/domains; reconstruction maps; diagnostic-state count; and closure/matrix limitations. Scaled reports additionally include the exact selection, evaluated parameters and dimensionless groups. Invalid requests receive 422 with a reason.

Explicit physical reports use the existing equation compiler, generating balances when necessary. Generated auxiliary integrals are distinguished from physical variables. Thermodynamic reports describe the current nested UV/PH strategy and retained inventories; they explicitly disclose the missing explicit equation trees. Neither report invents a constant matrix, Jacobian entries, a sparsity pattern or eliminated variables that the compiler has not produced.

Scaled results include the report at `procedencia.compilation`. Physical series keep `campo.<originalId>` and physical time; `transformed.<newId>` publishes numerical variables and `budget.<originalId>` publishes reconstructed integrated balances on the physical time axis. The frontend checks the report and returned selection against the request before accepting the result. The result adapter retains this report in the existing saved result for inspection in Results.

### Limits and verification

This increment does not execute affine/nonlinear maps, scaled thermodynamic closures, scaled spatial discretizations, arbitrary transformation chains, algebraic systems or DAEs. The underlying transformation core retains its broader symbolic capabilities. The compilation report is not a general structural-rank, elimination or DAE-index analysis.

`python tests/test_transformed_execution.py` verifies analytical decay with RK45/BDF, normalized and free scales, SI conversions and tolerance maps, coupled transfer, explicit time forcing, domain-event reconstruction, zero-term state retention, strict selection reading and stale revisions. `node frontend/verificar_transform_execution.mjs` (run from the repository root with its file-relative loader) verifies the real Python path and physical Results adapter across six existing models, with 60 checks. Workspace behavior and browser evidence are maintained in the [workspace specification](../engine/model-workspaces.md).

## 8. Material deduction journal (implemented subset)

**Scope and responsibility.** Model owns material assumptions; the common reader, balance generator, selected Transform execution and Solve consume the same effective formulation. Python replays the optional journal and rejects disagreement before compilation. Topology, components and thermodynamic state assumptions remain in their existing common-model fields. This is a compatible optional namespace, not a translation of published keys.

```ts
motores.materialDerivation?: {
  format: 'rage.material-derivation'; version: 1;
  volumes: Record<string, {
    origin: 'recorded' | 'reviewed_rebuild';
    operations: { id: string; title: string; changes: Partial<MaterialState> }[];
  }>;
};
```

`MaterialState` retains the published `FormulacionMateria` keys, excluding `componentes`, `fronteras` and `reglasEstado`. Those belong to the component/topology and thermodynamic definitions. The root is always unrestricted local conservation; it is generated by the core, never supplied as an already simplified equation. Operations retain the legacy shallow-merge semantics, including replacement of the `campo` object. Missing optional false flags are normalized only for comparison. Unknown fields, invalid values, repeated operation IDs, unknown owners and mismatched final assumptions are rejected. Limits: 160 journaled volumes, 400 operations per volume; existing engine size limits still apply.

**Authoring and development.** `POST /modelo/material-derivation` takes `{journal, volumeId, action?: {kind}}` and returns `{journal, development}`. It performs no time integration or flash. Supported action kinds: `start`, `integrate`, `total`, `no_reaction`, `fixed_boundary`, `impermeable_remainder`, `no_diffusion`, `no_convection`, `no_accumulation`, `undo`. Python returns the effective formulation and a versioned `rage.material-development` object containing ordered LaTeX steps: local conservation, Gauss, Reynolds, inventory/source definitions, declared assumptions and the equation after substitution. Coordinates remain in invariant vector notation. Volumetric-substitution development stays in the existing ordinary material view. Invalid requests return HTTP 422 with `detail: {code: 'invalid_material_derivation', message}`.

**Compatibility and consumers.** Ordinary material histories serialize their actual active operations; roots, ancestry and stored snapshots are checked before adaptation. No history is inferred from the final flags. Revision-2 network requests carry the same namespace inside `derivacion.materialDerivation`; the Python adapter maps it to `motores` and preserves round trips. Both the common reader and the legacy network validation/solve path reject a forged or stale journal. Inputs without journals remain readable and executable within their supported scope, with no invented provenance. A partial network journal establishes evidence only for its listed volumes and for matter.

**Compilation and results.** Optional `rage.compilation` v1 field `materialDerivation` contains `{volumeId, origin, operationIds, signature, relationIds}` entries. `signature` is SHA-256 of the volume journal. `relationIds` refer to common conservation relations (`materia.<volume>.<component>`); they are not a claim that all execution paths expose explicit AST rows. The generator still produces the actual equation trees from the verified assumptions; thermodynamic execution retains its coupled UV/PH closure. Supported physical balance runs and scaled runs preserve the report in common results and the frontend result store. Native revision-2 results retain the journal in their stored input request.

**Limits.** A valid journal is provenance evidence, not dimensional certification of arbitrary free expressions, an independent-rank proof or new solver support. Zero accumulation is an algebraic constraint; spatial forms, an unclosed remainder without a flux law and incompatible boundary/stream assumptions cannot be silently executed by the thermodynamic transient compiler. Energy and thermodynamic journals are defined in §9. General residual/DAE execution, additional spatial discretization and general transformation composition remain pending.

**Verification.** `npm run test:material-derivation` (from `frontend/`) runs the journal audit, cross-language checks and Python unit suite. `tests/test_material_derivation.py` covers replay, theorem development, mutation protection, undo, strict reading, compatible round trips, forged/stale records, compilation links and unsupported execution. `frontend/verificar_material_journals.mjs` checks all 41 models through both readers and independently checks closed conversion, open filling and connected volumes against analytical solutions and conservation residuals. See the maintained workspace specification for browser checks and remaining provenance gaps.


## 9. First-law and thermodynamic operation journals

**Primary workspace:** Model. Inputs are the fundamental first law/state relations, actual recorded operations, topology, mechanical boundaries and explicit constitutive choices. Outputs are effective assumptions and server-developed LaTeX. Transform retains these namespaces; Solve verifies them against its actual input; Results retains compilation provenance. An operation or package/policy change invalidates dependent artifacts. Archives and display names do not change execution identity.

Both are optional additive namespaces of common model v0, with independently versioned documents:

```ts
motores.energyDerivation?: {
  format: 'rage.energy-derivation'; version: 1;
  volumes: Record<string, OperationEntry<EnergyState>>;
};
motores.thermodynamicDerivation?: {
  format: 'rage.thermodynamic-derivation'; version: 1;
  volumes: Record<string, OperationEntry<ThermodynamicState>>;
};
type OperationEntry<S> = {
  origin: 'recorded' | 'reviewed_rebuild';
  operations: {id: string; title: string; changes: Partial<S>}[];
};
```

The server generates each unrestricted root. Limits are 160 journaled volumes and 400 operations per volume; operations shallow-merge validated fields. Unknown fields, duplicate IDs, incorrect types, unknown owners and mismatches with compiled assumptions are rejected. Version booleans are rejected. A journal verifies evidence for the listed volumes; it is not a physical certificate or additional solver capability.

**Energy state.** `EnergyState` uses the published `FormulacionEnergia` keys except `monofasico`, `sinCambioFase`, `densidadConstante` and `modelo`. Those four belong to Thermodynamics. Pressure uniformity and prescribed mechanical pressure remain first-law context. Collecting flow work into enthalpy requires pressure-stress separation first. A prescribed pressure history requires spatial uniformity; legacy total-work shorthand is rejected in a replayable journal until its work terms are declared explicitly.

`POST /modelo/energy-derivation` accepts `{journal, volumeId, context, action?:{kind}}`. `context` is `{fixed:boolean, remainderClosed:boolean, streamIds:string[], pressurePrescribed:boolean}` from actual topology. Actions are `start`, `integrate`, `reynolds`, `total`, `pressure_stress`, `enthalpy`, `no_kinetic`, `no_viscous_work`, `no_body_work`, `no_volume_source`, `uniform_state`, `uniform_pressure`, `prescribed_pressure`, `adiabatic`, `no_local_heat_flux`, `no_accumulation`, `undo`. The response is `{journal, development}`, with `rage.energy-development` v1, `volumeId`, `origin`, effective `formulation`, ordered `{id,title,latex}` steps and explanatory `notes`.

Python develops Gauss/Reynolds, relative boundary transport, pressure/viscous stress, enthalpy, heat/work/source definitions, substitutions and each resulting equation. The total first law retains boundary work on moving volumes. Under uniform prescribed pressure, `H=U+PV` gives `dH/dt=dU/dt+P dV/dt+V dP/dt`; the actual common RHS retains `V dP/dt`. Adiabatic boundaries and zero local heat flux remain distinct assumptions. Total terms have power units; local terms have power-per-volume units.

**Thermodynamic state.** `ThermodynamicState` contains the four state assumptions above and `closure:null | {packageId, model:{id,version}, policy}`. The policy uses the existing published keys. An equilibrium-package selection must agree with its phase flags and cannot simultaneously impose a manual caloric law or constant mixture density. A null closure is the unrestricted starting point; it cannot represent an executed equilibrium closure. Manual declared-state histories can retain null and must match the corresponding existing declared-state model.

`POST /modelo/thermodynamic-derivation` accepts `{journal, volumeId, fixed:boolean, action?:{kind}, configured?:{packageId,model,policy}}`. Actions are `start`, `select_closure`, `one_phase`, `no_phase_change`, `constant_density`, `linear_caloric`, `undo`; network UI exposes only the applicable equilibrium actions. `select_closure` explicitly adopts the configured package/version and policy, including their phase assumptions. Policy operations update the bound policy and matching flags together. The response uses `rage.thermodynamic-development` v1 with the same development envelope. Invalid energy/state requests return HTTP 422 with `detail:{code,message}`.

The development starts from the simple-compressible fundamental relation and Legendre identities, then shows declared assumptions, phase partition, equilibrium/stability, package-family relations and the final UV/PH or manual caloric closure. A package is a constitutive choice: its empirical data are not derived from conservation. Package data, units, validity domains and fingerprints keep their existing ownership and validation; the journal binds identity/version and policy without duplicating parameter truth.

**Adapters and editing.** Ordinary energy/state histories now record operation inputs alongside snapshots. A legacy snapshot without inputs remains a visible verification limit; no missing operation is inferred. Revision-2 requests carry the namespaces under `derivacion`, with lossless common-adapter round trips. New templates apply explicit first-law recipes and constitutive selections, checked against the reference physical inputs. Saved documents are not migrated automatically. Network editors support explicit rebuild, apply, undo and restoration of archived formulations; rebuilding one family preserves the others. An unbound or stale closure blocks journaled compilation until explicitly resolved. New volumes start from fundamental energy and an unbound thermodynamic root; deletion removes ownership. Deliberate model edits record their consequences only when the preceding journal was consistent and unchanged, never repairing old missing evidence.

**Compilation and Results.** Optional report fields `energyDerivation` and `thermodynamicDerivation` have the same provenance entry format as §8. Energy relation IDs name the actual `energia.<volume>` relation; thermodynamic IDs are selected from the actual state/equilibrium relations. Explicit physical, equilibrium and transformed common results retain the compilation report when journals are present. Native revision-2 results retain their journaled input. A common-reader mismatch or native validation diagnostic (`MOTOR_ENS_ENERGY_JOURNAL`, `MOTOR_ENS_THERMODYNAMIC_JOURNAL`) blocks execution before expensive state evaluation.

**Read-only handoffs.** `POST /modelo/formulation-summary` accepts `{modelo}` or `{solicitudV2}` and returns `{format:'rage.formulation-summary',version:1,modelId,families}`. The four family IDs are `matter`, `energy`, `momentum`, `thermodynamics`; each owns `volumes:[{volumeId,status,steps:[{id,title,latex}],note}]`. Recorded journals are replayed against the common definition; absent evidence is `unrecorded`, unsupported momentum is explicit, and an inactive family has an empty volume list. No state is initialized or integrated. This response is a presentation artifact, never a source of numerical equations.

`rage.compilation` v1 additionally permits `strategy:{methods:[{id,available,reason}],steps:[{id,title,description,latex}],scope}` and `systemEquations:[{id,family,latex}]`. Strategy describes the admitted compiler branch and selected method; `available` is scoped to that branch, not a universal engine claim. Symbolic balance displays bind to the admitted assembly's volume/stream/heat IDs. They do not replace `equations` ASTs or expose an assembled nonlinear Jacobian. Old reports without these additive fields remain readable. The strict frontend reader rejects malformed additions. Detailed workspace behavior and the requested coupled example are maintained in [the workspace specification](../engine/model-workspaces.md#visible-mathematical-handoffs-20-october-2026).

The common equilibrium compiler rejects unsupported first-law terms, zero accumulation, contradictory manual/package closures, mismatched phase policies, unsupported rigid pressure constraints and inconsistent heat links. It never interprets missing heat as an imposed zero. These guards preserve supported transient scope; they do not implement general residual/DAE or spatial energy execution. The live [Engine checklist](../engine/engine-checklist.md) separates those extensions.

**Verification:** `npm run test:physical-derivation` runs cross-language template/lifecycle checks and the energy/state Python suites. `tests/test_energy_derivation.py` includes independent heating/open-balance algebra and the actual compiled prescribed-pressure RHS; `tests/test_thermodynamic_derivation.py` includes strict binding, policy/closure conflicts and independent caloric/chemical-potential identities. The existing energy, common-model, balance and UNIFAC reference suites remain the physical regression evidence. Browser evidence and counts are maintained in the workspace specification.

## 10. Dynamic inventory definition (Model first)

User decision, 20 October 2026. Conservation remains dynamic even when its evaluated derivative is zero. For each inventory `I_b`, retain `dI_b/dt = Phi_b(t,y,z,u)`. A permanent constraint adds `I_b(t)=I_b(t0)` and compatibility `Phi_b=0`. Initially stationary conditions are initialization specifications in Solve; they never declare permanent Model constraints. A perturbation changes the evaluated rates without deleting or restoring physical states.

The additive optional namespace `motores.dynamicDefinition` has its own contract:

```json
{"format":"rage.dynamic-definition","version":1,"operations":[]}
```

An operation contains `id`, `volumeId`, `inventory`, `mode`, `reason` and, for a fixed condition, an optional `dependent` binding. Inventory kinds are `total_mass`, `component_amount` (with integer `componentId`) and `energy` (with explicit `coordinate:'U'|'H'|'E'`). Energy coordinates are part of the inventory identity: changing a boundary or kinetic-energy assumption never silently reinterprets a saved U constraint as an H or E constraint. Modes are `fixed` and `dynamic` (explicitly remove the permanent constraint). Dependent kinds are `stream_total`, `component_flow` (with `componentId`) and `heat_flow`, each referencing an existing incident stream/exchange ID. Only prescribed-power heat links can become dependent heat unknowns; a conductance law cannot be silently removed. Fixed conditions without a binding are incomplete and diagnosed. A selected binding changes that data's role to a dependent unknown; its stored numerical declaration is preserved, not simultaneously imposed as an independent specification.

Python strictly validates fields, versions, operation IDs, current owners/components, incident-flow references, basis and dimensional compatibility through the shared units service. The last operation per inventory defines its current condition. Superseded operations remain structurally checked history; their retired bindings need not still exist in current topology. New operations always require existing owners/components. Undo is explicit and can repair the latest binding after topology changes. Common v0 and native revision-2 envelopes remain unchanged; native metadata carries this namespace in `derivacion.dynamicDefinition`, with lossless adapters in both directions. Absent namespaces retain existing behavior. Published Spanish keys are not renamed.

`POST /modelo/dynamic-definition` accepts one `{modelo}` or `{solicitudV2}` envelope and an optional `action:{kind:'append',operation}` or `action:{kind:'undo'}`. It returns `{definition,formulation}` without numerical initialization, equilibrium search or integration. `formulation` is `rage.dynamic-formulation` v1: model ID, inventories, dynamic-law/constraint/compatibility rows, variable roles and units, closure-to-inventory references, domains, diagnostics and scope. Roles distinguish inventory states, derived quantities, external inputs, dependent unknowns, closure unknowns and specified data. Total mass is derived from component inventories, using constant molar masses when the basis is molar; it is not an extra independent state. Fractions are derived on one declared basis from nonnegative inventories with strictly positive total; no clipping or undefined empty-mixture composition is accepted by this formulation.

Physical law rows reuse the existing matter/first-law Python generators with temporal accumulation retained. `Phi` denotes the full net physical rate, not a truncated inlet/outlet balance; retained sources and boundary remainder still count. Displaying the preserved dynamic baseline never rewrites a legacy journal. The thermodynamic package and phase policy remain the authority for local closure and domains. Temperature or volume is not fixed by declaring an energy or mass inventory fixed. Enthalpy coordinates explicitly retain `H=U+PV` and its pressure-work derivative.

Diagnostics identify missing or reused dependent flows, inactive targeted balances, missing total-inventory deductions, redundant total/component constraints and legacy zero-accumulation flags. They are structural checks, not a numerical rank, feasibility or initialization certificate. A component flow can have zero coefficient for an absent species, and independent matching does not prove a nonsingular coupled system. These checks belong to later Transform/Solve compilation.

Legacy `estacionario`, `sinAcumulacion` and `sinAcumulacionTotal` retain their original protocol meaning and recorded history. The Model UI offers removal of existing legacy flags and creation of new inventory-specific conditions; it does not automatically reinterpret old stationarity as fixed total mass or initial stationarity. Review the original journal explicitly before adding a new permanent inventory condition.

**Execution boundary:** current common explicit/scaled/nested compilers and the native network endpoint reject active new fixed-inventory constraints. Browser fallback compilation/integration does too. None can silently ignore the constraint, overwrite an inventory derivative with zero, adjust a prescribed input or run a steady algebraic replacement. Removing the constraint explicitly restores the supported dynamic path. This is a completed Model authoring foundation, not general DAE/time-integration support or a real-time session implementation.

**Verification:** `npm run test:dynamic-definition` covers thirteen Python tests, cross-language strict readers, actual Python publications rendered with KaTeX, ownership/basis/units, immutable energy-coordinate meaning, lifecycle/signatures and existing workspace handoffs. An independent binary-tank reference uses unequal molar masses: equal mass inflow/outflow permits changing component inventories and independently varying energy. Browser evidence and the priority transition to momentum are maintained in the workspace specification and roadmap.

## 11. Momentum deduction: Cauchy to reduced machines

User decision, 20 October 2026: Navier–Stokes and machine relations must be reached through explicit assumptions and algebraic steps, just like matter and energy. The primary workspace is **Model**; spatial discretization and coupled momentum integration remain future Transform/Solve work.

### Versioned source and ownership

The additive `motores.momentumDerivation` namespace is `{format:'rage.momentum-derivation',version:1,volumes:{[volumeId]:{origin,operations}}}`. Each operation has `id`, `title` and `changes`; all new identifiers are English. The shared operation-journal engine validates unique operations, fields, versions and replay. One assumption is recorded at a time; the two port IDs can be bound together. No stored terminal equation replaces its deduction. Native revision-2 metadata carries `derivacion.momentumDerivation`; both adapters preserve it losslessly. Ordinary saved models carry the same optional namespace. Existing formats and Spanish protocol keys are unchanged.

`POST /modelo/momentum-derivation` accepts one existing `{modelo}` or `{solicitudV2}` envelope, `volumeId` and optional `action:{kind}`. `bind_ports` additionally carries `inletStreamId` and `outletStreamId`. It returns `{journal,preview,development}`. An absent journal produces a clearly identified fundamental preview without persisting or reconstructing history. Start and Undo are explicit operations. Existing unrecorded momentum flags are archived by the storage adapter when the user starts a new fundamental-law journal; they are not interpreted as a fabricated past deduction.

`rage.momentum-development` v1 publishes the effective formulation, chronological `steps`, `finalSteps`, `couplingSteps`, variables/units/roles, prerequisites still requiring closure, currently available deduction operations, port bindings and scope notes. Main/final rows belong to momentum; coupling rows are classified as matter, energy or thermodynamics and displayed only in that family's existing panel. Transform's common formulation summary carries the same deduced equations and provenance. Scientific algebra is Python; frontend readers validate structure and references, never derive equations.

**Direct assumptions (20 October 2026).** The same journal additionally accepts `action:{kind:'set_assumption',name,value:boolean}` for one declared physical flag. Enabling and disabling both append operations; prerequisites are validated without a cascade that would silently change other assumptions. Cauchy conservation can be integrated before a Newtonian law is selected, and continuity does not depend on that constitutive choice. Angular stationarity does not imply equal passage mass flow or zero other torque; Euler transfer is derived only when those independent conditions jointly hold. Blade guidance supplies a velocity triangle independently of the conditions needed to turn it into a torque characteristic. Final/coupling rows are rebuilt from the effective state; historical equations remain only in the chronological development when their assumptions are removed.

The additive optional `controls:[{key,group,label,value,canChange,reason}]` and `forms:[{id,label,action,selected,canSelect,reason}]` describe server-validated direct switches and representation buttons. `available` remains readable for earlier clients; it is no longer the UI's recipe selector. New state flags default to false when replaying existing journals; readers accept old development envelopes without the additions. No published identifier is renamed or history reconstructed.

Cartesian reductions use `expandCartesian`, `invariantX/Y/Z` (all continuum fields), `velocityInvariantX/Y/Z` (velocity only), `zeroVelocityX/Y/Z`, `negligibleConvection`, `negligibleViscousStress`, `negligibleBodyForce` and `zeroLocalAccumulation`. They substitute declared field dependencies into the conservative component equations and Newtonian tensor in Python/SymPy. All three momentum equations remain present: a zero transverse velocity can require hydrostatic pressure compatibility. Velocity invariance permits a pressure gradient along the flow; global field invariance removes it. Density assumptions and property validity retain their Thermodynamics ownership; the momentum reference-density conversion does not override the medium. The product-rule/continuity reduction is used when applicable; neglecting convective momentum transport is a separate explicit approximation. `zeroTotalAccumulation` constrains the integrated fluid-momentum inventory. Local and integrated stationarity retain their differential law and add the zero-rate condition and compatibility; they do not freeze other inventories or the rotor. Initially stationary data remain Solve specifications.

These field reductions currently use Cartesian coordinates in local form. Integration with their boundary consequences and curvilinear metric terms are not implemented and cannot be selected silently; remove the local constraints before entering the existing integral branch. This is symbolic Model authoring, not spatial discretization or a solver extension.

### Fundamental chain and branches

1. **Cauchy conservation:** inertial-frame linear momentum with general stress and body force. No Newtonian, constant-density, zero-inertia or equipment assumption is made at the starting point.
2. **Stress decomposition:** `sigma=-p I+tau`, then an explicitly isotropic Newtonian law with shear viscosity `mu` and second coefficient `lambda`. The bulk dissipation condition is `lambda+2 mu/3 >= 0`; Stokes' hypothesis is not imposed. Conservative compressible Navier–Stokes follows by substitution. Total mass continuity, spatially uniform viscosity and divergence-free motion are separate operations; variable coefficients are not pulled outside derivatives implicitly.
3. **Control volume:** Gauss and Reynolds steps retain temporal accumulation and relative boundary velocity. Fixed control envelope, impermeable walls, uniform local section components and port definitions are recorded before the two-port reduction. Surface normal integrals remain explicit for curved ports. Angular-flux representative values are mass-flux averages; axisymmetric annular ports do not use one constant global radial vector.
4. **Straight hydraulic branch:** constant area, reference-density approximation and conservative gravity yield dynamic inertance. Equal port mass flow follows from an explicitly retained mass balance plus the fixed full-path storage constraint. Wall, port-viscous and nongravitational body forces are collected into declared drive/loss terms; none is silently dropped. Signed Darcy–Weisbach/local resistance is an optional constitutive law with nonnegative coefficients, not an automatically known friction factor.
5. **Rotating branch:** moments of Cauchy conservation yield fluid angular accumulation and torque fluxes. An unresolved-rotor actuator is explicit; constant positive rotor inertia retains `J domega/dt`. Shared fluid torque supplies equal/opposite shaft power in Energy. Passage mass storage, other axial torques and angular accumulation have separate declarations. The original differential balances remain beside their zero-accumulation constraints.
6. **Ideal radial-blade reduction:** zero inlet prewhirl, axisymmetric full-annulus outlet without blockage and ideal blade guidance give the velocity triangle. Substitution gives ideal torque and Euler specific transfer/head. Adiabatic passage, explicit zero passage energy accumulation, reference density and a lossless/internal-energy-change approximation are additionally required before deriving static pressure rise with kinetic/elevation corrections. Hydraulic head uses `mathcal H_E`, distinct from total enthalpy `H`. Straight-pipe and radial-annulus reductions cannot be mixed without undoing their incompatible assumptions.

This derives an **ideal centrifugal characteristic**; it does not predict real slip, efficiency or losses from conservation. Real data/closures, transport-property providers, cavitation, reverse-flow machine maps, compressibility and multiphase operating domains remain explicit requirements. A quasi-steady passage constitutive limit does not make the retained shaft or network balances globally stationary. No small numerical inertia or compressibility is invented to avoid algebraic constraints.

### Connected pressure, matter and energy

Port bindings reference existing oriented material streams in the same common model. Pressure aliases identify the same **absolute static** local pressure used by thermodynamics; dynamic pressure is not substituted into the EOS. The phase-resolved donor state supplies enthalpy, density and composition. Bulk-to-port hydrostatics and loss relations remain required instead of silently equating all pressures in a network. A fully liquid-filled rigid incompressible volume still cannot determine absolute pressure from its thermodynamic closure alone.

The service diagnoses unbound ports, missing transport/drive/loss closures, density-domain requirements and incompatible material/heat/kinetic-energy assumptions. A declared heater is not disabled by selecting an adiabatic passage. A prescribed flow datum is not silently changed into a solved unknown. Active momentum remains rejected outside the explicitly admitted reduced hydraulic path in §12; native network and legacy browser execution retain their momentum block. Derivation capability and executable simulation remain distinct.

`reduced_relations()` is the canonical symbolic source of published scalar inertance, loss, rotor, ideal torque, transfer and static-pressure equations. The renderer, reduced hydraulic compiler and independent numerical/dimensional checks use those same expressions. `npm run test:momentum-derivation` runs twenty-three Python tests plus strict frontend/publication checks, covering tensor differentiation, impulse, velocity triangles, power, signed dissipation, dimensional homogeneity, prerequisite/branch rejection, replay, topology, roundtrip, family placement and execution guards. The shared frontend verifier currently renders 289 formulas across existing branches and the momentum paths.

Physical references: [Newtonian compressible governing equations, COMSOL](https://doc.comsol.com/6.4/doc/com.comsol.help.aco/aco_ug_aero.08.128.html), [Euler turbomachine equation, MIT](https://web.mit.edu/16.unified/www/FALL/thermodynamics/notes/node91.html), [centrifugal-pump control-volume exercise, MIT](https://web.mit.edu/2.25/www/5_27/5_27.html). These establish physical foundations, not validation of any real machine or its data.

## 12. Reduced hydraulic execution

20 October 2026. This is a scoped common-compiler specialization, not a general DAE, pump or spatial solver. The optional namespace `motores.hydraulicNetwork` has `format:'rage.hydraulic-network'`, `version:1`, `medium`, `gravityId`, `storages` and `paths`. The strict Python definition is `core/balances/hydraulic_definition.py`; the compatible frontend reader is `frontend/app/models/hydraulicDefinition.ts`.

- `medium` binds `densityId`, `viscosityId`, `temperatureId`, `minimumPressureId` and an explicit assumption `reason` to common data. This increment admits one constant-density, single-phase Newtonian reference liquid, externally maintained isothermal, with no energy integration or equilibrium package substitution.
- A storage binds `volumeId`, `areaId`, `surfacePressureId`, `floorElevationId`. Its dynamic material inventory and recorded local hydrostatic momentum reduction determine height and absolute static port pressure. The prismatic, hydrostatic storage limit is a declared approximation; changing material inventory is not global stationarity.
- A path binds `volumeId`, existing oriented `inletStreamId`/`outletStreamId`, and `lengthId`, `areaId`, `diameterId`, `driveId`, `inletElevationId`, `outletElevationId`. Geometry and fixed full-path mass must agree with density. All owners and streams must have exactly one supported role; ignored topology and independent stream-flow specifications are rejected.
- `flow` is `{kind:'prescribed',datumId}` or `{kind:'dynamic',initialId}`. Each `inletPressure`/`outletPressure` is `{kind:'datum',datumId}`, `{kind:'storage',volumeId}` or `{kind:'recover'}`. Prescribed differentiable flow requires exactly one recovered pressure; dynamic flow requires two independent pressure closures. A discontinuous imposed flow would require impulse pressure and is rejected.

Every referenced quantity uses the shared units service; compatible inputs convert to SI. Recorded material, momentum and thermodynamic operations must replay against the same physical definition. Independent `circularSection`, `developedProfile`, `quasiSteadyWall`, `regularAxis` and `noSlipWall` operations now derive the profile and wall relation. The former `laminarCircular` shortcut remains readable as legacy history but no longer admits execution. The resulting signed wall relation and dynamic force balance share their symbolic source:

$$
\frac{L}{A}\frac{d\dot m}{dt}=p_1-p_2+\Delta p_{\rm drive}-\Delta p_{\rm wall}-\rho g(z_2-z_1),\qquad
\Delta p_{\rm wall}=\frac{8\pi\mu L}{\rho A^2}\dot m.
$$

The wall law is a **quasi-steady laminar closure with retained bulk inertia**, not the exact transient radial Navier–Stokes solution. Entrance and profile-adjustment/frequency assumptions remain validity obligations. Reynolds number above 2100, absolute pressure below its declared bound, nonfinite values or depleted inventories stop supported execution; no turbulence, cavitation or clipping is invented.

`core/compilador/hydraulics.py` assembles these shared laws and stream incidence. It derives numerical scalar functions from `momentum_derivation.reduced_relations()` and uses the existing RK45/BDF integrators. Dynamic paths retain flow states; storage retains mass states. A prescribed-flow path reconstructs pressure using the known time derivative, retaining the dynamic law without inventing a hydraulic ODE state. Independently integrated transferred-mass and pressure-impulse diagnostics are identified separately. No small numerical inertia/compressibility is added.

`POST /modelo/hydraulics` accepts `{modelo}` and returns the read-only `rage.hydraulic-inspection` v1 envelope with `modelId`, `dataFields` and `report`. Existing `/modelo/compilation`, `/modelo/resolver` and compilation reports execute/publish the admitted branch. Reports include actual states, units/tolerances, replayed journals, eliminated-pressure treatment, available methods and step/Jacobian strategy. Native assembly execution explicitly rejects this namespace; it cannot fall through into an unrelated equilibrium solver. Transform currently passes the physical formulation unchanged; hydraulic scaling and spatial transformations remain unsupported.

Common results publish actual pressure, flow, inventories, heights, Reynolds number and dissipation, with mass, force-impulse and signed-dissipation diagnostics. Publication includes requested uniform samples and bounded accepted-step samples so fast initial inertia remains visible. These numerical checks **do not certify energy, phase equilibrium or real-fluid data**. The existing Results reader/dashboard presents the series; no hydraulic chart engine or example-specific Model frontend exists.

The two requested input-only documents are [prescribed-flow pressure](../ejemplos/momentum-pressure-v1.model.json) and [coupled inventories/flow](../ejemplos/matter-momentum-pressure-v1.model.json). `npm run test:hydraulics` checks recorded deductions, readers, rendering and independent analytical pressure/matrix-exponential trajectory references. Broader energy/rotor coupling, real property providers, compressibility, general constrained networks and spatial dynamics remain pending.

Physical foundation: [MIT hydraulic inertance notes](https://ocw.mit.edu/courses/2-141-modeling-and-simulation-of-dynamic-systems-fall-2006/815006fb290589611069f8240ea823dd_hydraulic_ram.pdf) and [COMSOL Poiseuille-flow glossary](https://doc.comsol.com/6.4/doc/com.comsol.help.cfd/cfd_ug_glossary.15.2.html). The selected reduced wall approximation and its applicability must be distinguished from the fundamental conservation law.


### Equation-operation correction (20 October 2026)

The initial hydraulic increment had two authoring gaps: hydrostatic pressure/height rows were appended from hydraulic configuration, and a laminar profile was shown already solved. These have been removed. An operation journal alone is not proof that an equation was derived: the equation graph must record and execute the mathematical operation.

`core/modelo/equation_manipulation.py` supplies reusable server-side equation operations: substitution, symbolic isolation, integration and differentiation. Graph nodes retain their input equations, rule and assumptions/nonzero conditions. Ambiguous algebraic branches are rejected; arbitrary persisted Python/SymPy strings are never evaluated. Physical producers declare fundamental/constitutive laws and geometry, then use these operations. This is a scoped manipulation kernel, not unrestricted automatic discovery of mathematical models.

`core/balances/momentum_reductions.py` derives path momentum from its integrated inventory and port balance, integrates the auxiliary radial wall ODE with its constants, applies axis regularity and wall boundary conditions, integrates section flux and recovers pressure loss. Missing wall conditions leave integration constants; the compiler cannot use a completed wall law. The wall approximation is confined to the auxiliary constitutive problem, not global zero fluid inertia.

For storage, `uniformGravity`, `referenceDensity`, `verticalGravity`, the existing local force/accumulation reductions, `pressureReference` and `prismaticStorage` are separate recorded operations. The pressure primitive is integrated, its constant is determined at the declared surface, and the material inventory integral is evaluated and isolated for height. Geometry/data bindings do not create these equations. Removing the prismatic operation removes the inventory-to-pressure coupling and blocks that numerical specialization.

Momentum rows add optional `derivation:{rule,inputIds,beforeLatex,assumptions}`. The strict frontend reader accepts legacy rows and validates these additions. The existing Model rows expose the equation inputs and rule in a disclosure; the layout and right-hand assumptions panel remain canonical. Historical operations remain visible, while effective final equations are rebuilt from the remaining assumptions. Undo removes downstream results; unsupported dependencies require an explicit return to an earlier valid state. The compiler evaluates the expressions produced by these same operations, including pressure/height, rather than injecting a separate stored hydrostatic formula.

Acceptance commands remain `npm run test:momentum-derivation` and `npm run test:hydraulics`. The former now includes six equation-operation tests (generic algebra, branch rejection, independent radial ODE/flux reference, a changed wall boundary, pressure/inventory prerequisites and trace inputs). The latter checks all actual deduction rows and their input equations with the strict reader and KaTeX, and rejects topology that tries to supply an unrecorded geometry reduction.

## 13. Selectable equation operations in Model

**Mathematical-kernel boundary:** the shared operation implementation belongs to `core/mathematics`, below physical-family producers. Its inputs are a typed equation graph, explicit units, group/owner metadata and an ordered operation definition. Group names are uninterpreted labels; physical adapters may enforce their own presentation ownership. The kernel does not select equipment, physical laws, packages or numerical methods. Existing `core.modelo` imports and version-1 journals remain compatible adapters.

An operation may additionally carry `sourceSignatures: Record<equationId, sha256>`. When present, it must cover exactly the selected source equations, substitution relation and selected domain-condition IDs. Fingerprints describe typed expressions, mathematical classification, conditions, branch evidence when present and quantity units; titles and display aliases are excluded. Append creates these fingerprints from the current graph. Replay rejects changed input content even when its equation ID survives. Legacy operations without fingerprints remain unsigned; readers do not invent a historical signature. These additive version-1 extensions preserve existing persisted equation identities and histories.

Kernel replay returns an independent graph and chronological receipts containing actual input/output expressions, signatures and generated conditions. Failed replay never mutates its source graph or saved history. Conditions and dependent consequences remain distinct from original laws. Numerical admission remains the compiler's responsibility; a symbolic receipt does not grant numerical support.

Without selected domains, isolation/substitution retain their existing single-polynomial-solution admission. Leading-coefficient and denominator nonzero conditions survive cancellation, including `a*x = a*b` → `x = b` conditional on `a != 0`. Nonpolynomial inversions remain unsupported; one expression returned by a symbolic solver is insufficient evidence.

`declare_domain {sources:[equationId],symbol,domain,reason}` records a typed membership condition for a scalar quantity occurring in that equation. Supported domains are `real`, `positive`, `nonnegative`, `negative`, `nonpositive` and `nonzero`, all subsets of the finite real numbers. Signs require declared absolute units; affine quantities need a reference first. The condition is a `Contains(quantity,set)` premise with `kind:'constraint'` and `rule:'domain_assumption'`, never an equality invented from the source. Contradictory same-quantity domains or contradictions with quantity typing are rejected. The source law remains intact. Domain conditions currently block numerical execution until their lowering is admitted.

`isolate` and `substitute` optionally accept `domains: equationId[]` (one to twenty-four distinct recorded domain conditions). The target quantity needs a selected domain; parameter domains provide explicit assumptions for membership reasoning. The kernel enumerates the complete roots of a real polynomial of degree one or two, proves membership for every candidate, verifies the selected expression against the original residual and admits exactly one distinct branch. For `x^2 = a`, recorded `a > 0` and `x > 0` select `sqrt(a)`; `x < 0` selects the negative branch. Merely declaring `x` real leaves two admissible branches and is rejected. Unresolved parameter regimes, including some coalescing roots, are rejected instead of guessed. Leading-coefficient degeneracy stays an explicit excluded regime, not a solved special case. Higher-degree domain-guided inversion, nonpolynomial inversions, unbounded/symbolic-endpoint intervals and general inequality systems remain pending; bounded interval and singleton extensions are specified below.

Successful branch operations add optional `derivation.branches: {latex:string,admitted:boolean}[]`; all candidates are retained and exactly one is admitted. Internal receipts retain the typed branch equations and their status. Selected domains are actual input nodes in `inputIds`, `beforeLatex` and fingerprints. Changing a domain behind its existing ID invalidates the dependent operation; recovery preserves the history and blocks execution. Existing readers accept histories/reports without these optional fields. Graph copying preserves immutable unevaluated expressions, including contradictory equalities, instead of collapsing them to booleans during replay.

The compatible domain extension adds `zero` (the singleton `{0}`) and `interval`. An interval declaration requires `lower:string`, `upper:string`, `lowerOpen:boolean` and `upperOpen:boolean`. Endpoints accept finite exact decimal/scientific literals or rational fractions, never expressions or executable text. The optional additive `endpointUnit:string` explicitly declares their unit. Python checks dimensional compatibility and converts the bounds to canonical SI through the shared units service using rational catalog factors. New UI records include this field (defaulting to the selected quantity's unit). Old records without it retain their SI-scale-only interpretation; no unit is inferred for an old scaled-unit record. Affine endpoint scales require an absolute reference and remain rejected. Reversed intervals and open singleton intervals are rejected. Closed equal endpoints form a singleton. Endpoint fields on other domain types are invalid.

An explicit endpoint-unit declaration produces `operation.N.declared` (`domain_declaration`) with the original normalized membership expression, followed by `operation.N` (`domain_assumption`) with the converted SI membership expression. Both rows and their input identities appear in the operation receipt and Model/Transform summaries. For example, endpoints in `km/hour` use the exact factor `5/18`; the kernel never rationalizes a rounded floating-point conversion. Symbolic quantities represent physical quantities in SI coordinates during domain proofs. Unit changes that alter meaning invalidate downstream input signatures and formulation/run identities. The units service remains the sole owner of the unit catalog. Exactness is relative to its catalog definitions, not a certificate of empirical constants. Nonrational conversions are diagnosed; affine reference operations remain pending.

Membership proofs now include bounded exact univariate inequality reduction when sign reasoning alone is insufficient. For `x^2 = a`, `a in [1,4]` and `x in [1,2]` prove the positive branch, including both endpoints; opening an endpoint changes admission. These proofs do not use numerical sampling. Unsupported multivariate, transcendental or unresolved mixed regimes remain findings.

Recorded singleton parameter domains are applied by actual simultaneous substitution into the selected inversion equation before polynomial analysis. A generated `operation.N.case` row has `rule:'domain_case'`, the original equation/domain inputs and the specialized expression; it is included in the same operation receipt and Transform summary. Irrelevant singleton premises do not generate a fictitious substitution row. Zero coefficients can therefore reduce a quadratic to a linear equation. Constant residuals are diagnosed separately as an identity, inconsistent case or unresolved residual constraint; they are never divided by the vanished coefficient. Zero and nonzero singleton specialization preserve physical dimensions. Nonzero constants are exact numeric coefficients times typed positive SI basis factors; these factors participate in dimensional algebra and differentiation and are never offered as independent unknowns. Domain proofs project to SI magnitudes internally while the graph retains the typed expressions. Plain numeric literals in relation text remain dimensionless. Domain-guided isolation/substitution still admits exactly one branch; automatic exhaustive parameter partitions, coalescing regimes across intervals, general inequality systems and numerical lowering remain pending.

A blank ordinary model may request `{draft:{format:'rage.fundamental-equations',version:1,modelId}}` from the same authoring endpoint. The report adds `draft:true`, unbound fundamental material/Cauchy laws, an empty operation history and a reason that components must be declared before operations are enabled. This preview is not a numerical common model, invents no component identity or property values and rejects mutation actions. Instantiated requests continue through the strict common-model reader.

The compatible physical-preview protocol uses **request version 2**: `{draft:{format:'rage.fundamental-equations',version:2,modelId,materialJournal,ports,momentumJournal?}}`. `materialJournal` is the actual recorded volume entry (origin and operations), `ports` contains the existing boundary IDs, directions and optional time-constant flags, and `momentumJournal` retains its existing namespace/version and cursor for owner `dominio`. Python validates and replays these inputs through the shared expression producers with an unbound component index `i`. No species, properties or numerical initialization are fabricated. The response remains report version 1 with `draft:true`; additional equation-workbench mutations and numerical compilation remain unavailable until components are declared. Version 1 requests remain compatible as root-only previews; they must not be used for an edited symbolic model. The complete version-2 payload is part of the request identity, including Undo/Redo and boundary changes.

The current client uses **request version 3**, adding required `definition: EquationWorkbench` to the version-2 draft. The envelope may include the same `action` as instantiated models. Python replays both physical journals and additional equation operations with the unbound index; Preview remains read-only, Record saves the returned definition, and Undo/Redo retain the branch. `draft:true` identifies a symbolic source, not disabled authoring. Such a source always has `execution.supported:false`; it never becomes a fictitious chemical component or a solver-ready common model. Versions 1 and 2 remain read-only compatible previews. Request identity includes the complete physical journals and workbench definition; a response for an older source cannot overwrite a later edit.

The material expression producer now includes volume-average inventory definitions and product differentiation, time-constant mean density, uniform source integration, Fick flux substitution, existing orthogonal-coordinate operator expansion with metric terms, common-density convective port relations, uniform-port definitions and time-constant port constraints. These are symbolic Model capabilities, not new spatial solvers. `formulation-summary` selects the same current material graph, including density–volume forms. Unsupported numerical operators still require explicit lowering and cannot fall back to a prior mass equation.

Optional namespace `motores.equationWorkbench` (ordinary models) or `derivacion.equationWorkbench` (native transport metadata):

```ts
{format:'rage.equation-workbench', version:1,
 operations: EquationOperation[], cursor:number}
```

An operation has `kind`, `family` (`matter|momentum|energy|thermodynamics`) and the arguments required by its rule. Supported kinds are `combine`, `substitute`, `isolate`, `expand`, `factor`, `differentiate`, `integrate`, `volume_integrate`, `gauss`, `reynolds`, `zero`, `apply_zero`, `declare_symbol`, `declare_function`, `change_dependencies`, `declare_relation`, `multiply`, `divide`. `sources` references prior equation IDs; `symbol` references a stable quantity ID; substitution adds `relation`; integration adds an explicitly named constant; declarations require a quantity name/unit or dimension-compatible left/right expressions and a physical reason. The common safe expression grammar handles arithmetic; no persisted Python/SymPy source is evaluated. User-facing `q_n` aliases are converted to stable IDs before saving. Units are checked by the shared Python service; affine quantities require a reference.

Additive operation arguments preserve version-1 histories and existing identifiers:

- `declare_relation` optionally carries `relationKind: definition|constitutive|constraint` (default `definition` for existing histories). The selected classification is retained in the graph; a declared premise cannot be labeled as a derived balance.
- `declare_symbol {name,unit}` declares an independent symbolic quantity. `declare_function {name,unit,dependencies:string[]}` declares a quantity depending on existing coordinates or quantities, including compositions such as `u(T(t))`. Dependencies are stable quantity IDs or declared names, not executable source. New names cannot shadow existing quantity identities.
- `change_dependencies {sources:[id],symbol,dependencies,reason}` removes selected arguments from an existing dependent quantity. It records a separate condition and applies it to both sides of the selected equation, evaluating affected derivatives. An empty retained list declares a constant in that equation. It does not erase the original dynamic law or silently change all equations.
- `apply_zero {sources:[id],symbol,reason}` likewise records a zero condition and substitutes it into that equation; the original `zero` rule remains declaration-only for compatibility. Neither action is an unconditional mathematical identity. Their new physical constraints block numerical execution until supported lowering exists.
- `substitute` rejects missing/ambiguous targets, checks replacement dimensions, records denominator conditions, retains both input equations and evaluates derivatives with the chain rule. Arithmetic relations retain denominator conditions even when symbolic cancellation removes them from the final expression.
- `integrate` retains an integration quantity depending on other field arguments, for example `C(t)` after spatial integration. It assigns the integrated unit and rejects name collisions.
- `multiply|divide {sources:[id],right:factorExpression}` scales both sides. Zero and nonfinite factors are rejected; symbolic nonzero conditions are published. These conditional consequences supplement their premises and do not replace a solver equation.

The same strict readers, replay recovery and history actions apply to these additions. These operations do not migrate the remaining family-specific physical producers by themselves.

`POST /modelo/equation-workbench` accepts exactly one common/native envelope and optional `{action:{kind:'append',operation}}` or `undo|redo|rewind`. It returns `rage.equation-workbench-report` version 1: model identity, definition, topologically ordered typed equations, mathematical quantities and execution status. Each equation includes `id,title,family,ownerId,kind,dependent,current,latex,derivation:{rule,inputIds,beforeLatex,assumptions}`. Quantities include stable `id`, readable `input` alias, LaTeX, unit when known, coordinate eligibility and internal identity. Readers reject missing inputs, malformed classifications and unsupported versions. Cursor operations preserve inactive future history; append branches at the current cursor.

The read-only authoring response may additionally carry `replay:{completed,failedOperation,message}` after an upstream edit invalidates a saved operation. `completed` counts the longest valid additional-operation prefix, `failedOperation = completed + 1` is within the requested active cursor, and `execution.supported` must be false. The equations/quantities describe only that valid prefix and the current physical source; `definition` retains the entire original history and cursor. The reader never treats this as a complete executable system. `undo` may return another recovery report if an earlier operation is also invalid; `rewind` preserves all inactive operations. Append/redo and compilation keep strict replay and reject invalid inputs. No recovery report is persisted as a repaired physical definition, and merely viewing it does not change data or results.

**Typed validity guards (22–23 October audit repair).** In-memory equation nodes and operation receipts retain typed predicates separately from explanatory strings. Generated denominator/nonzero conditions survive cancellation and substitutions specialize inherited conditions before accepting a consequence. Even-denominator rational powers retain nonnegative-radicand guards, including before parser cancellation; kernel logarithms retain positive-argument guards. Recorded singleton/sign/interval domains participate in contradiction checks. Unsupported multivariate implications remain explicit unresolved guards, not proofs. Non-finite and non-real numeric expressions are rejected at graph insertion and replay input boundaries. No persisted free-text condition is evaluated as code or silently promoted to a proved predicate.

Differentiation and indefinite integration require a declared quantity depending on the selected coordinate and retain a typed `HoldsOnInterval(equation, coordinate)` premise. A scalar equation constraining that coordinate is insufficient. This premise asserts identity on an interval excluding recorded singularities; it does not prove that identity from a pointwise equality. Real logarithmic antiderivatives use `log(Abs(argument))` with a nonzero guard; even-root antiderivatives retain a nonnegative-radicand guard. Unknown real logarithm arguments are rejected. General real-domain calculus is not certified.

Signatures include predicate structure and units of quantities occurring only in guards. Existing display rows continue to expose rendered conditions in `derivation.assumptions`; no new persisted equation keys are required. New operation guards without numerical enforcement block execution, including conditional scaling and calculus; dependent consequences do not authorize an older solver formulation. Source revision `physical-equation-graphs-7` invalidates affected artifacts. Legacy unsigned histories retain their original records, but invalid replay is rejected and remains recoverable through Undo.

Source material graphs retain local laws, domain/transport theorems, inventory definitions, oriented boundary partitions and actual algebra. Total mass is a dependent sum of component mass, never an extra independent state; combining domains uses common stream identities. The supported momentum source graph includes Cauchy components, recorded stress/density/gravity premises, moving-boundary transport, port averages, axial moments, rotor power and conditional ideal blade transfer. The straight-path projection is checked algebraically against the local Cauchy component. Auxiliary wall and storage developments retain their declared premises; their remaining provenance bridges are not certified by merging them into one graph. Labels use generic mathematical indices; published legacy hydraulic binding keys are preserved.

Typed first-law and thermodynamic producers now participate in the same selectable graph. First-law operations retain internal/kinetic inventories, Gauss/Reynolds terms, explicit pressure decomposition, enthalpy transport, moving-wall work and the full enthalpy product rule. Material and energy use identical component stream quantities; bound momentum ports use their sums. Thermodynamics distinguishes the fundamental differential, definitions, extensive homogeneity and empirical package potential premises. Legendre and Gibbs–Duhem identities are algebraic consequences; package internals and global phase stability are not certified by those identities.

The chronological physical journal remains stored and replayed, including its active cursor. The generated energy/thermodynamic proof is in mathematical dependency order for the replayed state, not a manufactured historical edit transcript. A complete one-to-one chronological edit/proof mapping remains pending. Missing journals stay unrecorded in Transform summaries; they are never replaced with inferred recorded history. All four summary families select current graph rows directly. Compilation/Results carry the same graph for recorded formulations. Within the admitted equilibrium subset, stream/heat/pressure power coefficients are extracted from the derived energy inventory rate; any retained unhandled term blocks that lowering. Legacy unrecorded inputs retain their explicit evidence limitation. General manual-energy, residual/DAE and passage pressure-recovery lowering remain separate findings.

Verification: `tests/test_physical_equation_graphs.py` checks independent open-system/product-rule, moving-wall, Gibbs–Duhem, angular/rotor references, source cursor replay, dimensional errors before cancellation and rejection of an unhandled retained power term. The workbench, journal, hydraulic and cross-workspace suites remain required; frontend strict readers render real Python publications.

The read-only `/modelo/formulation-summary` also accepts exactly `{draft}` with the versioned symbolic authoring payload. It selects the same current physical-family rows as `/modelo/equation-workbench` and preserves all additional-operation rows, including intermediate theorem and singleton-case substitutions, identifies the unbound component index in its notes and grants no numerical capability. A stale operation history is rejected instead of publishing its valid prefix as the selected formulation. Model, Transform and Solve's final-equation presentation share the same frontend source adapter; Solve no longer independently renders the browser formula recipe.

The implementation revision `physical-equation-graphs-5` participates in compilation signatures and frontend execution/formulation signatures for the affected energy, momentum, network and active workbench paths. Earlier transformations/results remain stored but cannot be reused as current evidence for the changed graph implementation. Pure material paths unaffected by the migration retain their existing frontend identity. This is an implementation fingerprint, not a translation or incompatible change to persisted model keys.

Pure consequences retain their premises. `formulation-summary` includes them as system-level derived rows; compilation reports add optional `equationWorkbench` with the same replayed expressions and input graph, retained in Results. This supplements the physical equations; it does not introduce redundant independent solver equations. New arbitrary physical constraints/relations currently block numerical execution with a capability finding. Common/native and browser fallback guards prevent executing the former model silently. Existing supported material generators and hydraulic storage RHS consume the actual derived material expression graph. Unsupported operators require explicit numerical lowering, not a hidden replacement.

Model-only storage adds optional `previousHydraulicNetwork` when an explicit topology/component edit retires numerical bindings that no longer fit. It is archived configuration, not an active common-model namespace, and is never executed. Navigation and display-name changes do not retire bindings. See the maintained [workspace specification](../engine/model-workspaces.md#granular-equation-authoring) and [deduction skill](../../.agents/skills/model-equation-deduction/SKILL.md).

Hydraulic compilation publishes the same current typed graph and distinguishes physical differential `variables` from `auxiliaryStates`. Its imposed-flow specialization can publish an empty physical-variable list with positive diagnostic-state count: known-flow pressure reconstruction does not invent a differential fluid state. The coupled reference retains only its two material inventories and one flow as physical states; conservation totals and verification integrals are not extra physical DOFs.
