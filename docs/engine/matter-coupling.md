# Assembly of several volumes — independent matter reference

Delivery: 13 October 2026. Work only in `/motor`. Claude's backend is neither modified nor compared. Spatial dimensions and geometries are not extended. No commit or push.

## What was implemented

A sheet can contain a graph of volumes and streams, with transient mass conservation per species in each volume. External streams have an Exterior end; a connection between volumes has a shared identity Sₖ, with a negative sign at the origin and a positive sign at the destination. The number of balances is N species × V volumes. The global balance is a check of the assembly, not a new independent equation.

The compiler contains no branches by experiment name, by being a tank or a reactor, or by the shape of the network. It builds the conservation rows from each volume's structured terms and their incidences. Internal columns sum to zero. Chains, branchings, mixing and recirculation use the same assembly. A self-circulation has zero net incidence, even if the flow is large.

Each stream expression per component is evaluated once per joint evaluation of the state. That value is distributed through the sparse incidence. The first volume is not solved and its result then passed to the next: states, fluxes and sources are evaluated at the same instant and integrated in a single vector, also in closed circuits. The same integrator accepts RK45 and implicit Euler with a full Jacobian.

The connection **assumes no** composition, perfect mixing, density, discharge law, reaction or equality of properties between volumes. Fluxes per component are given as values or expressions. If an outlet is meant to follow the donor's composition, that relation is written explicitly. Laws can depend on the state of the donor, of the receiver, of other volumes and on time. Gross exchanges are not invented from a net flux.

## Interface and use

1. Open a saved matter sheet and choose **Acoplar varios volúmenes** (couple several volumes). Its current volume, boundaries and data migrate into the assembly; the old inlets/outlets become external streams. Local aliases of flux expressions are converted into volume identities.
2. **+ Volumen** creates a general derivation with the same components, without streams or hypotheses copied from the other volume. Choose Total and apply its own assumptions in the editor. The executable family of this delivery is the transient amount of matter.
3. **Corrientes** (streams) opens a panel on demand. Select origin and destination; Exterior represents the feed or discharge. Ends and names can be edited, and a stream can be declared constant or removed. The ports of the equations are derived from these connections; two independent lists are not kept.
4. Each volume is selected through its tab. It has its own name, derivation and assumptions. Components are identities shared by the sheet: adding/removing/renaming components updates the other volumes' lists, keeping their assumptions. References in an expression that stops being valid are diagnosed, not silently rewritten.
5. **V como dato** (V as a datum) allows declaring the geometric volume/function V(t), according to the chosen boundary, in order to use calculated concentrations. It does not add a constant-density restriction. A uniform source that needs V also asks for it explicitly.
6. **Resolver** shows the balances of every volume, with the shared identities highlighted, the data grouped by volume/component and by stream, units, initial values, horizon and count. Each shared stream is specified once.
7. **Gráficos** (charts) uses stable volume–component identities. It allows choosing masses, global amounts, concentrations when V is known, and shared fluxes. Table and CSV keep those identities. The local and global residuals are in Detalles técnicos (technical details).

Undoing the assembly recovers up to 30 changes of this editing session, including data removed with connections/volumes. It is not presented as a complete historical archive and does not persist after leaving that view. Identity counters do not go back on undo; a new element does not recycle the id of a discarded branch. The per-volume derivations keep their own history. The current topology is common to the active equations; going back to an earlier local derivation does not change the current connections.

Editing, adding or removing elements invalidates the results and renews the dashboard. Selecting another volume tab does not alter the physical signature or invalidate results. The model and the data are stored as additive fields of the current sheets. The earlier single-volume sheets keep using their previous compilation.

## Data and expressions

Examples of identities: `m_A_v1`, `m_A_v2`, `m_B_v1`, `m_total_v1`. A source local to the volume can use `m`, `m_A` or `m_total`; a stream uses explicit volume identities. `V_v1`, `rho_A_v1` and `rho_total_v1` are enabled only when V is declared or required by a uniform source. In expressions, states and time are in SI; the selected unit applies to the result of the field.

There are no default physical values. Zero is given explicitly; a missing stream is a pending datum and counts once, even though it appears in two balances. An initial value per species and volume is required. The gross rates G and C are non-negative; an oriented flow can be negative and represent exchange in the opposite direction. The DOF analysis is still **structural**, separate from initial values and horizon; it is not the general numerical rank of a DAE.

The compatibility of the local assumptions with transport is checked: a non-zero stream cannot be brought into a volume that removed that transport. Duplicated volume, component or stream identities, nonexistent ends and incompatible components are rejected. Field data that disappear are removed; if another field's expression referred to them, it stays invalid until corrected.

The internal dimensionality of free expressions is not certified yet. The function and domain limits of the independent parser still apply; no user JavaScript is evaluated. Not every discontinuity of an arbitrary expression is located automatically. Time tolerances control the local error, not a universal guarantee of global error.

## Numerical scope

Coupling of transient balances of total mass per component. For now, spatial fields are not coupled between domains, and the substitution m=ρ̄V is not run as a volumetric state inside the network. For concentrations, m is kept as the state and V declared as a datum; ρᵢ=mᵢ/V is calculated. Algebraic/steady-state solution and constraints without a time derivative stay outside this compiler.

Explicit limits of the reference calculation: up to 32 volumes, 8 components per volume and 128 total states; implicit Euler up to 64 states. They are not limitations of a chain: the topology is generic and can have branches or cycles within the stated scope. No energy, momentum, hydrodynamics, properties or physical equipment closures were added.

The test of the circuit that is initially empty in some volumes uncovered an ill-conditioned Newton. The scaling of the linear system was fixed with a floor relative to the joint state, keeping the perturbation size of each species and the physical tolerances independent. Masses are not clipped and tolerances are not relaxed in order to solve. The earlier regression of a trace mass of 1e−20 kg still passes.

The depletion of a volume stops the joint calculation and returns `parcial`; the other part is not continued as if the connection were still supplying matter. Events and restrictions follow the limits already documented for the independent solver. The global budget is integrated separately from external streams, Φ_rest and sources. It is not built by simply adding the published residuals.

## Systems ready to test

In the library, **Añadir pruebas de acoplamiento** (add coupling tests) creates six editable sheets without overwriting the existing ones. That catalog is a collection of documents, not special solver code. The cases are complete, ready to press Resolver.

| System | Reference / expected result |
| --- | --- |
| Two tanks in series | m₁=100+t and m₂=200+t; at 600 s: 700 and 800 kg |
| Chain of three with expressions | With z=0.1t: e⁻ᶻ, ze⁻ᶻ and z²e⁻ᶻ/2; at 20 s: 0.135335283, 0.270670566 and 0.270670566 kg |
| Splitting and joining streams | At 60 s: 100, 50, 60 and 40 kg, in four volumes |
| Closed recirculation | Three capacities exchanging mass; total 3 kg; reference with exponential and sine/cosine, approaching 1 kg per volume |
| Selective exchange of A | A₁=(1+e⁻⁰·⁴ᵗ)/2, A₂=(1−e⁻⁰·⁴ᵗ)/2; B stays at 2 and 3 kg |
| Coupled conversion and transport | Consumption of A and generation of B in v1, transport of both species to v2; total A+B=1 kg |

The linear outlet laws of some cases are **explicit expressions chosen for the reference**; they are not imposed because something is a tank, and discharge coefficients are not introduced in every volume.

## Verification

`npm run test:acoplamiento-materia`: **3726 checks**, analytical references at every sample of the six systems, cancellation of internal columns, global budgets, reversed orientation, reordered species/nodes, equivalent units, a nonlinear law, concentration with different volumes, a uniform source, depletion of the donor, self-circulation, migration and the chart catalog. The equations are rendered with KaTeX, without fallback.

The earlier tests of operators, derivation, one volume, solver and the eight simple sheets also pass; all the scripts are included in `npm run test:motor-fundamental`. TypeScript and ESLint are checked separately.

**Visual review pending:** access to localhost through the browser tool was automatically refused because of a usage limit. It was not replaced by another way of controlling the browser, and the new sheets were not loaded into its storage. The user must reload Hojas and press Añadir pruebas de acoplamiento to add them. The mathematical and catalog checks do not depend on that tool.

## Files

- `ensamblajeMateria.ts`: model of domains/streams, migration, terms, incidence, fields, compilation and equations.
- `modeloHojaMotor.ts`: single entry to analyse, sign, compile and solve a simple or coupled sheet.
- `integracionMotor.ts`: generic integration of the joint state and local/global budgets.
- `EditorEnsamblajeMateria.tsx`, `HojaGuardada`, `ResolverHoja`: editing of structure and assumptions, fields and solution.
- `datosGraficasEnsamblaje.ts`, `datosGraficasMotor`, `ResultadosHoja`, `TableroMotor`: identity and display of the results.
- `hojasPruebaAcoplamiento.ts`, `verificar_acoplamiento_materia.mjs`: test documents and independent references.

No routes, algorithms or contracts of the lab backend were changed. The comparison with Claude is left for a future delivery, when the user asks for it. (Since 18 October 2026 the common Engine generates these networks' equations on the server and matches this reference: [docs/engine/balance-engine.md](balance-engine.md).)
