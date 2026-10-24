# Engine capabilities

Reviewed: 2026-10-23. Scope inventory, not an individual-run certificate.

Source: frontend/app/checklist/datos.ts. The live page and download use this same registry.

## Mathematical foundation

Workspace: Shared · below multiphysics

- [x] Equipment-independent Python kernel for typed equation graphs, algebra/calculus, explicit units, conditions and ordered replay; no imports from physical producers, packages, compilers or solvers.
- [x] Arbitrary equation groups and dimension-compatible cross-group operations; independent product/chain, mechanical and electrical reference tests use the same kernel.
- [x] Copied replay inputs and immutable operation receipts with actual before/after equations and transitive conditions; atomic append, Undo/Redo and history branching.
- [x] New operations pin input equation content, conditions and units, including substitution relations; changed algebra behind the same ID requires review. Legacy unsigned histories remain unsigned.
- [x] Conditional isolation and substitution retain nonzero linear coefficients lost by cancellation; unsupported or ambiguous branches are rejected.
- [x] Generated denominator, isolation, even-root and logarithm guards are typed predicates, separate from explanatory prose. Substitution checks inherited guards and recorded domains; non-finite/non-real numeric expressions and proved contradictions are rejected. Claude independently verified N1 on revision 7.
- [x] Calculus requires declared coordinate dependence and records an interval-identity premise. Real logarithmic primitives retain absolute values and excluded zeros; new operation validity conditions block Solve until numerical enforcement exists.
- [x] Recorded real/sign domains are typed membership premises in the shared assumptions panel. Degree-one/two polynomial isolation and substitution prove one branch, retain all alternatives and pin their domain inputs.
- [x] Domain contradictions, unresolved membership, empty/multiple admitted branches and unsupported inversions are rejected. Domain edits invalidate dependent derivations and block numerical fallback.
- [x] Bounded exact rational intervals and zero domains in the shared controls; open/closed endpoints, intersections and scoped univariate inequality proofs without numerical sampling.
- [x] Explicit singleton parameter-case substitution rows before inversion; zero coefficients can reduce polynomial degree. Identity, inconsistent and unresolved residual cases remain distinct diagnostics.
- [x] Typed nonzero dimensioned singleton constants retain units through substitution, roots and calculus; explicit interval units produce original/conversion rows using exact rational factors from the shared units service.
- [x] Graph replay preserves unevaluated equations and independent node metadata, including an impossible real equality that must not collapse into a boolean while copied.
- [ ] M1 deduction-readiness gate (D1): D1(1) awaits independent review of the B1 storage-ancestry repair and freshly frozen A/B/C inputs. Energy commutation is enforced without changing its producer; the wall is an explicit constitutive premise. Claude accepted D1(2)–D1(5); their verdicts are retained.
- [ ] General implication/enforcement of validity predicates, migration of legacy free-text physical premises, irrational catalog-conversion detection and visible unsigned-history status remain pending after the independent audit.
- [ ] Extend beyond bounded rational intervals and explicit singleton cases: arbitrary typed-literal authoring, affine references, nonrational conversions, unbounded or symbolic bounds, general inequalities, exhaustive parameter partitions, coalescing regimes, higher degrees and nonpolynomial inversions.
- [ ] Chronological physical-control-to-proof mapping for unused adapters and remaining wall/passage bridges; the M1 energy dependency proof retains separately verified operation commutation.
- [ ] General residual/DAE numerical lowering and adapters for additional disciplines; symbolic kernel references do not certify new product solver families.
- [ ] *Deferred:* New spatial discretization, meshes and geometry solvers.

## Common Engine

Workspace: Model → Transform → Solve → Results

- [x] One versioned model connects the four workspaces; equations and assumptions stay in Model, numerical data and methods in Solve.
- [x] Common contracts for volumes, streams, heat exchanges, units, mathematical equations and results.
- [x] Server-generated balance equations from the effective assumptions of each volume.
- [x] Selectable typed matter, first-law, thermodynamic and linear/angular-momentum graphs: shared algebra/calculus, domain integration, Gauss/Reynolds, unit-checked declarations and reversible equation history in the same Model assumptions panel.
- [x] Dependent quantities, chain-rule substitution and partial-integration constants with units; classified definitions/constitutive relations/conditions; explicit dependency-removal and applied-zero assumptions; equation scaling with nonzero conditions, units and reversible provenance. Symbolic models can record these operations before components exist.
- [x] Named physical regions and connection overview in the shared worksheet; scoped assumptions and optional mathematical operations with pure preview followed by explicit recording.
- [x] Located reduced-hydraulic physical admission requirements, separate from numerical data/initialization checks in Solve; display-label edits preserve flat-assembly execution identity.
- [x] Strict material, first-law and thermodynamic operation journals, with Python replay and comparison against the compiled model.
- [x] Dynamic Model inventories: retained conservation laws, explicit permanent constraints, dependent-flow roles and units, physical domains, operation history and legacy-accumulation review in the same assumptions panel.
- [x] Blank model creation starts at fundamental laws. New examples are created on request through the same assumption tools; the previous product examples and template loader are retired.
- [x] Recoverable removal clears active and archived models from the library without altering scientific data; internal regression inputs are not product templates.
- [x] One canonical Model worksheet for every family, blank or legacy document, ordinary/coupled model and network example: development on the left, assumptions and physical configuration on the right; alternate editors removed.
- [x] Journal and physical-input changes invalidate dependent transformations and results. Editing notes or archived formulations does not change execution identity.
- [x] Component-free symbolic formulations pass unchanged from Model into Transform; Solve displays the same strict Python graph, while missing species or unsupported lowering still blocks execution.
- [x] The multiphysics battery records solved cases, intentional diagnostics and unsupported spatial cases separately.
- [ ] M1 end-to-end usability gate (U1): compile the exact three accepted derived graphs, verify reference/conservation errors and invalidation, and complete an isolated browser walkthrough. Current scoped solver tests do not certify this whole gate.
- [ ] Hierarchical multiphysics model instances with pinned revisions, independent state and typed physical interfaces; the current flat-region assembly is not this capability.
- [ ] Complete auxiliary wall and unused storage/passage provenance bridges beyond the verified workbench path; the M1 wall remains an explicit constitutive premise with no fundamental-law projection claimed.
- [ ] Explicitly rebuild legacy saved models that lack operation history; no invented retrospective derivations.
- [ ] Move the remaining browser-only volume-substitution paths to the common Python compiler.
- [ ] Complete arbitrary transformation chains and solver support for every derived equation family.
- [ ] General numerical lowering of new physical constraints/relations, lossless passage first-law/pressure coupling and chronological physical-edit-to-proof correspondence beyond the current replayed dependency-order proof. Unsupported operations must report findings, never run earlier equations.
- [ ] *Deferred:* Spatial engine migration and discretization extensions, until the user resumes spatial work.

## Matter

Workspace: Model · shared with Solve and Results

- [x] Local conservation → integration, Gauss and Reynolds → component inventories and oriented streams.
- [x] Per-volume recorded assumptions, full mathematical development, undo and reversible legacy rebuilds.
- [x] Physical assumptions update Python equations before components are declared: actual journals, boundary declarations and Undo/Redo drive a versioned symbolic draft with generic index i.
- [x] Typed density–volume/product reductions, uniform sources, Fick flux substitution and existing orthogonal-coordinate operators; common-density port relations and explicit constant/uniform-flow conditions. These authoring operations do not add spatial numerical execution.
- [x] Component identities, per-component flows or total donor flows, accumulation, filling and draining.
- [x] Connected-volume material balances and global conservation checks.
- [x] Total mass balances derived from component sums and marked dependent; domain sums cancel shared internal streams. Supported total-mass compilers consume the actual material expression graph.
- [x] Dynamic liquid inventories coupled to solved hydraulic flow through shared stream incidence, with mass/height/port-pressure reconstruction.
- [x] Declared generation and consumption in the supported balance-expression grammar; reaction thermodynamics is a separate pending capability.
- [x] Cartesian 1D convection and diffusion in the existing spatial path; common Python execution is still pending.
- [x] Units, missing-data diagnostics and structural degree-of-freedom checks within each supported model family.
- [ ] Thermodynamically coupled selective mass-transfer laws and reaction kinetics.
- [ ] Volumetric stream flows in the equilibrium assembly and general momentum/real-fluid flow coupling.
- [ ] General steady-state/DAE balances and inverse problems.
- [ ] General numerical lowering for density–volume and spatial expression graphs; Model and Transform expose the derivation without claiming these forms are universally executable.
- [ ] *Deferred:* Additional spatial geometries and coupled spatial transport; current priority is nonspatial thermodynamics.

## Energy

Workspace: Model · first law, then Solve and Results

- [x] Recorded local → integrated → moving-boundary → total first-law deductions, developed by Python.
- [x] Typed first-law algebra retains moving-boundary work, shared component-flow identities and V dP/dt; recorded equilibrium inventory rates lower from that graph and reject unhandled retained terms.
- [x] Explicit pressure-stress separation, flow work collected into enthalpy, heat, boundary work and declared term-removal assumptions.
- [x] Shared relation/substitution authoring connects two first-law heat rates through an explicit constitutive law; frozen M1-C checks caloric-rate deduction, exact internal cancellation, analytic decay and Transform handoff. Numerical execution of these new relations remains blocked.
- [x] Independent energy journals in network volumes; new templates, rebuild, undo, restore and solver provenance use the same contract.
- [x] Coupled inventories and energy with a declared linear u(T) law and monitored validity interval.
- [x] Uniform equilibrium volumes: U with rigid boundaries and H with prescribed smooth pressure, including V dP/dt.
- [x] Donor enthalpy transport, thermal contact, phase-change trajectories and supported phase-selective extraction.
- [x] Energy budgets, sample certification and second-law checks when the required boundary-temperature data are available.
- [x] Unsupported energy terms, algebraic accumulation and conflicting zero-heat assumptions are rejected by the equilibrium compiler.
- [ ] Reaction energy with consistent thermodynamic reference states.
- [ ] Nonequilibrium heat/mass transfer and mechanical work coupled to momentum.
- [ ] Dynamic solid-phase transitions and discontinuous pressure with a physical jump rule.
- [ ] General steady-state/DAE execution and reliable detection of transitions missed by step sampling.
- [ ] *Deferred:* Spatial energy transport and local material-property coupling.

## Momentum

Workspace: Model · shared matter/energy/thermodynamic coupling

- [x] Recorded Cauchy stress → Newtonian constitutive law → compressible or divergence-free Navier–Stokes, with explicit coefficient assumptions.
- [x] Direct, reversible physical assumptions: Cartesian field/velocity invariance by axis, zero velocity components, transport/force approximations and local or total momentum constraints. All transverse balances remain present.
- [x] Gauss/Reynolds development, impermeable walls, port averages and dynamic hydraulic inertance; signed Darcy–Weisbach losses remain an explicit constitutive closure.
- [x] Typed axial moments of Cauchy conservation, Gauss/Reynolds transport, rigid-rotor power and conditional ideal radial-blade shaft transfer; static-pressure recovery still requires the first-law coupling.
- [x] Dynamic conservation retained beside explicit zero-storage constraints; shared stream bindings, static-pressure identities and mechanical equations routed to their physical panels.
- [x] The same Model worksheet and right-hand assumptions panel, strict versioned journals, Undo, provenance and source-dependent invalidation.
- [x] Equation-operation graphs expose inputs, substitution, integration, boundary constants and isolation; missing wall/reference/geometry assumptions leave deductions incomplete instead of inserting final relations.
- [x] The M1 workbench storage path connects hydrostatic pressure to all three local Cauchy components and recorded zero-rate conditions, deriving horizontal pressure independence before vertical integration; independent D1(1) review remains pending.
- [x] Reduced isothermal hydraulic execution on Python RK45/BDF: constant-density Newtonian liquid, fluid inertia and an explicitly assumed quasi-steady laminar circular wall law.
- [x] Prescribed differentiable flow with recovered pressure, or dynamic path flow coupled to prismatic free-surface inventories and hydrostatic port pressure; no imposed pressure-drop trajectory.
- [x] Shared pressure/flow charts, actual solver strategy, mass and force-impulse diagnostics, signed wall dissipation, and pressure/Reynolds/inventory domain stops.
- [ ] General constrained pressure/flow assembly, consistent DAE initialization, compressible/multiphase hydraulics and coupling to energy/rotor dynamics; unsupported runs remain blocked.
- [ ] Complete lossless passage first-law/pressure recovery, general Darcy constitutive lowering and auxiliary wall/unused-storage provenance bridges. Unbound ports and unsupported passage-energy conditions publish explicit findings.
- [ ] Validated viscosity/transport providers, real pump slip/efficiency/loss data, cavitation and reverse/multiphase machine regimes.
- [ ] Other machine closures, including displacement pumps and compressible rotating equipment.
- [ ] *Deferred:* Spatial Navier–Stokes discretization, turbulence models and resolved blade geometry.

## Thermodynamics

Workspace: Model · shared state-closure service

- [x] Fundamental relation, Legendre transforms, phase partition, equilibrium/stability relations and a distinct thermodynamic assumptions panel.
- [x] Recorded package identity/version, phase policy and manual state assumptions; replay must reproduce the actual model closure.
- [x] Explicit constitutive selection: empirical package data are not claimed to follow from conservation laws.
- [x] Python-developed Euler/Gibbs–Duhem, normalized phase partition and activity/excess-potential caloric relations, displayed in the existing Model worksheet.
- [x] Located phase events retain their numerical state for certified publication; exact event samples preserve incipient phase IDs and independent boundary-work verification.
- [x] Pure water with IAPWS-95; supported TP, PH, UP and UV state closures with published domains.
- [x] Ideal mixtures and existing NRTL data; verified flash examples up to seven ideal and four NRTL components.
- [x] UNIFAC original, Dortmund and LLE in the common thermodynamic layer and compiler, with independent reference checks.
- [x] UNIFAC-LLE: seven admitted species within 10–40 °C (ethyl acetate 25–40 °C, bounded by its ideal-gas Cp data); methanol remains blocked for missing assignments. The catalog publishes each admitted species range per package.
- [x] Liquid–vapor equilibrium and supported liquid–liquid/LLV cases, including water–butanol.
- [x] Property-driven phase discovery in a closed rigid water–1-butanol vessel: one unrestricted policy and one UNIFAC package through heating, with TV/UV closure and independent implementation checks.
- [x] Finite, inventory-bounded Newton trials and package-domain checks before normalization; float-range-bounded invariant-point (heteroazeotrope) polishing; trace-safe ternary stability search and phase seeds down to 1e-300; small-phase and invariant-pressure initialization regressions.
- [x] Single-closure UNIFAC performance within the accepted budgets up to eight species and 1e-300 traces (benchmark, 23 October): seeded dynamic step median <= 0.017 s, TP <= 0.40 s, PH <= 0.23 s, UV <= 2.2 s, with unchanged certification tolerances.
- [x] Static water ice/solid–liquid–vapor equilibrium and the water pressure–temperature diagram.
- [x] Pure-property sources, units, domains and fingerprints; coherent liquid-volume, ideal-Cp and vapor-pressure substitutions.
- [x] Material streams between mixture packages sharing a compatible reference; binary T–xy and P–xy diagrams.
- [x] Binary L–L branches by arc-length continuation, located L–L critical points (the binodal's fold) and certified L–L–V three-phase points in T–xy/P–xy diagrams (liquidoLiquido), checked against an analytic Margules binodal, the package's TP flash and cross-slice consistency.
- [x] Ternary L–L at fixed T and P (tie lines by arc length, plait point, binary-edge ends, certified L–L–V triangle) and multicomponent composition-line slices keeping every species, as core operations checked against an analytic Margules plait point, the TP flash and the binary branch.
- [ ] Material streams between IAPWS and mixture packages; nonideal vapor and high-pressure mixtures.
- [ ] Critical regions beyond the current domain, mixture solid–liquid equilibrium and reaction equilibrium.
- [ ] Solid–liquid diagrams, arc-length continuation of L–V branches, three-liquid ternary regions and multicomponent equilibrium surfaces; an HTTP route and contract for ternary L–L and line slices, and drawing the L–L results in the interface.
- [ ] Broader phase-search/domain reliability in large UNIFAC networks; the located-event publication/work incident has a targeted correction. Volume scaling of network runs is not yet benchmarked.
- [ ] *Deferred:* Experimental validation of UNIFAC predictions, after Engine validation.
- [ ] *Deferred:* NRTL extensions and additional parameter coverage are outside the current priority.

## Transform

Workspace: Transform

- [x] Optional nondimensionalization of supported equations derived from the model; physical and selected scaled execution retain provenance.
- [x] Dimension and unit checks, equivalent formulations and supported invertible variable changes in the nondimensionalization core.
- [x] Compilation inspection identifies retained variables, equation provenance and execution scales.
- [ ] A general composable transformation pipeline with explicit input/output contracts and invalidation.
- [ ] Additional mathematical transformations and solver adapters; nondimensionalization is one optional technique.
- [ ] *Deferred:* Common-engine spatial discretization, mesh/boundary operators and reconstruction of physical fields.

## Solve & Results

Workspace: Solve → Results

- [x] Numerical data, supported method selection, missing-data diagnostics and structural degree-of-freedom inspection.
- [x] Common Python RK45 and BDF paths within their published scopes; time integration belongs to Solve.
- [x] Supported explicit first-order ODE systems and nested UV/PH equilibrium closures.
- [x] Compilation reports distinguish the outer differential system, nested closures and method-dependent Jacobian assembly.
- [x] Transform starts with a Python-replayed summary of matter, energy, momentum status and thermodynamics; Solve starts with the selected formulation, variable maps and compiled balance equations.
- [x] Automatic compilation inspection publishes compatible time integrators and a mathematical solution plan: initialization, conserved states, local equilibrium/donor coupling, time stepping, phase events and verification. It is a plan, not an iteration transcript.
- [x] Shared charts with animated drag-to-swap layout, saved ordering, keyboard movement and reduced-motion support; tables, events, physical reconstruction, conservation diagnostics and recorded derivation signatures.
- [ ] General nonlinear algebraic/DAE systems, sparse solver-dependent assembly and a universal matrix inspector.
- [ ] Constrained dynamic integration and consistent initialization for fixed inventories; current compilers reject those constraints explicitly. Persistent real-time sessions and perturbation timelines remain future work.
- [ ] Universal rank/invertibility proofs and general inverse simulation; structural counts alone are not such proofs.
