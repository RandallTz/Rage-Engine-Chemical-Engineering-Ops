# Derivation sheet of the fundamental balances

Route `/motor`, entry "Ecuaciones". Current version: 13 October 2026. An independent mathematical reference to define and verify how the lab's engine should be formulated. The goal includes matter, energy and momentum; matter per component is implemented today. It neither modifies nor runs the lab; the comparison between the two is left until this reference is verified. (Since 19 October 2026 every model must start here, from the fundamental equations: ARCHITECTURE.md §2, principle 10.)

## Sheets and independent solution — extension of 13 October

At the user's later request, persistence and an independent matter solver were added. The flow is **Sheets → Equations → Resolver → Charts**. The lab was not modified. The current scope, numerical methods, tests and limits are in [docs/engine/sheet-solver.md](sheet-solver.md).

Transient equations without a mesh and Cartesian 1D fields on a fixed mesh are run. There is not yet a general multiphysics compiler, or a solution of energy, momentum, 2D/3D, inverse problems or steady states of this sheet. Curvilinear coordinates remain available for deriving equations, but not for this discretization.

## Current interaction

The first equation is Accumulation = Inlet − Outlet + Generation − Consumption. Below it there is a vertical sheet. It only starts with the general local conservation, without simplifications. There are no stages to complete, recipes, tank scenarios, targets, schedules or preloaded future steps.

Each user operation adds a row with the equation obtained, the chosen form, its unit and the new relations. Equations stay horizontal while they fit; they are split between terms if the width runs out. Relations already introduced are not repeated in every row.

"Continuar aquí", "Volver al paso N", Inicio, Deshacer and Ir al paso (continue here, go back to step N, start, undo, go to step) restore the chosen configuration and remove the later rows of the sheet. × removes that row's operation and all its continuations: they depend on that formulation, so the derivation is not silently skipped over. The previous step is restored. The starting equation is not removed.

Redo temporarily keeps the removed rows in a separate buffer, which is not printed and does not appear in the step selector. A new operation discards that buffer and continues with consecutive numbering. Cancelled branches are no longer kept on screen or dimmed. Component indices stay stable and are not reused after discarding an operation. "Reiniciar" (restart) begins a new derivation within the sheet. "Hojas" (sheets) allows creating independent documents, duplicating them and archiving them recoverably. Saved sheets keep their history, assumptions and data in this browser; the calculated profiles are stored separately in IndexedDB. There is no export/import of sheets yet; there is CSV export of results.

The operations are on the right. Form, relations and assumptions can be changed in any order. The panel keeps its own position while the sheet brings the new equation into view. There are no calculations or scenario charts on this screen.

## Forms of the same conservation

- **Differential**: ∂ρᵢ/∂t = −∇·(ρᵢv) −∇·jᵢ + γᵢ(x,t) − χᵢ(x,t). ρᵢ and the sources are scalar fields; fluxes and velocities are vectors.
- **Integral**: d/dt ∫V(t) ρᵢ dV = −∮∂V(t) [ρᵢ(v−v_b)+jᵢ]·n dA + ∫V(t) γᵢ dV − ∫V(t) χᵢ dV. Transport relative to a moving boundary is kept. Declaring a fixed boundary removes v_b; it is not chosen by default.
- **Total**: dmᵢ/dt = Σinlets ṁᵢ,p − Σoutlets ṁᵢ,p − Φᵢ,rest + Gᵢ − Cᵢ. Each total is defined through its integral, with the outward normal and the inlet/outlet signs. Moving to the total form does not assume perfect mixing or local uniformity.

The three forms are available operations, not a mandatory path. Choosing Total directly adds only that row; its definitions allow seeing the relation with the field without fabricating steps the user did not take.

## Components and variables by location

"Componentes", at the top of the right panel, allows adding, renaming and removing species. With no components declared, i is a generic template. Adding N components shows N simultaneous conservations in each new row, in any of the three forms. The symbols A, B, etc. are identities of the sheet, not chemical names or CAS numbers; S27 and later are shown as full indices. Names are edited on leaving the field, without adding a row per keystroke.

Renaming keeps the index. Removing does not renumber the rest or modify past rows. Continuing from an earlier row restores its components. A removed index is not recycled for another species, even when replacing cancelled steps. The catalog uses the components of the selected step.

V is the mixture's domain, shared by every species. mᵢ is its contained mass and ρᵢ is the mass of the species per volume of mixture, not the density of the pure compound. No additive Vᵢ are invented. For a real mixture, assigning volumes per species needs additional relations, such as partial molar volumes; see [IUPAC, partial molar quantity](https://goldbook.iupac.org/terms/view/P04418).

The mixture definitions are m=Σmᵢ, ρ=Σρᵢ and wᵢ=ρᵢ/ρ, with Σwᵢ=1 for the complete list of species and ρ>0. The mixture flows are the sum of their per-species flows. A redundant total balance is not added as an independent equation. The velocity convention is mass-average, so Σjᵢ=0. With a single species jᵢ=0 and wᵢ=1 by identity. The relation appears explicitly and its term is removed in all three forms; "Difusión" is disabled with the short reason "Cero · una sola especie" (zero · a single species). The template i, without a complete declared list, does not assume a pure fluid. A scalar Fick law per species does not replace a compatible multicomponent closure: arbitrary independent coefficients can contradict Σjᵢ=0. The sheet keeps this constraint. The bounded solver checks the sum of fluxes during its evaluations and rejects incompatible coefficients; it does not certify a general multicomponent closure.

The panel's operations are common to the components. The rates γᵢ and χᵢ stay independent per species; no kinetics, stoichiometry or reaction is added by selecting generation. Different hypotheses per species and integration with a thermodynamic catalog have not been implemented yet for this sheet.

"Variables" in the bar leads to two columns: **Volumen de control** (shared volume, mass per species, concentrations, sources and internal transport) and **Corrientes y frontera** (mixture and per-species flow, composition of each port, areas and exchange outside the ports). Units and short descriptions stay visible. Geometry and operators have a separate group. It is a symbolic catalog, not a form of numerical specifications. A stream's composition is not automatically set equal to the volume's: that equality needs an additional relation or assumption.

## Local and aggregated sources

Generation and consumption are switched on/off separately. They are gross sources: they are not fabricated by splitting the sign of a net source. Both can be positive with a zero net.

Gᵢ(t) = ∫V γᵢ(x,t) dV and Cᵢ(t) = ∫V χᵢ(x,t) dV. That Gᵢ is a scalar function of time does not mean γᵢ has the same value at every point. Only declaring spatial uniformity allows taking the rate out of the integral and writing γᵢ(t)V(t). Temporal uniformity is not assumed. Generation and consumption have independent hypotheses.

Restrictions on spatial dependence apply to the independent fields and the physical components of v and the general j, not to the metric factors. With every direction invariant, uniformity of the scalar sources of the regular domain also follows. Fick produces a derived j: no additional invariance is imposed on its components by confusing it with the general flux.

Reference: [COMSOL, diffusion equations and conservation per species](https://www.comsol.com/multiphysics/diffusion-equation).

## Geometry and constitutive laws

Cartesian (x,y,z), cylindrical (r,φ,z) and spherical (r,θ,φ) coordinates keep three dimensions. θ is the colatitude, φ the azimuth. The diagrams show coordinates; they do not choose a physical geometry or a mesh.

The operators come from orthogonal metric factors h_a. Divergence: 1/H·∂a(H/h_a·F_a). Scalar diffusion: 1/H·∂a(H/h_a²·κ·∂a f). Keeping radial components constant in curved coordinates does not cancel their divergence: F_r/r or 2F_r/r and the relevant polar contributions remain. The corresponding volume element is printed when the integral form or curvilinear coordinates are used.

Diffusive relations: a general flux without a law; scalar Fick jᵢ=−ρDᵢ∇wᵢ; Fick with ρ and D spatially uniform, which allows Dᵢ∇²ρᵢ. The scalar Fick model does not certify a concentrated multicomponent mixture. Expressions at the origin/poles need regular limits.

Changing coordinates with active restrictions allows reviewing their removal. Independence in x is not automatically turned into independence in r.

## Boundaries and fluxes

Ports are added as time-varying fluxes, with no default flow. Each port can be declared constant afterwards. The total flow is defined by the integral of relative transport through its surface. If a uniform normal flux is declared, the local relation divides the flow by the area; that distribution is not deduced from a total flow.

Φᵢ,rest is the exchange through the whole part of the boundary outside the declared ports, including streams not yet classified. It is positive outward and negative inward; that is why it appears subtracted in the balance. It can represent, for example, matter passing through a membrane. It is not a pipe flow or a reaction rate. An impermeable wall contributes zero. The short help in Fronteras (boundaries) explains the term without adding paragraphs next to the equations. It is removed only by explicitly declaring "Resto de la frontera sin flujo" (rest of the boundary without flux). A tank with only pipes is a choice of boundaries, not a fixed formulation of the editor. Ports must partition surfaces without overlapping when real geometric domains are defined; the current sheet does not certify that topology.

No volumetric source is added to represent a boundary inlet a second time. The partition is made of the declared ports plus their complement, without overlap. A family without ports does not add another unknown sum on top of Φ: that exchange already belongs to the complement. Without any port, Φ covers the whole boundary. Declaring that complement impermeable then gives a closed domain. Without that declaration, the flux stays unknown. Zero flows are not imposed by default.

## Amount, mean density and volume

The generic relation is mᵢ = ρ̄ᵢ V, with ρ̄ᵢ = (1/V)∫Vρᵢ dV and V>0. It is not tied to a pure-liquid recipe or to the absence of reaction. The product rule keeps ρ̄ᵢ dV/dt + V dρ̄ᵢ/dt. Declaring a constant mean density only removes its time derivative: it does not make the local field uniform.

A fixed domain removes dV/dt, but V dρ̄ᵢ/dt can remain. With a fixed domain and a constant mean density the total accumulation vanishes; the constraints on fluxes and sources remain.

Converting to volumetric flows needs the explicit choice "Puertos convectivos, densidad común" (convective ports, common density): jᵢ·n=0 at the ports, ρᵢ,p=ρ̄ᵢ>0 and ṁᵢ,p=ρ̄ᵢQ_p. Each aggregated source and the remaining flux are also divided by ρ̄ᵢ, keeping the units. That conversion is not applied to a diffusive exchange without declaring it.

There are no separate filling and draining scenarios. For a single species, boundaries closed except for its ports, zero sources and the relevant relations, the same conservation can be reduced to dV/dt = Q_in − Q_out. A rigid vessel and a liquid domain with a moving free surface are different concepts.

## Structure and continuity toward multiphysics

- `operadores.ts`: transport operators, independent sources, geometry and boundary notation.
- `recorridoMateria.ts`: structured formulation, differential/integral/total forms, relations and steps with origin, operation and resulting state.
- `catalogoMateria.ts` and `VariablesMateria.tsx`: variables, units and location by domain/stream.
- `GestorComponentesMateria.tsx`: additions, removal and names with a stable identity.
- `ProgresoMateria.tsx`: vertical sheet that prints the equations and relations of each operation.
- `MateriaFundamental.tsx`: the controls of the operations, without presets or logic of a concrete scenario.
- `FormulaMateria.tsx`: horizontal rendering with breaks by available width; it does not modify the common renderer of the rest of the project.

Steps and their operations are structured data, separate from the text of their titles. To extend to energy/momentum and couple systems, conservation families, domains/variables with dimensions, constitutive laws and shared ports must be added. The assembly must keep a single flux reference on both sides of the connection. That work must provide coherent differential and algebraic equations, not join LaTeX texts.

This reference is not an arbitrary CAS or a general multiphysics compiler: it implements the listed transformations for matter. It does not replace freely written formulas or deduce any symbolic identity. It does not discretize or solve PDEs/DAEs, calculate rank or degrees of freedom, validate a real geometry or modify the backend. Formulation, numerical closure and solution are kept separate.

## Verification

`npm run test:motor-fundamental` runs the analytical references of the operators in three coordinate systems and the sheet's test. It covers free order of operations, removal of cancelled steps and recovery with Redo, local sources without implicit uniformity, independent generation/consumption, transport at a moving boundary, the rest of the surface, the product rule, dimensional conversion of sources and 288 combinations of forms/coordinates/restrictions/sources rendered by KaTeX. It also checks 54 configurations with two components (three forms, three coordinate systems, three diffusive relations and two expansion modes), their independent conservation, mixture relations, the signs of Φ, the grouping of variables, identity when renaming/removing/replacing steps and 27 rendered species. TypeScript and ESLint complete the checks. The browser review tests adding, renaming, removing, recovering an earlier row and querying the catalog. The backend and the solution are not modified.

## Background: the plan before the solver was added

This plan belongs to the earlier milestone, when it was still asked not to solve. The current extension is described above and in [docs/engine/sheet-solver.md](sheet-solver.md). The general tree of operators and the multiphysics assembler were still pending; the structured total terms and the numerical expressions are compiled for the verified scopes.

The sheet generates LaTeX expressions from a structured configuration. The mathematical string is not yet a tree of typed expressions, nor is it sent to the lab's numerical assembly. The lab backend already has an assembly of states, terms and residuals for the verified combinations; that implementation does not automatically turn the /motor derivation into executable models. It must not be presented as a single connected engine yet. (The common model, its compiler and the balance engine have since closed much of this gap: ARCHITECTURE.md §10.)

The next work had to extend the mathematical representation, without adding more controls or scenarios:

1. **Typed expressions.** Variables with id, species, domain, physical dimension and spatial/temporal dependence; nodes for sum, product, derivative, gradient, divergence, integral and equation. LaTeX is generated from these objects and stops being the main representation. Transformations record their validity conditions.
2. **Domains and ports.** A variable can belong to an interior field or to a boundary. A connection identifies the same flux between two domains and its opposite signs; it does not copy two independent variables. An imposed stream is a boundary datum and a generation is an interior source.
3. **Relations and assumptions.** Balances keep their general form; constitutive relations add equations and assumptions transform terms explicitly. Integrating keeps the geometry and variable sources; taking a rate out of the integral needs uniformity. Perfect mixing is not presupposed.
4. **Auditable assembly.** Collect equations, shared identities, variables and closures in a single system. Publish provenance, dimensions and pending relations. Distinguish independent equations from global checks. A local differential field needs discretization for a finite numerical residual; do not pretend a matrix system exists just because nabla is printed.

The agreed order was: **one volume / one component for matter**, then the formulation of energy and momentum in that same domain, before extending components or coupling volumes. The matter audit is in [docs/history/frontend/audit-one-volume-matter.md](../history/frontend/audit-one-volume-matter.md); it is not the same as having finished a general compiler. The representation of expressions and transformations had to be built and checked first in that single domain. Only then would the coupling be verified: two volumes, N declared species and a shared stream must produce 2N balances and a single flux identity per species. The same identity appears subtracted in one and added in the other; it cancels when the balances are added. Data and laws stay pending if they were not declared. Testing the total form and its cancellation first makes it easier to verify the assembly, but it does not impose a tank scenario on the model or replace the differential/integral representation. No solver was added in that milestone. The later request authorized the independent, bounded solution documented in [docs/engine/sheet-solver.md](sheet-solver.md). No kinetics, physical hypothesis or default property is added.

### Matter audit: one volume / one component

`verificar_un_volumen_materia.mjs` was added, included in `npm run test:motor-fundamental`. It checks 147 conditions and 66 independent cross-checks, with a maximum relative error of 3.32e-11 against analytical references and central differences. The total terms the renderer consumes carry role, sign, component, port, source form and LaTeX; the references check their signs and transformations without importing or calling the lab. They are not yet a general mathematical tree or an integrator.

Fixes: diffusion of a pure species removed by identity; boundary partition without double counting; zero transport simplified consistently; catalog without fictitious streams. The test loaders now preserve Set iteration when transpiling, so the relations that could previously be left out of those tests are also checked. See the report for cases, conditions and limits.
