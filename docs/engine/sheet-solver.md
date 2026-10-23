# Equation sheets and the independent solver

Delivery: 13 October 2026. Scope: `/motor` only. The lab, its backend, its data and its simulations are not modified. No commit or push.

Energy update, 14 October: the matter scope described here is kept. The first transient assembly of matter and energy for one volume and one species, its derivation, manual u(T) relation, events and evidence are in [docs/engine/energy-foundation.md](energy-foundation.md). The historical energy limits stated below belong to the initial matter delivery. (Since 18 October 2026 the Resolver solves on the common Engine every sheet that reaches it; this browser solver remains for 1D fields and volumetric substitution: ARCHITECTURE.md §10, step 5.1.)

## Use and screens

1. `/motor/hojas`: create a sheet with a name, open, duplicate, archive and restore. No scenarios or physical properties are loaded by default.
2. `/motor/hojas/[id]`: its own derivation. Each operation adds an equation to the sheet. Steps and assumptions are saved automatically; the name is editable. The `/motor` draft can be saved as an independent sheet.
3. `/motor/hojas/[id]/resolver`: final equation, fields by domain and component, values or expressions with units, initial values, horizon and the Resolver button. A counter shows variables/equations, structural DOF, defined data and defined initial values. Method, mesh, samples and tolerances stay in Opciones avanzadas (advanced options).
4. `/motor/hojas/[id]/resultados`: dashboard, table and separate technical details. Charts of chosen variables on X and Y, several curves and units, vertical or side-by-side layout, drag to reorder, adjustable width and height. In 1D there are profiles with a time selector and the evolution per cell. CSV with every time/cell.

The drag and height buttons also accept the keyboard arrows. A dashboard left empty after removing its charts stays empty; it is not rebuilt by default. Adjusting axes for an almost constant signal avoids amplifying numerical noise; it never rounds or modifies the series.

## Which equations are run

The structured formulation of the last step is used; its LaTeX is not interpreted. The compiler's total terms are the same `terminosTotalesMateria` the renderer uses: role, sign, species, port and form of the source. Data expressions are parsed with a limited AST; `eval`, `Function` or any execution of user code are not used in the application.

- **Total transient:** dmᵢ/dt = inlets − outlets − Φᵢ,rest + Gᵢ − Cᵢ. An unknown port is not the same as zero. The complement keeps its external sign. Aggregated sources are kg/s; a rate declared spatially uniform is multiplied by the declared volume. No implicit V=1 is used.
- **Local transient:** with invariance in the three Cartesian directions, dρᵢ/dt = γᵢ − χᵢ is integrated, in kg/m³. Density is not swapped for mass and no volume is invented.
- **Relation m=ρ̄V:** if the domain is not fixed and the density is not constant, the user chooses to give ρ̄(t) or V(t); the other function is obtained from the integrated mass. With a fixed volume, V is given and ρ̄ obtained. These functions do not become unknowns without an additional equation.
- **Final volumetric equation:** if the derivation reaches dV/dt = Q_in − Q_out, V is integrated, with an initial V and Q in volumetric units. A cancelled density is not asked for and no mass is published without it. If there are sources or a remaining flux divided by density, that property is required. The extension V(0)=0 is accepted only for the flow law without domain sources or remaining exchange; it does not claim that the mean density of an empty domain is defined.
- **Transient 1D:** Cartesian local conservation with one active direction (x, y or z), invariance in the other two and a fixed boundary. Convection, general diffusive flux or Fick, generation and consumption are discretized into a single state vector of all species and cells. Integrated amounts are expressed per unit area (kg/m²), without inventing a cross-section.

From 1 to 8 declared species in a domain. Names bring no thermodynamic properties or molar masses. A single species has zero relative diffusion. For several species, the velocity is the mass-average one and Σjᵢ=0 is required. Arbitrary coefficients that contradict that identity are rejected. The Laplacian form requires spatially uniform total density, spatially uniform diffusivity and compatible sources/velocity.

To avoid losing the derivatives of a trace species when subtracting fractions close to one, the identity Σwᵢ=1 (or uniform Σρᵢ) is differentiated: the derivatives of the minor species are kept and that of the dominant species is eliminated. A calculated mass is not projected or corrected. The tests reverse the order of the components and cross-check the analytical mode in traces.

In the total form, local field constraints or local steadiness need additional compatibility with the aggregated fluxes; this delivery blocks them before integrating. They are not ignored to make a result work.

## Data, units and completeness

Every physical value starts empty. An explicit zero is needed to declare a null contribution. Data marked constant in the derivation do not accept an expression that depends on t or on the state. Each field accepts only its available dependencies.

The field's unit is converted to SI. The horizon accepts s/min/h, masses kg/g, fluxes kg/s or kg/h and other units published in `unidadesMotor.ts`; volumetric flows m³/s, L/s, L/min or m³/h. Mass is not converted to moles and `thermo` is not used.

In free expressions, t is in seconds, the active coordinate in metres, m in kg, rho in kg/m³ and V in m³. The selected unit applies to the expression's result. For example, `2*m_A` given in kg/s represents a numerical coefficient of 2 s⁻¹. The aliases `m_A`, `m_B`, `rho_A`, `rho_B`, `m_total` and `rho_total` allow coupling species; they are available only if the necessary amounts are known. γ and χ are non-negative gross rates; oriented flows can reverse direction with a negative value. The user is responsible for formulating rates compatible with the conservation of their reaction: no stoichiometry is fabricated from two generic sources.

+, −, *, /, ^, parentheses, sin, cos, exp, log, sqrt, abs, min, max and step are accepted. There is no internal dimensional check yet of the constants and operations of a free expression. Nor are all its discontinuities located automatically: pulses or steps need enough time resolution and a cross-check by refining samples/tolerances; it is not certified that an under-sampled arbitrary function was captured.

**Structural DOF** counts the required functions/parameters that are missing or invalid. Initial values and horizon are checked separately. Spatial boundary functions stay pending until their type is chosen. It is not a numerical rank or a general proof of independence for PDEs, DAEs or algebraic systems. A complete form is compiled and evaluated initially before Resolver is enabled; an incompatibility is shown without running.

## Methods and numerical limits

- ODE: adaptive Dormand–Prince RK45 5/4, or adaptive implicit Euler by comparing one step with two half steps.
- Implicit Euler: Newton with a full finite-difference Jacobian, scaling per variable and elimination with pivoting. Cross dependencies between species are thus kept. The residual's convergence is scaled with physical magnitudes and tolerances, without an arbitrary floor of 1 kg that would hide traces.
- 1D PDE: conservative finite volumes, first-order upwind convection and centred diffusion; RK45 integration of the semi-discrete system. Step limited by velocity and diffusion (0.4 Δx/max|v| and 0.2 Δx²/max D), in addition to the time error.
- Boundaries: periodic, reservoir values (inlet convection and diffusion; upwind outlet), or no flux. Data that contradict an impermeable boundary are rejected. Fluxes shared between cells cancel with opposite signs.

Tolerances control the **local time error**; they do not guarantee the same global error or the spatial error. Implicit Euler keeps its order one; it needs more steps for fine precision. Upwind's numerical diffusion shrinks as the mesh is refined. BDF/Radau, an implicit spatial discretization, AMR and a tensor solver were not implemented.

Amounts and densities are not clipped to zero in order to continue. A negative crossing stops the trajectory at a non-negative state by bounding the step and returns `parcial`. An initially empty state with extraction stops at t=0. An expression outside its domain, a lack of convergence or the step limit also produce a diagnosis and avoid claiming the horizon was reached. Maximum 150000 steps/attempts, 160 cells, 201 samples; the limits can be revised in future deliveries. The integrator also yields the thread during rejected attempts and accepts cancellation.

The published closure is the change in amount minus the boundary/source budget integrated by the same method. In 1D the budget is calculated with the end fluxes and sources before adding the states, to check the interior cancellation. It is a check of the discretized problem, not a certification of any physical model of the user.

Equations without a time derivative, steady states, inverse problems, the integral form without discretization/reduction, 2D/3D, curvilinear coordinates, moving meshes, energy, momentum or several domains are not run yet. The reason is reported in Resolver. An algebraic equation is not turned into an ODE and dimensions are not silently discarded.

## Persistence and identity

Sheets/configurations/dashboards: localStorage `rage.motor.hojas.v1`. Numerical profiles: IndexedDB `rage-motor-resultados`, compound key [sheet, signature]. The signature includes the formulation, the numerical data and the solver version (`motor-independiente-materia-1`); it is local validity, not authentication.

Editing equations, going back to a step or changing data invalidates results. When the formulation changes, numerical fields that disappear or change magnitude are removed, to avoid reusing kg/s as L/s or the data of a removed port. Duplicating keeps steps/data/dashboard but forces a new calculation. If an edit changes the state variable between mass, density or volume, or moves between a field and an ODE, the dashboard is reset for the new representation; charts of a variable that is no longer solved are not kept. Results are published only if the signature is still valid before and after the asynchronous save; they do not overwrite a calculation of another concurrent formulation. Corrupt sheets are not silently replaced by an empty library. Saving is local to the browser, with no server synchronization or export/import of sheets yet.

## Verification

`npm run test:motor-fundamental` includes the tests of operators, derivation and the single-domain audit, plus `verificar_solver_motor.mjs` with **335 new checks**:

- linear transient solution, bit-for-bit equivalent units, budget balance and draining/initial event;
- direct volumetric equation and ρ(t)/V(t) selection, without fabricating properties;
- stiff kinetics with both methods and coupled A→B conversion against the analytical solution;
- a mass of 1e-20 kg in an implicit nonlinear law, to check scaling;
- periodic advection against the analytical translation and refinement 20/40/80 cells (mean errors 0.04168 / 0.02215 / 0.01142);
- diffusion against the semi-discrete eigenmode, mixing with traces, component order and rejection of incompatible coefficients;
- coupled local sources in 1D, the budget of a no-flux boundary and rejection of an incompatible velocity;
- unsupported dimensions/hypotheses, safe expressions, incompatible units and numerical overflow;
- the chart catalog with the same aliases, mass not invented, axes without modifying data, independence of sheets, duplication and recoverable archiving.

Also: TypeScript and ESLint of the section. Browser QA: sheet→solver→results flow, 100 kg + (10800 kg/h − 2 kg/s) for 10 min = 700 kg; a periodic 1D sheet; duplication and change to dV/dt=Q₁−Q₂ with 100 L and 3−2 L/s, which gives 0.7 m³ at 10 min without asking for density; reload with IndexedDB results; axis selection, reordering by drag and keyboard, height and profile time persistent. The QA sheets are archived recoverably at the end and are not presets of the engine.

## Files and continuity

Compilation: `modeloNumerico.ts`, `expresionesMotor.ts`, `unidadesMotor.ts`. Methods: `integracionMotor.ts`. Documents/results: `hojasMotor.ts`, `resultadosMotor.ts`, `useHojasMotor.ts`. UI: `ModelLibrary` and the four `/models` workspaces, with `ModelWorksheet` as the sole Model layout; `HojaGuardada` supplies the document controller, while `ResolverHoja`, `ResultadosHoja`, `TableroMotor` and `datosGraficasMotor` supply Solve/Results content. The old `BibliotecaHojas` and `BarraHojaMotor` frontends have been removed. There is no dependency on or call to the lab's APIs.

The next mathematical work was still to complete energy and momentum in this same section and to extend expressions/transformations with dimensions and validity conditions. The comparison with the lab will be done later with independent references, without confusing this bounded compiler with a universal multiphysics assembler.

Method references (not libraries invoked): [SciPy, RK45 and the choice of integration methods](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html) and [Clawpack, conservative 1D advection](https://www.clawpack.org/gallery/pyclaw/gallery/advection_1d.html). The numerical implementation of this delivery is the project's own, in TypeScript.

## Sheets prepared for manual checking

At the user's later request, eight complete editable sheets were added, without modifying the solver or creating special cases in it. See [docs/engine/matter-test-sheets.md](matter-test-sheets.md) for data, references, limits and results. They are added explicitly from the library; no scenarios are loaded by default into a new sheet.

## Extension: assembly of several volumes

The reference now accepts networks of transient mass balances, with shared streams, sources and declared laws. The earlier mentions of several domains as pending describe the initial scope. Spatial fields or volumetric states are not yet coupled inside the network. See [docs/engine/matter-coupling.md](matter-coupling.md) for the contract, examples, tests and limits. The backend was neither compared nor modified.
