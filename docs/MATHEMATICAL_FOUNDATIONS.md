# Mathematical, Physical, and Algorithmic Foundations of the Simulation Engine
## A Rigorous Formal Specification for Applied Mathematicians, Chemical Engineers, and Autonomous Agents

**Document Reference:** `DOC-MATH-ENG-2026-CANONICAL-V2`  
**Authors:** Antigravity Architecture, Numerical Analysis & Thermodynamics Core Team  
**Date:** 20 October 2026  
**Status:** Invariant Mathematical Specification (Canonical Reference)  
**Contractual References:** [ARCHITECTURE.md](../../ARCHITECTURE.md), [docs/contracts/common-model.md](contracts/common-model.md), [docs/contracts/thermodynamic-layer.md](contracts/thermodynamic-layer.md), [docs/contracts/results-format.md](contracts/results-format.md), [docs/contracts/units-service.md](contracts/units-service.md), [docs/engine/model-workspaces.md](engine/model-workspaces.md).

---

## Abstract

This monograph establishes the foundational mathematics, continuum physics, thermodynamic state closures, numerical algorithms, symbolic compilation theory, and dimensional analysis governing the equation-oriented multiphysics process simulation engine. Operating under the four-workspace paradigm (**Model $\to$ Transform $\to$ Solve $\to$ Results**) and strictly adhering to Principle 10, the engine rejects empirical "unit operation" templates and hardcoded equipment heuristics. Every model, from single-phase dynamic vessels to multi-component flash columns, reactive distillation segments, and hydraulic piping networks, is derived from the fundamental microscopic conservation laws of continuum mechanics (mass, linear momentum, angular momentum, and total energy) paired with rigorous, always-present thermodynamic closures.

This specification provides an exhaustive mathematical formulation of:
1. Microscopic Eulerian conservation laws and their macroscopic reduction via the Reynolds Transport Theorem for moving, deforming control volumes $\Omega(t)$.
2. Interphase transport phenomena, interface jump conditions, Stefan-Maxwell multicomponent diffusion, and non-Newtonian rheology.
3. The complete deduction of one-dimensional hydraulic inertance, Churchill friction factor equations, and turbomachinery Euler characteristics from Cauchy momentum.
4. The variational foundation of multiphase equilibrium via Michelsen Tangent Plane Distance ($TPD$) and Kuhn-Tucker complementarity conditions ($\beta_k \ge 0, tm_k \ge 0, \beta_k \cdot tm_k = 0$) solved via semismooth Newton methods.
5. The exact thermodynamic state formulations of IAPWS-95 (pure water with all 56 residual Helmholtz terms) and UNIFAC/NRTL (non-ideal liquid mixtures), including machine-precision complex-step differentiation for caloric excess properties.
6. The complete theory of the **Nondimensionalization Module**:
   - Buckingham $\Pi$ theorem matrix formulation and exact rational nullspace computation over $\mathbb{Q}$.
   - Dimensional vector spaces over $\mathbb{Q}^7$, affine temperature transformations, and unit projection.
   - Continuous Lie scaling groups, infinitesimal generators, and similarity reductions from PDEs to ODEs.
   - Logarithmic formulation of normalization objectives and certified equivalence proofs.
   - Kruskal's method of dominant balance, Newton polygon upper envelopes, and singular perturbation boundary layer analysis.
   - Linear stability, dispersion relations $\sigma(k)$, Turing instabilities, and pseudo-arclength continuation of bifurcations.
   - Method of Lines (MOL) spatial semi-discretization with cell Péclet heuristics, CFL stability bounds, and ghost-cell Newton boundary solvers.
7. Directed Acyclic Graph (DAG) compilation, Tarjan strongly connected components (SCC), Block Lower Triangular (BLT) partitioning, bipartite Dulmage-Mendelsohn structural analysis, and Differential-Algebraic Equation (DAE) Pantelides index reduction.
8. Adaptive Runge-Kutta-Fehlberg (RK45), stiff variable-order Backward Differentiation Formula (BDF), and Radau IIA integration with signature-based bisection and warm restarts across $C^1$ derivative kinks.
9. Global integral conservation verification, Clausius-Duhem Second Law entropy generation diagnostics, and five closed-form analytical benchmark problems.
10. A comprehensive architectural and mathematical **Proposal for Spatial Treatment, Differential Geometry, and Multidimensional Discretization** covering Riemannian metric tensors on curvilinear manifolds, Cell-Centered Finite Volume Methods (FVM), Total Variation Diminishing (TVD) high-resolution flux limiters, conjugate phase interface jump solvers, Adaptive Mesh Refinement (AMR), sparse Jacobian block structuring, and Method of Manufactured Solutions (MMS) spatial verification.
11. The fundamental mathematical derivation of chemical engineering **Unit Operations and Reactive Separation Systems** (Dynamic reactive distillation MESH-D equations with hydraulic tray weeping/flooding, rate-based two-film multicomponent mass transfer, non-isothermal CSTR/PFR reactors with Danckwerts boundary conditions, heterogeneous catalytic pellets with Thiele moduli and effectiveness factors, LMTD/$\epsilon$-NTU heat exchanger networks, and piping manifold hydraulic loops).
12. **Non-Equilibrium Thermodynamics and Onsager Reciprocity:** Bilinear local entropy production $\sigma_s \ge 0$, Curie's symmetry principle, Onsager reciprocal symmetry $L_{ij} = L_{ji}$, cross-coupled thermal diffusion (Soret) and diffusion thermo-effects (Dufour), interfacial excess thermodynamics, and Marangoni surface tension gradient instabilities along boiling and falling liquid films.
13. **Turbulence Closures on Generalized Unstructured Grids:** Reynolds-Averaged Navier-Stokes (RANS) closures, Lumley realizability constraints, Kato-Launder production limiters suppressing stagnation point anomalies, low-Reynolds Launder-Sharma damping, Menter Shear Stress Transport (SST) $k-\omega$ blending, Wall-Adapting Local Eddy-viscosity (WALE) subgrid LES, Delayed Detached Eddy Simulation (DDES), and turbulent scalar transport.
14. **Volume-Averaging Theory (VAT) and Porous Homogenization:** The Slattery-Whittaker averaging theorem with moving boundary corrections, generalized Brinkman-Forchheimer-Darcy momentum equations, anisotropic Ergun and structured packing (Mellapak) drag tensors, multicomponent hydrodynamic dispersion, dual-porosity catalytic pellet models, and Beavers-Joseph-Saffman permeable wall jump conditions.
15. **DAE Sensitivity Analysis, Adjoint Equations, and Dynamic Optimization:** Parametric Jacobians, linear forward sensitivity DAEs with staggered LU reuse, variational derivation of continuous and discrete adjoint DAE systems with $N_p$-independent gradient evaluation, exact Hessian-vector products via second-order adjoints, and large-scale dynamic start-up optimization of reactive distillation columns via orthogonal Radau collocation (IPOPT).
16. **Mathematical Treatment and Software Architecture Implementation Methodology:** The formal translation of continuum mathematics and thermodynamic closures into software: the "Engine of Engines" architecture, the Common Model (`rage.modelo`) data structures and $\mathbb{Q}^7$ typed expression ASTs, the deduction algebra $\mathcal{O}_{\text{ded}}$ of the balance generator, the transformation and spatial discretization pipelines, bipartite matching and Dulmage-Mendelsohn structural analysis, Tarjan SCC Block Lower Triangular (BLT) partitioning, Pantelides index reduction, stiff numerical execution kernels (Radau IIA / BDF) with event bisection and warm restarts across phase kinks, and scientific verification layers.

---

## Table of Contents

- [1. Mathematical Conventions and Tensor Notation](#1-mathematical-conventions-and-tensor-notation)
- [2. Continuum Mechanics and Transport Laws](#2-continuum-mechanics-and-transport-laws)
  - [2.1 Multi-Component Species Mass Conservation](#21-multi-component-species-mass-conservation)
  - [2.2 Multicomponent Diffusion: Stefan-Maxwell vs. Fickian Diffusion](#22-multicomponent-diffusion-stefan-maxwell-vs-fickian-diffusion)
  - [2.3 Linear and Angular Momentum Conservation](#23-linear-and-angular-momentum-conservation)
  - [2.4 Constitutive Rheology: Newtonian and Non-Newtonian Fluids](#24-constitutive-rheology-newtonian-and-non-newtonian-fluids)
  - [2.5 Total Energy and Internal Energy Conservation](#25-total-energy-and-internal-energy-conservation)
  - [2.6 Reynolds Transport Theorem on Arbitrary Deforming Volumes](#26-reynolds-transport-theorem-on-arbitrary-deforming-volumes)
  - [2.7 Interphase Jump Conditions and Boundary Interfaces](#27-interphase-jump-conditions-and-boundary-interfaces)
  - [2.8 Macroscopic Control Volume Lumped Balances](#28-macroscopic-control-volume-lumped-balances)
  - [2.9 Momentum Reduction: Hydraulic Inertance and Turbomachinery](#29-momentum-reduction-hydraulic-inertance-and-turbomachinery)
  - [2.10 Friction Losses: Churchill and Colebrook-White Formulations](#210-friction-losses-churchill-and-colebrook-white-formulations)
  - [2.11 Open Channel and Orifice Hydraulics: Francis Weir Formula](#211-open-channel-and-orifice-hydraulics-francis-weir-formula)
  - [2.12 Compressible Conduit Flow: Sonic Choking and Critical Pressure Ratio](#212-compressible-conduit-flow-sonic-choking-and-critical-pressure-ratio)
  - [2.13 Dynamic Inventory Retention Policy](#213-dynamic-inventory-retention-policy)
- [3. Thermodynamic Equilibrium and Complementarity Layer](#3-thermodynamic-equilibrium-and-complementarity-layer)
  - [3.1 Variational Formulation of Phase Equilibrium](#31-variational-formulation-of-phase-equilibrium)
  - [3.2 Michelsen Tangent Plane Distance and Phase Stability Analysis](#32-michelsen-tangent-plane-distance-and-phase-stability-analysis)
  - [3.3 Kuhn-Tucker Complementarity Conditions for Candidate Phases](#33-kuhn-tucker-complementarity-conditions-for-candidate-phases)
  - [3.4 Semismooth Newton Solvers for Complementarity Systems](#34-semismooth-newton-solvers-for-complementarity-systems)
  - [3.5 Multiphase Flash Algorithms (TP, UV, and PH Flashes)](#35-multiphase-flash-algorithms-tp-uv-and-ph-flashes)
  - [3.6 Monotonic Step-Limiting for Rachford-Rice Objective Functions](#36-monotonic-step-limiting-for-rachford-rice-objective-functions)
  - [3.7 Constitutive Equation of State: Pure Water via Full IAPWS-95 Formulation](#37-constitutive-equation-of-state-pure-water-via-full-iapws-95-formulation)
  - [3.8 Constitutive Liquid Activity: UNIFAC Group Contribution Models](#38-constitutive-liquid-activity-unifac-group-contribution-models)
  - [3.9 Complex-Step Numerical Differentiation of Excess Properties](#39-complex-step-numerical-differentiation-of-excess-properties)
  - [3.10 Euler Homogeneity and Gibbs-Duhem Consistency Checks](#310-euler-homogeneity-and-gibbs-duhem-consistency-checks)
- [4. Mathematical Theory of Nondimensionalization, Asymptotics, Symmetries, and Dynamics](#4-mathematical-theory-of-nondimensionalization-asymptotics-symmetries-and-dynamics)
  - [4.1 Dimensional Vector Spaces over $\mathbb{Q}^7$ and Unit Projections](#41-dimensional-vector-spaces-over-mathbbq7-and-unit-projections)
  - [4.2 The Fundamental Theorem of Dimensional Analysis: Matrix Formulation over $\mathbb{Q}$](#42-the-fundamental-theorem-of-dimensional-analysis-matrix-formulation-over-mathbbq)
  - [4.3 Continuous Transformation Groups and Invariant Symmetries (Lie Theory)](#43-continuous-transformation-groups-and-invariant-symmetries-lie-theory)
  - [4.4 Similarity Reductions and Traveling Wave Invariants](#44-similarity-reductions-and-traveling-wave-invariants)
  - [4.5 Logarithmic Formulation of Normalization Objectives and Equivalence Certificates](#45-logarithmic-formulation-of-normalization-objectives-and-equivalence-certificates)
  - [4.6 Kruskal's Method of Dominant Balance and Asymptotic Layer Analysis](#46-kruskals-method-of-dominant-balance-and-asymptotic-layer-analysis)
  - [4.7 Linear Stability, Dynamical Systems, and Dispersion Relations](#47-linear-stability-dynamical-systems-and-dispersion-relations)
  - [4.8 Pseudo-Arclength Numerical Continuation of Equilibrium Curves](#48-pseudo-arclength-numerical-continuation-of-equilibrium-curves)
  - [4.9 Method of Lines (MOL) Numerical Simulation of Dimensionless Systems](#49-method-of-lines-mol-numerical-simulation-of-dimensionless-systems)
- [5. Symbolic Model Compilation and Structural Index Theory](#5-symbolic-model-compilation-and-structural-index-theory)
  - [5.1 Typed Directed Acyclic Graph (DAG) Representation](#51-typed-directed-acyclic-graph-dag-representation)
  - [5.2 Block Lower Triangularization via Tarjan's SCC Algorithm](#52-block-lower-triangularization-via-tarjans-scc-algorithm)
  - [5.3 Bipartite Matching, Dulmage-Mendelsohn Decomposition, and DOFs](#53-bipartite-matching-dulmage-mendelsohn-decomposition-and-dofs)
  - [5.4 DAE Index Classification and Structural Pantelides Reduction](#54-dae-index-classification-and-structural-pantelides-reduction)
  - [5.5 Mattsson-Söderlind Dummy Derivative Method](#55-mattsson-soderlind-dummy-derivative-method)
  - [5.6 Algebraic Compatibility Constraints on Invariant Inventories](#56-algebraic-compatibility-constraints-on-invariant-inventories)
- [6. Numerical Solvers and Discontinuity Localization](#6-numerical-solvers-and-discontinuity-localization)
  - [6.1 Embedded Runge-Kutta-Fehlberg (RK45) Integration](#61-embedded-runge-kutta-fehlberg-rk45-integration)
  - [6.2 Stiff Variable-Order Backward Differentiation Formulas (BDF)](#62-stiff-variable-order-backward-differentiation-formulas-bdf)
  - [6.3 Fully Implicit Radau IIA Collocation for Index-1 and Index-2 DAEs](#63-fully-implicit-radau-iia-collocation-for-index-1-and-index-2-daes)
  - [6.4 Phase Signature Tracking and Event Bisection Across $C^1$ Kinks](#64-phase-signature-tracking-and-event-bisection-across-c1-kinks)
  - [6.5 Warm-Restart Protocol and Step-Size Re-Initialization](#65-warm-restart-protocol-and-step-size-re-initialization)
- [7. Numerical Verification and Analytical Benchmark Theorems](#7-numerical-verification-and-analytical-benchmark-theorems)
  - [7.1 Global Integral Conservation Residuals of Mass and Energy](#71-global-integral-conservation-residuals-of-mass-and-energy)
  - [7.2 Second Law Clausius-Duhem Entropy Generation Certification](#72-second-law-clausius-duhem-entropy-generation-certification)
  - [7.3 Benchmark 1: Unsteady Multicomponent Batch Diffusion with Chemical Reaction](#73-benchmark-1-unsteady-multicomponent-batch-diffusion-with-chemical-reaction)
  - [7.4 Benchmark 2: Hydraulic Surge and Water Hammer in Pipe Networks](#74-benchmark-2-hydraulic-surge-and-water-hammer-in-pipe-networks)
  - [7.5 Benchmark 3: Binary Vapor-Liquid Flash Equilibrium](#75-benchmark-3-binary-vapor-liquid-flash-equilibrium)
  - [7.6 Benchmark 4: The Classical Stefan Moving Boundary Problem](#76-benchmark-4-the-classical-stefan-moving-boundary-problem)
  - [7.7 Benchmark 5: Singularly Perturbed Boundary Layer with Exact Matched Asymptotics](#77-benchmark-5-singularly-perturbed-boundary-layer-with-exact-matched-asymptotics)
- [8. Comprehensive Mathematical Proposal for Spatial Treatment, Generalized Meshes, and Multiphysics Discretization](#8-comprehensive-mathematical-proposal-for-spatial-treatment-generalized-meshes-and-multiphysics-discretization)
  - [8.1 Architectural Paradigm and Pipeline Integration (Model $\to$ Transform $\to$ Solve $\to$ Results)](#81-architectural-paradigm-and-pipeline-integration-model-to-transform-to-solve-to-results)
  - [8.2 Differential Geometry, Manifolds, and Unified 1D, 2D, and 3D Formulations](#82-differential-geometry-manifolds-and-unified-1d-2d-and-3d-formulations)
  - [8.3 Mathematical Theory of Generalized Meshes: Cartesian, Hexagonal, Simplicial, and Polyhedral](#83-mathematical-theory-of-generalized-meshes-cartesian-hexagonal-simplicial-and-polyhedral)
  - [8.4 The Multiphysics Coupling Framework: 4-Way Balance Interactions and Conjugate Transports](#84-the-multiphysics-coupling-framework-4-way-balance-interactions-and-conjugate-transports)
  - [8.5 Rigorous Cell-Centered Finite Volume Method (FVM) on Arbitrary Grids](#85-rigorous-cell-centered-finite-volume-method-fvm-on-arbitrary-grids)
  - [8.6 High-Resolution Monotonic TVD Schemes and Multidimensional Flux Limiters](#86-high-resolution-monotonic-tvd-schemes-and-multidimensional-flux-limiters)
  - [8.7 Boundary Conditions and Conjugate Phase Interface Jumps](#87-boundary-conditions-and-conjugate-phase-interface-jumps)
  - [8.8 Adaptive Mesh Refinement (AMR) on Generalized Mesh Topologies](#88-adaptive-mesh-refinement-amr-on-generalized-mesh-topologies)
  - [8.9 Semi-Discrete DAE Assembly, Monolithic vs. Partitioned Structuring, and Block Solvers](#89-semi-discrete-dae-assembly-monolithic-vs-partitioned-structuring-and-block-solvers)
  - [8.10 Spatial Verification: Method of Manufactured Solutions (MMS) for 1D, 2D, and 3D Multiphysics](#810-spatial-verification-method-of-manufactured-solutions-mms-for-1d-2d-and-3d-multiphysics)
  - [8.11 Pressure-Velocity-Density Coupling on Colocated Generalized Meshes (Rhie-Chow, PISO, and SIMPLE)](#811-pressure-velocity-density-coupling-on-colocated-generalized-meshes-rhie-chow-piso-and-simple)
  - [8.12 High-Order Discontinuous Galerkin (DG) and Multidimensional Riemann Solvers](#812-high-order-discontinuous-galerkin-dg-and-multidimensional-riemann-solvers)
  - [8.13 Implicit-Explicit (IMEX) Time Integration for Stiff Multiphysics Systems](#813-implicit-explicit-imex-time-integration-for-stiff-multiphysics-systems)
  - [8.14 Dynamic Interface and Free Surface Tracking: VOF, Level Set, and CLSVOF](#814-dynamic-interface-and-free-surface-tracking-vof-level-set-and-clsvof)
  - [8.15 Parallel Domain Decomposition and Nonlinear Preconditioning (PETSc/Trilinos Architecture)](#815-parallel-domain-decomposition-and-nonlinear-preconditioning-petsctrilinos-architecture)
- [9. Mathematical Derivation of Unit Operations and Reactive Separation Systems from Fundamental Laws](#9-mathematical-derivation-of-unit-operations-and-reactive-separation-systems-from-fundamental-laws)
  - [9.1 Fundamental Derivation Methodology: From First Principles to Unit Envelopes](#91-fundamental-derivation-methodology-from-first-principles-to-unit-envelopes)
  - [9.2 Reactive Distillation and Equilibrium Stage Separations (MESH-D Formulation)](#92-reactive-distillation-and-equilibrium-stage-separations-mesh-d-formulation)
  - [9.3 Non-Equilibrium Rate-Based Transport Modeling (Two-Film Theory)](#93-non-equilibrium-rate-based-transport-modeling-two-film-theory)
  - [9.4 Chemical Reaction Engineering: CSTR, PFR, and Heterogeneous Catalysis](#94-chemical-reaction-engineering-cstr-pfr-and-heterogeneous-catalysis)
  - [9.5 Heat Exchange Networks, LMTD, and Conjugate Thermal Walls](#95-heat-exchange-networks-lmtd-and-conjugate-thermal-walls)
  - [9.6 Fluid Machinery and Piping Manifold Networks](#96-fluid-machinery-and-piping-manifold-networks)
  - [9.7 Shortcut Distillation and Multicomponent Design Methods](#97-shortcut-distillation-and-multicomponent-design-methods)
  - [9.8 Transient Batch Distillation and the Rayleigh Equation](#98-transient-batch-distillation-and-the-rayleigh-equation)
  - [9.9 Continuous Packed Columns and Differential Mass Transfer](#99-continuous-packed-columns-and-differential-mass-transfer)
  - [9.10 Liquid-Liquid Extraction (LLE) and Immiscible Decanters](#910-liquid-liquid-extraction-lle-and-immiscible-decanters)
  - [9.11 Compressible Conduit Gas Dynamics, Fanno/Rayleigh Flow, and Sonic Choking](#911-compressible-conduit-gas-dynamics-fannorayleigh-flow-and-sonic-choking)
  - [9.12 Acoustic Water Hammer and Method of Characteristics (MOC)](#912-acoustic-water-hammer-and-method-of-characteristics-moc)
- [10. Non-Equilibrium Thermodynamics, Onsager Reciprocity, and Interfacial Marangoni Phenomena](#10-non-equilibrium-thermodynamics-onsager-reciprocity-and-interfacial-marangoni-phenomena)
  - [10.1 Local Entropy Production Rate and Second Law Formulation](#101-local-entropy-production-rate-and-second-law-formulation)
  - [10.2 Conjugate Thermodynamic Fluxes and Generalized Forces](#102-conjugate-thermodynamic-fluxes-and-generalized-forces)
  - [10.3 The Phenomenological Matrix and Onsager Reciprocal Relations](#103-the-phenomenological-matrix-and-onsager-reciprocal-relations)
  - [10.4 Cross-Coupling Effects: Soret and Dufour Phenomena](#104-cross-coupling-effects-soret-and-dufour-phenomena)
  - [10.5 Interfacial Non-Equilibrium Jump Thermodynamics and Surface Excess Balances](#105-interfacial-non-equilibrium-jump-thermodynamics-and-surface-excess-balances)
  - [10.6 Marangoni Convection and Interfacial Surfactant/Thermal Instabilities](#106-marangoni-convection-and-interfacial-surfactantthermal-instabilities)
  - [10.7 Positive Entropy Generation Certification in Equation-Oriented Compilers](#107-positive-entropy-generation-certification-in-equation-oriented-compilers)
- [11. Turbulence Closures and Multiphysics Reynolds-Averaged Transport on Unstructured Polyhedra](#11-turbulence-closures-and-multiphysics-reynolds-averaged-transport-on-unstructured-polyhedra)
  - [11.1 The Reynolds Averaging Operator and the Reynolds Stress Closure Problem](#111-the-reynolds-averaging-operator-and-the-reynolds-stress-closure-problem)
  - [11.2 Boussinesq Turbulent Viscosity Hypothesis and Realizability Constraints](#112-boussinesq-turbulent-viscosity-hypothesis-and-realizability-constraints)
  - [11.3 Two-Equation Eddy-Viscosity Models: Standard $k-\epsilon$ and Launder-Sharma Formulation](#113-two-equation-eddy-viscosity-models-standard-k-epsilon-and-launder-sharma-formulation)
  - [11.4 Menter Shear Stress Transport (SST) $k-\omega$ Model with Spatial Blending](#114-menter-shear-stress-transport-sst-k-omega-model-with-spatial-blending)
  - [11.5 Large Eddy Simulation (LES): Top-Hat Filtering and the WALE Subgrid Model](#115-large-eddy-simulation-les-top-hat-filtering-and-the-wale-subgrid-model)
  - [11.6 Detached Eddy Simulation (DES/DDES) for Industrial Separation Units](#116-detached-eddy-simulation-desddes-for-industrial-separation-units)
  - [11.7 Turbulent Heat and Mass Transfer: Reynolds-Colburn Analogy](#117-turbulent-heat-and-mass-transfer-reynolds-colburn-analogy)
- [12. Volume-Averaging Theory (VAT) and Homogenization in Reactive Packed Beds and Porous Media](#12-volume-averaging-theory-vat-and-homogenization-in-reactive-packed-beds-and-porous-media)
  - [12.1 The Spatial Volume-Averaging Theorem (Slattery-Whittaker Formulation)](#121-the-spatial-volume-averaging-theorem-slattery-whittaker-formulation)
  - [12.2 Derivation of Macroscopic Continuity, Momentum, and Energy in Porous Architectures](#122-derivation-of-macroscopic-continuity-momentum-and-energy-in-porous-architectures)
  - [12.3 Generalized Brinkman-Forchheimer-Darcy Momentum Equation and Non-Linear Drag Tensors](#123-generalized-brinkman-forchheimer-darcy-momentum-equation-and-non-linear-drag-tensors)
  - [12.4 Multicomponent Hydrodynamic Dispersion Tensors and Anisotropic Tortuosity](#124-multicomponent-hydrodynamic-dispersion-tensors-and-anisotropic-tortuosity)
  - [12.5 Dual-Porosity and Dual-Permeability Formulations for Reactive Catalytic Pellets](#125-dual-porosity-and-dual-permeability-formulations-for-reactive-catalytic-pellets)
  - [12.6 Boundary Layer Jump Conditions at Porous-Fluid Interfaces](#126-boundary-layer-jump-conditions-at-porous-fluid-interfaces)
- [13. Forward Sensitivity Analysis, Adjoint DAE Systems, and Dynamic Optimization](#13-forward-sensitivity-analysis-adjoint-dae-systems-and-dynamic-optimization)
  - [13.1 Parameterized Nonlinear DAE Systems and Parametric Jacobian Operators](#131-parameterized-nonlinear-dae-systems-and-parametric-jacobian-operators)
  - [13.2 Forward Sensitivity Equations and Staggered vs. Simultaneous Newton Solution](#132-forward-sensitivity-equations-and-staggered-vs-simultaneous-newton-solution)
  - [13.3 Variational Derivation of Continuous Adjoint DAE Systems](#133-variational-derivation-of-continuous-adjoint-dae-systems)
  - [13.4 Discrete Adjoint Formulations for Radau IIA Collocation](#134-discrete-adjoint-formulations-for-radau-iia-collocation)
  - [13.5 Exact Gradient and Hessian Vector-Product Evaluations for Optimization](#135-exact-gradient-and-hessian-vector-product-evaluations-for-optimization)
  - [13.6 Dynamic Optimization and Nonlinear Model Predictive Control (NMPC) of Reactive Distillation Start-Up](#136-dynamic-optimization-and-nonlinear-model-predictive-control-nmpc-of-reactive-distillation-start-up)
- [14. Mathematical Treatment and Software Architecture Implementation Methodology](#14-mathematical-treatment-and-software-architecture-implementation-methodology)
  - [14.1 Architectural Foundations: The "Engine of Engines" Paradigm](#141-architectural-foundations-the-engine-of-engines-paradigm)
  - [14.2 The Common Model (`rage.modelo`) Data Structures and Mathematical Ontology](#142-the-common-model-ragemodelo-data-structures-and-mathematical-ontology)
  - [14.3 Model Workspace: Mathematical Deduction and Balance Generation Engine](#143-model-workspace-mathematical-deduction-and-balance-generation-engine)
  - [14.4 Transform Workspace: Transformation Pipelines, Symmetries, and Discretization](#144-transform-workspace-transformation-pipelines-symmetries-and-discretization)
  - [14.5 Solve Workspace: Symbolic Compilation, Index Theory, and Numerical Execution](#145-solve-workspace-symbolic-compilation-index-theory-and-numerical-execution)
  - [14.6 Results Workspace: Data Normalization, Verification, and Rendering Architecture](#146-results-workspace-data-normalization-verification-and-rendering-architecture)
  - [14.7 Implementation Blueprint: Object-Oriented and Functional Software Architecture](#147-implementation-blueprint-object-oriented-and-functional-software-architecture)
- [15. References and Computational Index](#15-references-and-computational-index)

---

## 1. Mathematical Conventions and Tensor Notation

Throughout this monograph, boldface lowercase letters ($\mathbf{v}, \mathbf{x}, \mathbf{j}, \mathbf{q}$) denote first-order spatial vectors in $\mathbb{R}^3$, boldface uppercase letters ($\boldsymbol{\sigma}, \boldsymbol{\tau}, \mathbf{I}, \mathbf{D}$) denote second-order Cartesian tensors in $\mathbb{R}^{3 \times 3}$, calligraphic capital letters ($\mathcal{D}, \mathcal{P}, \mathcal{E}$) denote mathematical sets or high-order operators, and italicized Latin and Greek letters ($P, T, \rho, u, h, s, \mu, \gamma$) denote scalar fields.

### Tensor Operations
Let $\mathbf{a}, \mathbf{b} \in \mathbb{R}^3$ and $\mathbf{A}, \mathbf{B} \in \mathbb{R}^{3 \times 3}$.
* **Inner (scalar) product of vectors:**
  $$\mathbf{a} \cdot \mathbf{b} = \sum_{i=1}^3 a_i b_i$$
* **Dyadic (tensor) product:**
  $$(\mathbf{a} \otimes \mathbf{b})_{ij} = a_i b_j$$
* **Vector cross product:**
  $$(\mathbf{a} \times \mathbf{b})_i = \sum_{j=1}^3 \sum_{k=1}^3 \epsilon_{ijk} a_j b_k$$
  where $\epsilon_{ijk}$ is the completely antisymmetric Levi-Civita permutation symbol:
  $$\epsilon_{ijk} = \begin{cases} +1 & \text{if } (i, j, k) \text{ is an even permutation of } (1, 2, 3) \\ -1 & \text{if } (i, j, k) \text{ is an odd permutation of } (1, 2, 3) \\ 0 & \text{if any index repeats} \end{cases}$$
* **Double contraction of tensors:**
  $$\mathbf{A} : \mathbf{B} = \operatorname{tr}(\mathbf{A}^T \mathbf{B}) = \sum_{i=1}^3 \sum_{j=1}^3 A_{ij} B_{ij}$$
* **Nabla operator in Cartesian coordinates:**
  $$\nabla = \sum_{i=1}^3 \mathbf{e}_i \frac{\partial}{\partial x_i}$$
* **Gradient of a vector field:**
  $$(\nabla \mathbf{v})_{ij} = \frac{\partial v_j}{\partial x_i}$$
* **Divergence of a vector field:**
  $$\nabla \cdot \mathbf{v} = \sum_{i=1}^3 \frac{\partial v_i}{\partial x_i}$$
* **Divergence of a second-order tensor:**
  $$(\nabla \cdot \mathbf{A})_i = \sum_{j=1}^3 \frac{\partial A_{ji}}{\partial x_j}$$
* **Material (substantial) derivative:**
  $$\frac{D\phi}{Dt} = \frac{\partial \phi}{\partial t} + \mathbf{v} \cdot \nabla \phi$$
* **Jump operator across an interface $\Gamma$:**
  $$[\![\psi]\!] = \psi^+ - \psi^-$$
  where $\psi^+$ and $\psi^-$ denote the limiting values of field $\psi$ approaching $\Gamma$ from the positive and negative normal directions, respectively.

---

## 2. Continuum Mechanics and Transport Laws

The simulation engine treats physical systems as continuum thermodynamic bodies interacting through mass, momentum, and energy exchange across well-defined geometrical boundaries.

### 2.1 Multi-Component Species Mass Conservation

Consider an open spatial domain $\Omega \subset \mathbb{R}^3$ containing $N_c$ distinct chemical species. Each species $i \in \{1, \dots, N_c\}$ possesses a local mass concentration $\rho_i(\mathbf{x}, t) \ge 0$ ($[\text{kg/m}^3]$) and an individual velocity field $\mathbf{v}_i(\mathbf{x}, t)$ ($[\text{m/s}]$).

The total mixture mass density is defined by the sum of individual species concentrations:
$$\rho(\mathbf{x}, t) = \sum_{i=1}^{N_c} \rho_i(\mathbf{x}, t)$$

The barycentric (mass-averaged) mixture velocity is defined as:
$$\mathbf{v}(\mathbf{x}, t) = \frac{1}{\rho(\mathbf{x}, t)} \sum_{i=1}^{N_c} \rho_i(\mathbf{x}, t) \mathbf{v}_i(\mathbf{x}, t)$$

The mass fraction of species $i$ is $w_i = \rho_i / \rho$, satisfying $\sum_{i=1}^{N_c} w_i = 1$. The molar concentration is $c_i = \rho_i / M_i$, total molar concentration is $c_{\text{tot}} = \sum_{i=1}^{N_c} c_i$, and the mole fraction is $x_i = c_i / c_{\text{tot}}$, satisfying $\sum_{i=1}^{N_c} x_i = 1$.

#### Species Diffusion Fluxes
The diffusive mass flux $\mathbf{j}_i$ of species $i$ relative to the barycentric reference frame is defined by:
$$\mathbf{j}_i = \rho_i (\mathbf{v}_i - \mathbf{v})$$

By summing over all species, the diffusive mass fluxes satisfy the strict algebraic closure:
$$\sum_{i=1}^{N_c} \mathbf{j}_i = \sum_{i=1}^{N_c} \rho_i (\mathbf{v}_i - \mathbf{v}) = \sum_{i=1}^{N_c} \rho_i \mathbf{v}_i - \mathbf{v} \sum_{i=1}^{N_c} \rho_i = \rho \mathbf{v} - \rho \mathbf{v} = \mathbf{0}$$

#### Eulerian Differential Species Balance
Applying Reynolds' transport formulation to an arbitrary fixed control volume $V \subset \Omega$, the local Eulerian conservation law is:
$$\frac{\partial \rho_i}{\partial t} + \nabla \cdot \left( \rho_i \mathbf{v} + \mathbf{j}_i \right) = r_i, \quad i = 1, \dots, N_c$$
where $r_i(\mathbf{x}, t)$ is the net rate of mass generation of species $i$ per unit volume via $N_{\text{rxn}}$ homogeneous chemical reactions:
$$r_i = M_i \sum_{k=1}^{N_{\text{rxn}}} \nu_{ik} \hat{r}_k$$
Here $M_i$ is the molar mass of species $i$ ($[\text{kg/mol}]$), $\nu_{ik}$ is the stoichiometric coefficient of species $i$ in reaction $k$ (positive for products, negative for reactants), and $\hat{r}_k$ is the intensive reaction rate ($[\text{mol}/(\text{m}^3\cdot\text{s})]$).

By the principle of conservation of atomic nuclei during chemical transformations:
$$\sum_{i=1}^{N_c} \nu_{ik} M_i = 0, \quad \forall k \in \{1, \dots, N_{\text{rxn}}\}$$
Consequently, the net chemical mass generation summed across all species vanishes identically:
$$\sum_{i=1}^{N_c} r_i = \sum_{k=1}^{N_{\text{rxn}}} \hat{r}_k \sum_{i=1}^{N_c} \nu_{ik} M_i = 0$$

Summing the species equations over all $i = 1, \dots, N_c$:
$$\sum_{i=1}^{N_c} \frac{\partial \rho_i}{\partial t} + \nabla \cdot \left( \sum_{i=1}^{N_c} \rho_i \mathbf{v} + \sum_{i=1}^{N_c} \mathbf{j}_i \right) = \sum_{i=1}^{N_c} r_i$$
Using $\sum_i \rho_i = \rho$, $\sum_i \mathbf{j}_i = \mathbf{0}$, and $\sum_i r_i = 0$, we recover the **continuity equation for total mass**:
$$\frac{\partial \rho}{\partial t} + \nabla \cdot (\rho \mathbf{v}) = 0 \iff \frac{D\rho}{Dt} + \rho (\nabla \cdot \mathbf{v}) = 0$$

---

### 2.2 Multicomponent Diffusion: Stefan-Maxwell vs. Fickian Diffusion

In multi-component gas and liquid mixtures, molecular transport is governed by chemical potential gradients. The generalized **Stefan-Maxwell equations** relate molar diffusive fluxes $\mathbf{J}_i = c_i (\mathbf{v}_i - \mathbf{v})$ to thermodynamic driving forces $\mathbf{d}_i$:
$$\mathbf{d}_i = \sum_{j=1}^{N_c} \frac{x_i \mathbf{J}_j - x_j \mathbf{J}_i}{c_{\text{tot}} \mathcal{D}_{ij}}$$
where $\mathcal{D}_{ij}$ is the binary Stefan-Maxwell Maxwell-Stefan diffusion coefficient ($\mathcal{D}_{ij} = \mathcal{D}_{ji} > 0$), and $\mathbf{d}_i$ is the generalized chemical affinity driving force:
$$\mathbf{d}_i = \frac{x_i}{RT} \nabla_T \mu_i + \frac{\phi_i - w_i}{P} \nabla P - \frac{\rho_i}{P} \left( \mathbf{g}_i - \sum_{k=1}^{N_c} w_k \mathbf{g}_k \right)$$
Under isothermal, isobaric conditions without external body force differentiation, $\mathbf{d}_i$ reduces to the chemical potential gradient:
$$\mathbf{d}_i = \frac{x_i}{RT} \sum_{j=1}^{N_c-1} \Gamma_{ij} \nabla x_j, \quad \Gamma_{ij} = \delta_{ij} + x_i \frac{\partial \ln \gamma_i}{\partial x_j}$$
where $\boldsymbol{\Gamma}$ is the thermodynamic matrix of activity corrections.

#### The Fickian Approximation
When the mixture is dilute in species $i$ (or for binary systems), the Stefan-Maxwell relations collapse to Fick's first law:
$$\mathbf{j}_i = -\rho D_{i, m} \nabla w_i$$
where $D_{i, m}$ is the effective mixture diffusion coefficient. In concentrated multicomponent systems, Fick's law fails to describe reverse diffusion (diffusion against the concentration gradient), osmotic diffusion, and diffusion barriers ($\nabla x_i \ne 0$ with $\mathbf{J}_i = 0$), all of which are properly captured by the Stefan-Maxwell formulation.

---

### 2.3 Linear and Angular Momentum Conservation

#### Linear Momentum (Cauchy's Equation of Motion)
The conservation of linear momentum for an arbitrary continuum element states that the time rate of change of momentum equals the resultant of all surface forces and body forces acting on it:
$$\frac{\partial (\rho \mathbf{v})}{\partial t} + \nabla \cdot (\rho \mathbf{v} \otimes \mathbf{v}) = \nabla \cdot \boldsymbol{\sigma} + \rho \mathbf{g}$$
where:
* $\rho \mathbf{v} \otimes \mathbf{v}$ is the convective momentum flux tensor with components $(\rho \mathbf{v} \otimes \mathbf{v})_{ij} = \rho v_i v_j$.
* $\boldsymbol{\sigma}$ is the second-order Cauchy stress tensor ($[\text{N/m}^2]$).
* $\rho \mathbf{g}$ is the external gravitational body force field per unit volume.

Expanding the left-hand side using the mass continuity equation:
$$\frac{\partial (\rho \mathbf{v})}{\partial t} + \nabla \cdot (\rho \mathbf{v} \otimes \mathbf{v}) = \rho \left( \frac{\partial \mathbf{v}}{\partial t} + \mathbf{v} \cdot \nabla \mathbf{v} \right) + \mathbf{v} \left( \frac{\partial \rho}{\partial t} + \nabla \cdot (\rho \mathbf{v}) \right) = \rho \frac{D\mathbf{v}}{Dt}$$
This yields the non-conservative Lagrangian form of Cauchy's momentum equation:
$$\rho \frac{D\mathbf{v}}{Dt} = \nabla \cdot \boldsymbol{\sigma} + \rho \mathbf{g}$$

#### Conservation of Angular Momentum and Stress Symmetry
Taking the cross product of the position vector $\mathbf{r}$ with the linear momentum equation and integrating over an arbitrary volume $V$:
$$\frac{d}{dt} \int_V \rho (\mathbf{r} \times \mathbf{v}) \, dV = \oint_{\partial V} \mathbf{r} \times (\boldsymbol{\sigma} \cdot \mathbf{n}) \, dA + \int_V \rho (\mathbf{r} \times \mathbf{g}) \, dV + \int_V \rho \mathbf{m}_b \, dV$$
where $\mathbf{m}_b$ is an intrinsic body couple per unit mass. In non-polar classical fluids (absence of internal spin or magnetic couple stresses), the balance of angular momentum requires that the Cauchy stress tensor be symmetric:
$$\boldsymbol{\sigma} = \boldsymbol{\sigma}^T \iff \sigma_{ij} = \sigma_{ji}, \quad \forall i, j \in \{1, 2, 3\}$$

---

### 2.4 Constitutive Rheology: Newtonian and Non-Newtonian Fluids

Under the Stokesian fluid hypothesis, the stress tensor is partitioned into the isotropic thermodynamic pressure $P(\mathbf{x}, t)$ and the deviatoric viscous stress tensor $\boldsymbol{\tau}$:
$$\boldsymbol{\sigma} = -P \mathbf{I} + \boldsymbol{\tau}$$

#### 1. Isotropic Newtonian Fluid
For a linear isotropic Newtonian fluid, $\boldsymbol{\tau}$ is proportional to the symmetric rate-of-strain tensor $\mathbf{D}$:
$$\mathbf{D} = \frac{1}{2} \left( \nabla \mathbf{v} + (\nabla \mathbf{v})^T \right), \quad D_{ij} = \frac{1}{2}\left( \frac{\partial v_i}{\partial x_j} + \frac{\partial v_j}{\partial x_i} \right)$$
The general linear constitutive relation is:
$$\boldsymbol{\tau} = 2\mu \mathbf{D} + \lambda_v (\nabla \cdot \mathbf{v}) \mathbf{I} = 2\mu \left( \mathbf{D} - \frac{1}{3}(\nabla \cdot \mathbf{v})\mathbf{I} \right) + \zeta (\nabla \cdot \mathbf{v})\mathbf{I}$$
where $\mu$ is dynamic shear viscosity ($[\text{Pa}\cdot\text{s}]$), $\lambda_v$ is the second coefficient of viscosity, and $\zeta = \lambda_v + \frac{2}{3}\mu$ is bulk (volume) viscosity. Under **Stokes' hypothesis** for low-density monoatomic gases, $\zeta = 0 \implies \lambda_v = -\frac{2}{3}\mu$.

Substituting this constitutive relation into Cauchy's law yields the complete **Navier-Stokes equation**:
$$\rho \frac{D\mathbf{v}}{Dt} = -\nabla P + \mu \nabla^2 \mathbf{v} + \frac{\mu}{3} \nabla (\nabla \cdot \mathbf{v}) + (\nabla \mathbf{v} + (\nabla \mathbf{v})^T) \cdot \nabla \mu + \rho \mathbf{g}$$
For incompressible fluids with uniform viscosity ($\nabla \cdot \mathbf{v} = 0$, $\nabla \mu = \mathbf{0}$):
$$\rho \left( \frac{\partial \mathbf{v}}{\partial t} + \mathbf{v} \cdot \nabla \mathbf{v} \right) = -\nabla P + \mu \nabla^2 \mathbf{v} + \rho \mathbf{g}$$

#### 2. Non-Newtonian Rheological Models
For polymer solutions, slurries, and biological fluids:
* **Ostwald-de Waele (Power-Law) Fluid:**
  $$\boldsymbol{\tau} = 2 K |\dot{\gamma}|^{n-1} \mathbf{D}, \quad |\dot{\gamma}| = \sqrt{2 \mathbf{D} : \mathbf{D}}$$
  where $K$ is the flow consistency index and $n$ is the flow behavior index ($n < 1$: pseudoplastic / shear-thinning; $n > 1$: dilatant / shear-thickening).
* **Bingham Plastic (Yield-Stress Fluid):**
  $$\begin{cases} \mathbf{D} = \mathbf{0}, & |\boldsymbol{\tau}| \le \tau_y \\ \boldsymbol{\tau} = 2 \left( \mu_p + \frac{\tau_y}{|\dot{\gamma}|} \right) \mathbf{D}, & |\boldsymbol{\tau}| > \tau_y \end{cases}$$
  where $\tau_y$ is the yield stress and $\mu_p$ is plastic viscosity.

---

### 2.5 Total Energy and Internal Energy Conservation

#### Total Specific Energy Equation
Let $e_t$ be the total specific energy per unit mass:
$$e_t = u + \frac{1}{2} |\mathbf{v}|^2 + \psi$$
where $u$ is specific internal energy, $\frac{1}{2}|\mathbf{v}|^2 = \frac{1}{2}\mathbf{v}\cdot\mathbf{v}$ is specific kinetic energy, and $\psi(\mathbf{x})$ is specific gravitational potential energy defined such that $\mathbf{g} = -\nabla \psi$.

The Eulerian conservation law for total energy is:
$$\frac{\partial (\rho e_t)}{\partial t} + \nabla \cdot \left( \rho e_t \mathbf{v} + \mathbf{q} - \boldsymbol{\sigma} \cdot \mathbf{v} \right) = \dot{Q}_V$$
where $\mathbf{q}$ is the conductive and diffusive heat flux vector ($[\text{W/m}^2]$), $\boldsymbol{\sigma} \cdot \mathbf{v}$ is the mechanical surface work rate vector:
$$\boldsymbol{\sigma} \cdot \mathbf{v} = (-P \mathbf{I} + \boldsymbol{\tau}) \cdot \mathbf{v} = -P \mathbf{v} + \boldsymbol{\tau} \cdot \mathbf{v}$$
and $\dot{Q}_V$ is volumetric heat generation (radiation, electromagnetic dissipation).

#### Mechanical Energy Theorem
Taking the inner product of velocity $\mathbf{v}$ with Cauchy's linear momentum equation:
$$\rho \mathbf{v} \cdot \frac{D\mathbf{v}}{Dt} = \mathbf{v} \cdot (\nabla \cdot \boldsymbol{\sigma}) + \rho \mathbf{v} \cdot \mathbf{g}$$
Using $\mathbf{v} \cdot \frac{D\mathbf{v}}{Dt} = \frac{D}{Dt}\left( \frac{1}{2}|\mathbf{v}|^2 \right)$ and $\rho \mathbf{v} \cdot \mathbf{g} = -\rho \mathbf{v} \cdot \nabla \psi = -\rho \frac{D\psi}{Dt}$ (for steady gravity $\frac{\partial \psi}{\partial t} = 0$):
$$\rho \frac{D}{Dt}\left( \frac{1}{2}|\mathbf{v}|^2 + \psi \right) = \mathbf{v} \cdot (\nabla \cdot \boldsymbol{\sigma})$$
Expanding the tensor divergence product:
$$\nabla \cdot (\boldsymbol{\sigma} \cdot \mathbf{v}) = \mathbf{v} \cdot (\nabla \cdot \boldsymbol{\sigma}) + \boldsymbol{\sigma} : \nabla \mathbf{v}$$
Therefore:
$$\rho \frac{D}{Dt}\left( \frac{1}{2}|\mathbf{v}|^2 + \psi \right) = \nabla \cdot (\boldsymbol{\sigma} \cdot \mathbf{v}) - \boldsymbol{\sigma} : \nabla \mathbf{v}$$

#### Internal Energy Balance (Thermal Energy Equation)
Subtracting the mechanical energy equation from the total energy equation yields:
$$\rho \frac{Du}{Dt} = \boldsymbol{\sigma} : \nabla \mathbf{v} - \nabla \cdot \mathbf{q} + \dot{Q}_V$$
Substituting $\boldsymbol{\sigma} = -P \mathbf{I} + \boldsymbol{\tau}$:
$$\boldsymbol{\sigma} : \nabla \mathbf{v} = (-P \mathbf{I} + \boldsymbol{\tau}) : \nabla \mathbf{v} = -P (\nabla \cdot \mathbf{v}) + \boldsymbol{\tau} : \nabla \mathbf{v}$$
Defining the **viscous dissipation function** $\Phi_{\text{diss}} = \boldsymbol{\tau} : \nabla \mathbf{v} \ge 0$:
$$\Phi_{\text{diss}} = 2\mu \left( \mathbf{D} - \frac{1}{3}(\nabla \cdot \mathbf{v})\mathbf{I} \right) : \left( \mathbf{D} - \frac{1}{3}(\nabla \cdot \mathbf{v})\mathbf{I} \right) + \zeta (\nabla \cdot \mathbf{v})^2 \ge 0$$
The exact differential equation for internal energy is:
$$\rho \frac{Du}{Dt} = -P (\nabla \cdot \mathbf{v}) + \Phi_{\text{diss}} - \nabla \cdot \mathbf{q} + \dot{Q}_V$$

#### Constitutive Heat Flux: Fourier's Law with Multi-Component Enthalpy Diffusion
The heat flux vector $\mathbf{q}$ accounts for molecular conduction and interdiffusional enthalpy transport:
$$\mathbf{q} = -k \nabla T + \sum_{i=1}^{N_c} h_i \mathbf{j}_i + \mathbf{q}_{\text{Dufour}}$$
where $k$ is thermal conductivity ($[\text{W}/(\text{m}\cdot\text{K})]$), $h_i$ is the partial specific enthalpy of species $i$, and $\mathbf{q}_{\text{Dufour}}$ is the Dufour diffusion-thermo effect (neglected in industrial chemical processes).

---

### 2.6 Reynolds Transport Theorem on Arbitrary Deforming Volumes

To transition rigorously from differential field equations to macroscopic control volumes, we formulate the Reynolds Transport Theorem (RTT) for an arbitrary time-dependent volume $\Omega(t) \subset \mathbb{R}^3$ bounded by surface $\partial \Omega(t)$ moving with surface velocity $\mathbf{w}_b(\mathbf{x}, t)$.

```
                      ∂Ω(t) with surface velocity w_b
                    ╭──────────────────────────╮
                    │                          │
                    │         Ω(t)             │   Fluid velocity: v
                    │                          │   Relative velocity: v_r = v - w_b
                    │     ∫_Ω(t) ϕ dV          │   Outward normal: n
                    │                          │
                    ╰──────────────────────────╯
                                   ▲
                                   │ Flux: ϕ (v - w_b) · n dA
```

Let $\phi(\mathbf{x}, t)$ be an arbitrary continuously differentiable scalar or tensor field per unit volume.

#### Formal Derivation via Flow Mapping
Let $\boldsymbol{\xi} \in \Omega_0$ be reference coordinates at $t = 0$. The deforming domain is mapped by the diffeomorphism $\mathbf{x} = \boldsymbol{\chi}(\boldsymbol{\xi}, t)$ such that the boundary velocity is $\mathbf{w}_b = \left. \frac{\partial \boldsymbol{\chi}}{\partial t} \right|_{\boldsymbol{\xi}}$.
The Jacobian determinant of this transformation is $J(\boldsymbol{\xi}, t) = \det\left( \frac{\partial \boldsymbol{\chi}}{\partial \boldsymbol{\xi}} \right)$.

By change of variables:
$$\frac{d}{dt} \int_{\Omega(t)} \phi(\mathbf{x}, t) \, dV_{\mathbf{x}} = \frac{d}{dt} \int_{\Omega_0} \phi(\boldsymbol{\chi}(\boldsymbol{\xi}, t), t) J(\boldsymbol{\xi}, t) \, dV_{\boldsymbol{\xi}}$$
Differentiating under the integral sign:
$$\frac{d}{dt} \int_{\Omega(t)} \phi \, dV = \int_{\Omega_0} \left[ \frac{\partial \phi}{\partial t} J + (\nabla \phi \cdot \mathbf{w}_b) J + \phi \frac{\partial J}{\partial t} \right] dV_{\boldsymbol{\xi}}$$
Using Euler's expansion formula for the Jacobian determinant:
$$\frac{\partial J}{\partial t} = J (\nabla \cdot \mathbf{w}_b)$$
Substituting:
$$\frac{d}{dt} \int_{\Omega(t)} \phi \, dV = \int_{\Omega(t)} \left[ \frac{\partial \phi}{\partial t} + \nabla \phi \cdot \mathbf{w}_b + \phi (\nabla \cdot \mathbf{w}_b) \right] dV = \int_{\Omega(t)} \left[ \frac{\partial \phi}{\partial t} + \nabla \cdot (\phi \mathbf{w}_b) \right] dV$$
Applying Gauss' Divergence Theorem to the second term:
$$\frac{d}{dt} \int_{\Omega(t)} \phi \, dV = \int_{\Omega(t)} \frac{\partial \phi}{\partial t} \, dV + \oint_{\partial \Omega(t)} \phi (\mathbf{w}_b \cdot \mathbf{n}) \, dA$$

#### RTT for a General Local Conservation Law
Consider a continuum conservation law for property $\phi$ with flux tensor $\mathbf{\Phi}$ and volumetric source $s$:
$$\frac{\partial \phi}{\partial t} + \nabla \cdot (\phi \mathbf{v} + \mathbf{\Phi}) = s$$
Integrating over $\Omega(t)$:
$$\int_{\Omega(t)} \frac{\partial \phi}{\partial t} \, dV = -\int_{\Omega(t)} \nabla \cdot (\phi \mathbf{v} + \mathbf{\Phi}) \, dV + \int_{\Omega(t)} s \, dV = -\oint_{\partial \Omega(t)} (\phi \mathbf{v} + \mathbf{\Phi}) \cdot \mathbf{n} \, dA + \int_{\Omega(t)} s \, dV$$
Substituting this into the Leibniz-Reynolds formula:
$$\frac{d}{dt} \int_{\Omega(t)} \phi \, dV = \int_{\Omega(t)} s \, dV - \oint_{\partial \Omega(t)} \mathbf{\Phi} \cdot \mathbf{n} \, dA - \oint_{\partial \Omega(t)} \phi \left( (\mathbf{v} - \mathbf{w}_b) \cdot \mathbf{n} \right) dA$$
Defining the **relative velocity vector**:
$$\mathbf{v}_r = \mathbf{v} - \mathbf{w}_b$$
we obtain the canonical macroscopic balance equation on deforming volumes:
$$\frac{d}{dt} \int_{\Omega(t)} \phi \, dV + \oint_{\partial \Omega(t)} \phi (\mathbf{v}_r \cdot \mathbf{n}) \, dA = -\oint_{\partial \Omega(t)} \mathbf{\Phi} \cdot \mathbf{n} \, dA + \int_{\Omega(t)} s \, dV$$

---

### 2.7 Interphase Jump Conditions and Boundary Interfaces

At a singular moving interface $\Gamma(t)$ separating two immiscible bulk phases (liquid-vapor or liquid-liquid) with normal speed $w_n = \mathbf{w}_{\Gamma} \cdot \mathbf{n}$:
1. **Mass jump condition:**
   $$[\![\rho (\mathbf{v} - \mathbf{w}_\Gamma) \cdot \mathbf{n}]\!] = 0 \iff \dot{m}'' = \rho^+ (\mathbf{v}^+ - \mathbf{w}_\Gamma) \cdot \mathbf{n} = \rho^- (\mathbf{v}^- - \mathbf{w}_\Gamma) \cdot \mathbf{n}$$
   where $\dot{m}''$ is the net rate of interphase mass transfer (phase change evaporation/condensation) per unit interface area ($[\text{kg}/(\text{m}^2\cdot\text{s})]$).
2. **Momentum jump condition (Young-Laplace with Marangoni stress):**
   $$[\![\rho \mathbf{v} \otimes (\mathbf{v} - \mathbf{w}_\Gamma) - \boldsymbol{\sigma}]\!] \cdot \mathbf{n} = \nabla_s \sigma - 2 H \sigma \mathbf{n}$$
   where $\sigma$ is surface tension ($[\text{N/m}]$), $H = -\frac{1}{2}\nabla_s \cdot \mathbf{n}$ is the mean curvature of the interface, and $\nabla_s = (\mathbf{I} - \mathbf{n}\otimes\mathbf{n}) \cdot \nabla$ is the surface gradient operator. When fluid velocities are small:
   $$P^- - P^+ = 2 H \sigma \quad (\text{Young-Laplace equation})$$
3. **Energy jump condition:**
   $$[\![\rho e_t (\mathbf{v} - \mathbf{w}_\Gamma) \cdot \mathbf{n} + \mathbf{q} \cdot \mathbf{n} - (\boldsymbol{\sigma} \cdot \mathbf{v}) \cdot \mathbf{n}]\!] = \dot{m}'' \Delta h_{\text{vap}} + \nabla_s \cdot \mathbf{q}_s$$

---

### 2.8 Macroscopic Control Volume Lumped Balances

By decomposing the boundary $\partial \Omega_v(t)$ of an engineering volume $v$ into discrete flow ports $A_s$ (inlets and outlets) and closed walls $\partial \Omega_{\text{wall}}(t)$:

#### 1. Macroscopic Species Mass Balance
$$\frac{dn_{i, v}}{dt} = \sum_{s} B_{vs} \dot{n}_s x_{si} + \sum_{k=1}^{N_{\text{rxn}}} \nu_{ik} r_{k, v} V_v + \dot{N}_{i, v}^{\text{interphase}}$$
where:
* $n_{i, v} = \int_{\Omega_v} c_i \, dV$ is the total molar inventory of species $i$ in volume $v$ ($[\text{mol}]$).
* $B_{vs}$ is the directed topological incidence matrix element connecting port $s$ to volume $v$:
  $$B_{vs} = \begin{cases} +1 & \text{if stream } s \text{ enters volume } v \\ -1 & \text{if stream } s \text{ leaves volume } v \\ 0 & \text{if stream } s \text{ is not connected to } v \end{cases}$$
* $\dot{n}_s = \oint_{A_s} c (\mathbf{v} \cdot \mathbf{n}) dA$ is the total molar flow rate of stream $s$ ($[\text{mol/s}]$).
* $x_{si}$ is the mole fraction of species $i$ in stream $s$.
* $\dot{N}_{i, v}^{\text{interphase}}$ is the rate of interphase mass transfer across internal phase interfaces.

#### 2. Macroscopic Total Energy Balance (Variable Volume and Prescribed Pressure)
Substituting specific total energy $\phi = \rho e_t$:
$$\frac{d}{dt} \int_{\Omega(t)} \rho e_t \, dV + \oint_{\partial \Omega(t)} \rho e_t (\mathbf{v}_r \cdot \mathbf{n}) \, dA = -\oint_{\partial \Omega(t)} \mathbf{q} \cdot \mathbf{n} \, dA + \oint_{\partial \Omega(t)} (\boldsymbol{\sigma} \cdot \mathbf{v}) \cdot \mathbf{n} \, dA + \int_{\Omega(t)} \dot{Q}_V \, dV$$
Neglecting kinetic and gravitational potential energy storage ($\frac{1}{2}|\mathbf{v}|^2 \ll u$, $\Delta \psi \ll u$), total stored energy equals internal energy $U_v(t) = \int_{\Omega_v(t)} \rho u \, dV$.

Decomposing the surface work:
1. **At flow ports $A_s$:** Boundary is fixed ($\mathbf{w}_b = \mathbf{0} \implies \mathbf{v}_r = \mathbf{v}$). The convective term combined with normal pressure work gives:
   $$\rho u (\mathbf{v} \cdot \mathbf{n}) + P (\mathbf{v} \cdot \mathbf{n}) = \rho \left( u + \frac{P}{\rho} \right) (\mathbf{v} \cdot \mathbf{n}) = \rho h (\mathbf{v} \cdot \mathbf{n})$$
   where $h = u + P v$ is the specific enthalpy of the flowing fluid stream.
2. **At moving mechanical boundaries $\partial \Omega_{\text{mech}}(t)$:** Fluid adheres to the wall ($\mathbf{v}_r \cdot \mathbf{n} = 0$). Convective flux is zero, and normal pressure work produces boundary displacement work:
   $$\oint_{\partial \Omega_{\text{mech}}} (-P \mathbf{v}) \cdot \mathbf{n} \, dA = -P_v \oint_{\partial \Omega_{\text{mech}}} \mathbf{w}_b \cdot \mathbf{n} \, dA = -P_v \frac{dV_v}{dt}$$
3. **At rotating shafts crossing the boundary:** Viscous shear produces shaft work $\dot{W}_{s, v}$.
4. **Net external heat transfer:** $\dot{Q}_v = -\oint \mathbf{q} \cdot \mathbf{n} \, dA + \int \dot{Q}_V \, dV$.

This yields the canonical **First Law of Thermodynamics for open, moving-boundary control volumes**:
$$\frac{dU_v}{dt} = \sum_{s} B_{vs} \dot{n}_s h_s + \dot{Q}_v + \dot{W}_{s, v} - P_v \frac{dV_v}{dt}$$

#### Transformation to Prescribed-Pressure Enthalpy Form
When the vessel pressure is prescribed $P_v = P(t)$, the total enthalpy is $H_v(t) = U_v(t) + P_v(t) V_v(t)$. Differentiating with respect to time:
$$\frac{dH_v}{dt} = \frac{dU_v}{dt} + P_v \frac{dV_v}{dt} + V_v \frac{dP_v}{dt}$$
Substituting $\frac{dU_v}{dt}$:
$$\frac{dH_v}{dt} = \left( \sum_{s} B_{vs} \dot{n}_s h_s + \dot{Q}_v + \dot{W}_{s, v} - P_v \frac{dV_v}{dt} \right) + P_v \frac{dV_v}{dt} + V_v \frac{dP_v}{dt}$$
The displacement work terms $-P_v \frac{dV_v}{dt}$ and $+P_v \frac{dV_v}{dt}$ cancel algebraically, yielding:
$$\frac{dH_v}{dt} = \sum_{s} B_{vs} \dot{n}_s h_s + \dot{Q}_v + \dot{W}_{s, v} + V_v \frac{dP_v}{dt}$$
For isobaric processes ($\frac{dP_v}{dt} = 0$), this simplifies to $\frac{dH_v}{dt} = \sum B_{vs} \dot{n}_s h_s + \dot{Q}_v + \dot{W}_{s, v}$.

---

### 2.9 Momentum Reduction: Hydraulic Inertance and Turbomachinery

Following `core/balances/momentum_derivation.py`, the engine deduces reduced momentum equations from Cauchy's conservation equation through traceable physical reductions.

#### Straight Hydraulic Conduit (Fluid Inertance)
Consider fluid flow through a rigid pipe conduit of length $L$, uniform cross-sectional area $A$, and perimeter $\mathcal{P}_w$. Let $x \in [0, L]$ be the axial coordinate along the pipe centerline.

Integrating Cauchy's axial momentum equation over the conduit volume $V = A L$:
$$\int_0^L \int_A \left[ \frac{\partial (\rho v_x)}{\partial t} + \frac{\partial (\rho v_x^2)}{\partial x} + \frac{\partial P}{\partial x} - \frac{\partial \tau_{xx}}{\partial x} + \rho g \frac{dz}{dx} \right] dA \, dx = \int_0^L \oint_{\mathcal{P}_w} \tau_w \, d\mathcal{P} \, dx$$
Assuming:
1. Incompressible fluid with constant reference density $\rho = \rho_{\text{ref}}$.
2. Divergence-free velocity $\frac{\partial v_x}{\partial x} = 0 \implies v_x(x, t) = v(t) = \frac{\dot{m}(t)}{\rho_{\text{ref}} A}$.
3. Negligible axial viscous normal stress $\frac{\partial \tau_{xx}}{\partial x} \approx 0$.

The convective spatial derivative integrates to zero across uniform area:
$$\int_0^L \frac{\partial (\rho v^2)}{\partial x} dx = \left[ \rho v^2 \right]_1^2 = 0$$
The unsteady term integrates to:
$$\int_0^L A \rho_{\text{ref}} \frac{\partial v}{\partial t} \, dx = A \rho_{\text{ref}} L \frac{d}{dt}\left( \frac{\dot{m}}{\rho_{\text{ref}} A} \right) = L \frac{d\dot{m}}{dt}$$
The pressure gradient integrates to:
$$\int_0^L A \frac{\partial P}{\partial x} \, dx = A (P_2 - P_1)$$
The gravitational term integrates to:
$$\int_0^L \rho_{\text{ref}} g A \frac{dz}{dx} \, dx = \rho_{\text{ref}} g A (z_2 - z_1)$$
The wall shear stress integrates to the friction pressure drop:
$$\int_0^L \mathcal{P}_w \tau_w \, dx = A \Delta P_{\text{loss}}$$

Dividing through by cross-sectional area $A$:
$$\frac{L}{A} \frac{d\dot{m}}{dt} = P_1 - P_2 + \Delta P_{\text{drive}} - \Delta P_{\text{loss}} - \rho_{\text{ref}} g (z_2 - z_1)$$
Defining the **hydraulic inertance parameter**:
$$L_I = \frac{L}{A} \quad [\text{m}^{-1}]$$
we obtain the canonical hydraulic equation:
$$L_I \frac{d\dot{m}}{dt} = P_1 - P_2 + \Delta P_{\text{drive}} - \Delta P_{\text{loss}} - \rho_{\text{ref}} g (z_2 - z_1)$$

#### Turbomachinery: Euler Energy Equation
For rotating machinery (centrifugal pumps and turbines), taking the moment of momentum $\mathbf{r} \times \mathbf{v}$ yields the fluid torque $\tau_f$:
$$\tau_f = \dot{m} \left( r_2 c_{\theta 2} - r_1 c_{\theta 1} \right)$$
where $r_1, r_2$ are impeller inlet and outlet radii, and $c_{\theta 1}, c_{\theta 2}$ are tangential components of absolute velocity. Under zero inlet swirl ($c_{\theta 1} = 0$) and blade discharge angle $\beta_2$, Euler's pump equation gives specific mechanical energy transfer $Y_E$:
$$Y_E = \omega \frac{\tau_f}{\dot{m}} = \omega^2 r_2^2 - \frac{\omega Q \cot \beta_2}{2\pi b_2} \quad [\text{J/kg}]$$
where $\omega$ is rotational speed ($[\text{rad/s}]$), $Q = \dot{m}/\rho$ is volumetric flow rate, and $b_2$ is blade exit width.

The dynamic shaft balance is governed by:
$$J_{\text{rotor}} \frac{d\omega}{dt} = \tau_{\text{motor}} - \tau_f - \tau_{\text{friction}}$$

---

### 2.10 Friction Losses: Churchill and Colebrook-White Formulations

Friction pressure drop through conduits is modeled via the Darcy-Weisbach equation:
$$\Delta P_{\text{loss}} = \left( f_D \frac{L}{D_h} + \sum_{k} K_k \right) \frac{\dot{m} |\dot{m}|}{2 \rho_{\text{ref}} A^2}$$
where $f_D$ is the Darcy friction factor and $K_k$ are minor loss coefficients.

#### 1. Churchill (1977) Explicit Friction Formulation
To span laminar, critical transition, and fully turbulent regimes smoothly without numerical discontinuities, the engine incorporates Churchill's explicit equation:
$$f_D = 8 \left[ \left(\frac{8}{Re}\right)^{12} + \frac{1}{(A_{\text{ch}} + B_{\text{ch}})^{3/2}} \right]^{1/12}$$
where:
$$A_{\text{ch}} = \left[ 2.457 \ln \left( \frac{1}{(7/Re)^{0.9} + 0.27 (\epsilon/D)} \right) \right]^{16}$$
$$B_{\text{ch}} = \left( \frac{37530}{Re} \right)^{16}$$
In the laminar limit ($Re \to 0$): $f_D \to 64/Re$. In the fully rough turbulent limit ($Re \to \infty$): $f_D \to \frac{1}{[2 \log_{10}(3.7 D / \epsilon)]^2}$.

#### 2. Colebrook-White Formulation and Halley Third-Order Iteration
The implicit Colebrook-White equation for turbulent pipe flow is:
$$\mathcal{F}(f_D) = \frac{1}{\sqrt{f_D}} + 2.0 \log_{10}\left( \frac{\epsilon/D}{3.7} + \frac{2.51}{Re \sqrt{f_D}} \right) = 0$$
Letting $x = 1/\sqrt{f_D}$, the root $x^*$ is solved via Halley's third-order iteration:
$$x_{k+1} = x_k - \frac{2 \mathcal{F}(x_k) \mathcal{F}'(x_k)}{2 [\mathcal{F}'(x_k)]^2 - \mathcal{F}(x_k) \mathcal{F}''(x_k)}$$
converging to machine precision ($10^{-15}$) within two iterations from an explicit Churchill initialization.

---

### 2.11 Open Channel and Orifice Hydraulics: Francis Weir Formula

For dynamic liquid level overflow in distillation trays, phase separators, and decanters:
#### 1. Francis Rectangular Weir Formula
$$Q_{\text{weir}} = \frac{2}{3} C_d \sqrt{2g} \left( b - 0.1 n_c h_{\text{ow}} \right) h_{\text{ow}}^{3/2}$$
where $b$ is weir crest length ($[\text{m}]$), $h_{\text{ow}} = \max(0, h_{\text{liquid}} - h_{\text{weir}})$ is liquid crest head over weir, $n_c \in \{0, 1, 2\}$ is the number of end contractions, and $C_d \approx 0.62$ is the discharge coefficient.

#### 2. Control Valve Sizing
For liquid valve flow:
$$\dot{m} = N_v C_v f_{\text{valve}}(x_v) \sqrt{\Delta P \cdot \rho_{\text{fluid}}}$$
where $x_v \in [0, 1]$ is valve opening fraction, and $f_{\text{valve}}$ represents valve characteristic trim:
* Linear trim: $f_{\text{valve}}(x_v) = x_v$
* Equal percentage trim: $f_{\text{valve}}(x_v) = R^{x_v - 1}$ (with rangeability $R \approx 30 \text{--} 50$)
* Quick opening trim: $f_{\text{valve}}(x_v) = \sqrt{x_v}$

---

### 2.12 Compressible Conduit Flow: Sonic Choking and Critical Pressure Ratio

For high-velocity gas lines and relief valves, isentropic compressible nozzle flow relates upstream stagnation pressure $P_0$ and downstream backpressure $P_b$:
The critical pressure ratio for sonic choking ($Ma = 1$) is:
$$\left( \frac{P^*}{P_0} \right) = \left( \frac{2}{\gamma + 1} \right)^{\frac{\gamma}{\gamma - 1}}$$
where $\gamma = C_p / C_v$ is the isentropic expansion coefficient.
* **Subcritical regime ($P_b / P_0 > P^*/P_0$):**
  $$\dot{m} = A_{\text{throat}} \sqrt{2 \rho_0 P_0 \frac{\gamma}{\gamma - 1} \left[ \left(\frac{P_b}{P_0}\right)^{2/\gamma} - \left(\frac{P_b}{P_0}\right)^{(\gamma+1)/\gamma} \right]}$$
* **Choked regime ($P_b / P_0 \le P^*/P_0$):**
  $$\dot{m}_{\text{choked}} = A_{\text{throat}} \sqrt{\gamma \rho_0 P_0 \left( \frac{2}{\gamma + 1} \right)^{\frac{\gamma+1}{\gamma-1}}}$$
Flow becomes independent of downstream backpressure $P_b$.

---

### 2.13 Dynamic Inventory Retention Policy

In adherence to the **Dynamic Inventory Foundation** (`common-model.md §10`), active physical conservation laws must retain their differential balance form $\frac{dI}{dt} = \Phi(t, \mathbf{y})$.
When a user declares a fixed inventory $M(t) = M_0$:
* **Prohibited behavior:** Deleting the differential state variable $\frac{dM}{dt}$ or replacing the balance with $M = M_0$.
* **Mandated behavior:** Retaining the differential balance $\frac{dM}{dt} = \Phi(t, \mathbf{y})$ and adjoining two simultaneous algebraic compatibility constraints:
  $$M(t) - M_0 = 0, \quad \Phi(t, \mathbf{y}) = \sum \dot{m}_{\text{in}} - \sum \dot{m}_{\text{out}} = 0$$

---

## 3. Thermodynamic Equilibrium and Complementarity Layer

### 3.1 Variational Formulation of Phase Equilibrium

The equilibrium state of a closed multi-component, multiphase system at constant temperature $T$ and pressure $P$ minimizes the total Gibbs free energy $G$:
$$\min_{\{\mathbf{n}_k\}} G(\mathbf{n}_1, \dots, \mathbf{n}_{N_p}) = \sum_{k=1}^{N_p} \sum_{i=1}^{N_c} n_{ki} \mu_{ki}(T, P, \mathbf{x}_k)$$
subject to mass conservation and non-negativity:
$$\sum_{k=1}^{N_p} n_{ki} = n_i^{\text{total}}, \quad n_{ki} \ge 0, \quad \forall i \in \{1, \dots, N_c\}, \; k \in \{1, \dots, N_p\}$$

At isolated volume and internal energy $(U, V, \mathbf{n})$, equilibrium maximizes total entropy:
$$\max_{\{\mathbf{n}_k, U_k, V_k\}} S_{\text{total}} = \sum_{k=1}^{N_p} S_k(U_k, V_k, \mathbf{n}_k) \quad \text{s.t.} \quad \sum U_k = U, \; \sum V_k = V, \; \sum n_{ki} = n_i$$

---

### 3.2 Michelsen Tangent Plane Distance and Phase Stability Analysis

A single-phase mixture with feed composition $\mathbf{z} \in \Delta^{N_c-1}$ is stable if and only if the Gibbs energy surface lies entirely above its tangent plane evaluated at $\mathbf{z}$.

The dimensionless Tangent Plane Distance ($TPD$) function at trial composition $\mathbf{w} \in \Delta^{N_c-1}$ is defined by:
$$tm(\mathbf{w}) = \frac{TPD(\mathbf{w})}{RT} = \sum_{i=1}^{N_c} w_i \left[ \ln w_i + \ln \hat{\phi}_i(T, P, \mathbf{w}) - h_i \right]$$
where $h_i$ is the chemical potential coordinate of the feed:
$$h_i = \ln z_i + \ln \hat{\phi}_i(T, P, \mathbf{z})$$
Introducing unnormalized amounts $W_i = \alpha w_i$:
$$\ln W_i + \ln \hat{\phi}_i(\mathbf{W}) - h_i = 0, \quad i = 1, \dots, N_c$$
Stationary points are located using modified Newton-Raphson iteration. The phase $\mathbf{z}$ is stable if and only if:
$$tm(\mathbf{w}^*) \ge 0$$
for all stationary trial compositions $\mathbf{w}^*$.

---

### 3.3 Kuhn-Tucker Complementarity Conditions for Candidate Phases

To model phase transitions without conditional logic or event discontinuities, candidate phases $\mathcal{P} = \{V, L_1, L_2, S\}$ are represented using **Kuhn-Tucker complementarity conditions**.

Let $\beta_k = n_k / n_{\text{total}}$ be the mole fraction of phase $k$, and let $tm_k \ge 0$ be the non-negative tangent distance of phase $k$. The state satisfies:
$$\beta_k \ge 0, \quad tm_k \ge 0, \quad \beta_k \cdot tm_k = 0, \quad \forall k \in \mathcal{P}$$
subject to:
$$\sum_{k \in \mathcal{P}} \beta_k = 1, \quad \sum_{k \in \mathcal{P}} \beta_k x_{ki} = z_i, \quad \forall i \in \{1, \dots, N_c\}$$

```
          tm_k (Tangent Plane Distance)
           ▲
           │   Phase ABSENT:
           │   tm_k > 0,  β_k = 0
           │
           │
           │             Phase PRESENT:
           │             tm_k = 0,  β_k > 0
           └───────────────────────────► β_k (Phase Mole Fraction)
```

---

### 3.4 Semismooth Newton Solvers for Complementarity Systems

The complementarity problem $a \ge 0, b \ge 0, a b = 0$ is reformulated into an equivalent unconstrained non-smooth nonlinear equation using the **Fischer-Burmeister function**:
$$\Psi_{\text{FB}}(a, b) = a + b - \sqrt{a^2 + b^2} = 0$$
Lemma: $\Psi_{\text{FB}}(a, b) = 0 \iff a \ge 0, b \ge 0, ab = 0$.

The function $\Psi_{\text{FB}}$ is globally Lipschitz continuous and semismooth, allowing solution via the **Semismooth Newton Algorithm**:
$$\mathbf{J}_{\Psi}^{(m)} \Delta \mathbf{w}^{(m)} = -\mathbf{\Psi}(\mathbf{w}^{(m)})$$
where the generalized subdifferential Jacobian $\mathbf{J}_{\Psi} \in \partial_C \mathbf{\Psi}$ has elements:
$$\frac{\partial \Psi}{\partial a} = 1 - \frac{a}{\sqrt{a^2 + b^2}}, \quad \frac{\partial \Psi}{\partial b} = 1 - \frac{b}{\sqrt{a^2 + b^2}} \quad (\text{for } (a, b) \neq (0, 0))$$
and $[1 - \xi_1, 1 - \xi_2]$ with $\xi_1^2 + \xi_2^2 \le 1$ at $(0, 0)$. This formulation converges superlinearly across phase appearance and disappearance boundaries without combinatorial switching.

---

### 3.5 Multiphase Flash Algorithms (TP, UV, and PH Flashes)

1. **Isothermal-Isobaric ($TP$) Flash:**
   Solves $\mu_{1, i} = \dots = \mu_{N_p, i}$ via successive substitution and accelerated Newton-Raphson on independent log-amounts $\theta_{ki} = \ln n_{ki}$.
2. **Isochoric-Isoenergetic ($UV$) Flash:**
   Given specified $(U_v, V_v, \mathbf{n})$, solves for $(T, P)$ using Newton-Raphson with the exact analytical $2 \times 2$ thermodynamic Jacobian:
   $$\mathbf{J}_{\text{UV}} = \begin{bmatrix} \left(\frac{\partial U}{\partial T}\right)_V & \left(\frac{\partial U}{\partial P}\right)_T \\ \left(\frac{\partial V}{\partial T}\right)_P & \left(\frac{\partial V}{\partial P}\right)_T \end{bmatrix} = \begin{bmatrix} n C_v & -T V \alpha_P + P V \kappa_T \\ V \alpha_P & -V \kappa_T \end{bmatrix}$$
   where $\alpha_P = \frac{1}{V}\left(\frac{\partial V}{\partial T}\right)_P$ is thermal expansivity and $\kappa_T = -\frac{1}{V}\left(\frac{\partial V}{\partial P}\right)_T$ is isothermal compressibility.
3. **Isobaric-Isoenthalpic ($PH$) Flash:**
   Solves the energy residual $H_{\text{flash}}(T, P, \mathbf{n}) - H = 0$ via Brent-Dekker root finding, automatically handling the latent heat boiling plateau by resolving vapor fraction $\beta_V \in [0, 1]$ directly when $T = T_{\text{bubble}}(P)$.

---

### 3.6 Monotonic Step-Limiting for Rachford-Rice Objective Functions

For a two-phase vapor-liquid system, phase split $\beta = n_V / n_{\text{tot}}$ satisfies the Rachford-Rice equation:
$$F(\beta) = \sum_{i=1}^{N_c} \frac{z_i (K_i - 1)}{1 + \beta (K_i - 1)} = 0$$
where $K_i = y_i / x_i$ is the equilibrium ratio.

#### Mathematical Properties
1. **Strict Monotonicity:**
   $$F'(\beta) = -\sum_{i=1}^{N_c} \frac{z_i (K_i - 1)^2}{[1 + \beta (K_i - 1)]^2} < 0, \quad \forall \beta \in (\beta_{\min}, \beta_{\max})$$
   $F(\beta)$ is strictly monotonically decreasing, ensuring at most one unique physical root.
2. **Singular Asymptotes (Poles):**
   The domain of definition is bounded by the poles of the denominators:
   $$\beta_{\min} = \frac{1}{1 - K_{\max}} < 0, \quad \beta_{\max} = \frac{1}{1 - K_{\min}} > 1$$
   where $K_{\max} = \max_i K_i > 1$ and $K_{\min} = \min_i K_i < 1$.

#### Step-Limiting Protocol
To prevent standard Newton steps $\Delta \beta = -F(\beta_k) / F'(\beta_k)$ from stepping across poles into divergent regions, the step is restricted:
$$\beta_{k+1} = \beta_k + \alpha_k \Delta \beta$$
$$\alpha_k = \min\left( 1.0, \; 0.8 \frac{\beta_{\max} - \beta_k}{\Delta \beta} \text{ if } \Delta \beta > 0, \; 0.8 \frac{\beta_{\min} - \beta_k}{\Delta \beta} \text{ if } \Delta \beta < 0 \right)$$
guaranteeing unconditional global convergence.

---

### 3.7 Constitutive Equation of State: Pure Water via Full IAPWS-95 Formulation

Water properties are governed by the Helmholtz free energy formulation of Wagner and Pruss (IAPWS-95):
$$\frac{a(\rho, T)}{RT} = \phi(\delta, \tau) = \phi^0(\delta, \tau) + \phi^r(\delta, \tau)$$
where $\delta = \rho / \rho_c$ is reduced density ($\rho_c = 322.0\text{ kg/m}^3$), $\tau = T_c / T$ is inverse reduced temperature ($T_c = 647.096\text{ K}$), and $R = 0.46151805\text{ kJ}/(\text{kg}\cdot\text{K})$.

#### 1. Ideal Gas Contribution $\phi^0$
$$\phi^0(\delta, \tau) = \ln \delta + a_1^0 + a_2^0 \tau + a_3^0 \ln \tau + \sum_{i=4}^8 a_i^0 \ln\left[ 1 - \exp(-\theta_i^0 \tau) \right]$$

#### 2. Residual Contribution $\phi^r$ (56 Fundamental Terms)
$$\phi^r(\delta, \tau) = \sum_{i=1}^7 n_i \delta^{d_i} \tau^{t_i} + \sum_{i=8}^{51} n_i \delta^{d_i} \tau^{t_i} e^{-\delta^{c_i}} + \sum_{i=52}^{54} n_i \delta^{d_i} \tau^{t_i} e^{-\alpha_i (\delta - \epsilon_i)^2 - \beta_i (\tau - \gamma_i)^2} + \sum_{i=55}^{56} n_i \Delta_i^{b_i} \delta \psi_i$$
where $\Delta_i = (\theta_i + \Delta_i^*)^2 + \beta_i (\delta - 1)^2$ and $\psi_i = \exp(-C_i (\delta - 1)^2 - D_i (\tau - 1)^2)$.

#### 3. Complete State Thermodynamic Derivatives
All macroscopic physical quantities are exact partial derivatives of $\phi$:
* **Thermodynamic Pressure:**
  $$P(\rho, T) = \rho R T \left[ 1 + \delta \left(\frac{\partial \phi^r}{\partial \delta}\right)_\tau \right] = \rho R T (1 + \delta \phi_\delta^r)$$
* **Specific Internal Energy:**
  $$u(\rho, T) = R T \tau \left( \phi_\tau^0 + \phi_\tau^r \right)$$
* **Specific Enthalpy:**
  $$h(\rho, T) = u + \frac{P}{\rho} = R T \left[ 1 + \tau (\phi_\tau^0 + \phi_\tau^r) + \delta \phi_\delta^r \right]$$
* **Specific Entropy:**
  $$s(\rho, T) = R \left[ \tau (\phi_\tau^0 + \phi_\tau^r) - \phi^0 - \phi^r \right]$$
* **Isochoric Heat Capacity:**
  $$c_v(\rho, T) = -R \tau^2 \left( \phi_{\tau\tau}^0 + \phi_{\tau\tau}^r \right)$$
* **Isobaric Heat Capacity:**
  $$c_p(\rho, T) = c_v + R \frac{\left( 1 + \delta \phi_\delta^r - \delta \tau \phi_{\delta\tau}^r \right)^2}{1 + 2\delta \phi_\delta^r + \delta^2 \phi_{\delta\delta}^r}$$
* **Speed of Sound:**
  $$w(\rho, T) = \sqrt{\left(\frac{\partial P}{\partial \rho}\right)_s} = \sqrt{R T \left( 1 + 2\delta \phi_\delta^r + \delta^2 \phi_{\delta\delta}^r - \frac{(1 + \delta \phi_\delta^r - \delta \tau \phi_{\delta\tau}^r)^2}{\tau^2 (\phi_{\tau\tau}^0 + \phi_{\tau\tau}^r)} \right)}$$

---

### 3.8 Constitutive Liquid Activity: UNIFAC Group Contribution Models

Activity coefficients $\gamma_i$ for non-electrolyte liquid mixtures are calculated from molecular architecture via UNIFAC:
$$\ln \gamma_i = \ln \gamma_i^C + \ln \gamma_i^R$$

#### 1. Combinatorial Part (Staverman-Guggenheim)
Accounting for molecular size and shape differences:
$$\ln \gamma_i^C = \ln \left( \frac{\Phi_i}{x_i} \right) + \frac{z}{2} q_i \ln \left( \frac{\theta_i}{\Phi_i} \right) + l_i - \frac{\Phi_i}{x_i} \sum_{j=1}^{N_c} x_j l_j$$
where:
* Volume fraction: $\Phi_i = \frac{x_i r_i}{\sum_j x_j r_j}$, Area fraction: $\theta_i = \frac{x_i q_i}{\sum_j x_j q_j}$.
* Coordination number: $z = 10$.
* Bulky shape parameter: $l_i = \frac{z}{2}(r_i - q_i) - (r_i - 1)$.
* Pure component structural parameters:
  $$r_i = \sum_{k} \nu_k^{(i)} R_k, \quad q_i = \sum_{k} \nu_k^{(i)} Q_k$$
  where $\nu_k^{(i)}$ is the number of functional groups of type $k$ in molecule $i$, and $R_k, Q_k$ are group volume and area constants.

#### 2. Residual Part (Functional Group Energetic Interactions)
$$\ln \gamma_i^R = \sum_{k} \nu_k^{(i)} \left[ \ln \Gamma_k - \ln \Gamma_k^{(i)} \right]$$
where $\Gamma_k$ is the group activity coefficient in the actual mixture, and $\Gamma_k^{(i)}$ is the group activity coefficient in a reference mixture of pure component $i$:
$$\ln \Gamma_k = Q_k \left[ 1 - \ln \left( \sum_m \Theta_m \Psi_{mk} \right) - \sum_m \frac{\Theta_m \Psi_{km}}{\sum_n \Theta_n \Psi_{nm}} \right]$$
where:
* Group area fraction: $\Theta_m = \frac{Q_m X_m}{\sum_n Q_n X_n}$, with group mole fraction $X_m = \frac{\sum_j \nu_m^{(j)} x_j}{\sum_j \sum_n \nu_n^{(j)} x_j}$.
* Group interaction parameter: $\Psi_{mn} = \exp\left( -\frac{a_{mn}}{T} \right)$ with $a_{mn} \ne a_{nm}$.

#### Representative UNIFAC Parameters
| Main Group | Subgroup | $R_k$ | $Q_k$ | Interaction Partner | $a_{mn}$ [K] | $a_{nm}$ [K] |
|---|---|---|---|---|---|---|
| 1: $\text{CH}_2$ | $\text{CH}_3$ | 0.9011 | 0.848 | $\text{H}_2\text{O}$ | 1318.0 | 300.0 |
| 1: $\text{CH}_2$ | $\text{CH}_2$ | 0.6744 | 0.540 | $\text{OH}$ | 986.5 | 156.4 |
| 5: $\text{OH}$ | $\text{OH}$ | 1.0000 | 1.200 | $\text{H}_2\text{O}$ | -229.1 | 353.5 |
| 7: $\text{H}_2\text{O}$ | $\text{H}_2\text{O}$ | 0.9200 | 1.400 | $\text{CH}_2\text{CO}$ | 200.0 | 72.0 |

---

### 3.9 Complex-Step Numerical Differentiation of Excess Properties

To compute caloric thermodynamic excess properties without subtractive roundoff cancellation:
* **Excess Enthalpy:**
  $$h^E = -R T^2 \sum_{i=1}^{N_c} x_i \left( \frac{\partial \ln \gamma_i}{\partial T} \right)_{P, \mathbf{x}}$$
* **Excess Heat Capacity:**
  $$c_p^E = \left( \frac{\partial h^E}{\partial T} \right)_{P, \mathbf{x}}$$

Standard finite differences suffer from numerical cancellation error:
$$\frac{dg}{dT} \approx \frac{g(T + h) - g(T)}{h} \implies \text{Optimal } h \approx \sqrt{\epsilon_{\text{mach}}} \approx 10^{-8}, \; \text{Error } \sim 10^{-8}$$

The engine utilizes **Complex-Step Differentiation** in the complex plane:
$$g(T + i h) = g(T) + i h g'(T) - \frac{h^2}{2} g''(T) - i \frac{h^3}{6} g'''(T) + O(h^4)$$
Taking the imaginary part and dividing by $h$:
$$g'(T) = \frac{\operatorname{Im}[g(T + i h)]}{h} + O(h^2)$$
Because there is no subtraction in the numerator, step size can be chosen near machine precision:
$$h = 10^{-20} T \implies \text{Approximation error } O(10^{-40}) \le \epsilon_{\text{mach}}$$
yielding exact derivative evaluations to 16 decimal places.

---

### 3.10 Euler Homogeneity and Gibbs-Duhem Consistency Checks

Extensive Gibbs free energy $G(T, P, \mathbf{n})$ is a homogeneous function of degree 1 with respect to mole numbers $\mathbf{n}$. By Euler's Homogeneity Theorem:
$$G = \sum_{i=1}^{N_c} n_i \left( \frac{\partial G}{\partial n_i} \right)_{T, P, n_{j \ne i}} = \sum_{i=1}^{N_c} n_i \mu_i$$
Taking the total differential:
$$dG = \sum_{i=1}^{N_c} \mu_i dn_i + \sum_{i=1}^{N_c} n_i d\mu_i$$
Comparing with the fundamental thermodynamic property relation:
$$dG = -S dT + V dP + \sum_{i=1}^{N_c} \mu_i dn_i$$
Equating both expressions establishes the **Gibbs-Duhem Equation**:
$$S dT - V dP + \sum_{i=1}^{N_c} n_i d\mu_i = 0$$
At constant temperature and pressure ($dT = 0, dP = 0$), dividing by total moles $n$:
$$\sum_{i=1}^{N_c} x_i d\mu_i = 0 \iff \sum_{i=1}^{N_c} x_i d\ln \gamma_i = 0$$
The thermodynamic engine continuously audits activity models against this identity:
$$\mathcal{E}_{\text{GD}} = \left| \sum_{i=1}^{N_c} x_i \frac{\partial \ln \gamma_i}{\partial x_k} \right| \le 10^{-12}$$

---

## 4. Mathematical Theory of Nondimensionalization, Asymptotics, Symmetries, and Dynamics

This chapter formalizes the complete mathematical theory underlying `core/adimensionalizacion/` and the **Transform** workspace.

### 4.1 Dimensional Vector Spaces over $\mathbb{Q}^7$ and Unit Projections

Physical dimensions form a 7-dimensional vector space $\mathbb{Q}^7$ over the field of rational numbers under multiplication, mapped to the base SI dimensions:
$$\mathbf{d} = \begin{bmatrix} d_L & d_M & d_T & d_I & d_\Theta & d_N & d_J \end{bmatrix}^T \in \mathbb{Q}^7$$
representing length $[L]$, mass $[M]$, time $[T]$, electric current $[I]$, thermodynamic temperature $[\Theta]$, amount of substance $[N]$, and luminous intensity $[J]$.

#### Structural AST Rules
1. **Additive Homogeneity:** In any sum $A + B$, dimensions must match exactly:
   $$[A] = [B] \iff \mathbf{d}_A - \mathbf{d}_B = \mathbf{0} \in \mathbb{Q}^7$$
2. **Dimensionless Arguments:** All arguments of transcendental operators ($\exp, \ln, \sin, \cos, \tan, \sinh, \cosh, \tanh, \text{erf}$) must be dimensionless:
   $$[\arg] = \mathbf{0} \in \mathbb{Q}^7$$
3. **Differential Operators:** Derivatives subtract the dimension of the independent coordinate:
   $$\left[ \frac{\partial^n f}{\partial x^n} \right] = [f] - n [x], \quad [\nabla \cdot \mathbf{v}] = [\mathbf{v}] - [L], \quad [\nabla^2 f] = [f] - 2[L]$$
4. **Affine Temperature Distinction:** Units with temperature datum shifts (e.g., $^\circ\text{C}, ^\circ\text{F}$) represent affine coordinates $T = T_0 + \Delta T$. The engine prohibits multiplicative scaling on affine quantities, requiring an explicit affine transformation:
   $$v = R_v + S_v v'$$

---

### 4.2 The Fundamental Theorem of Dimensional Analysis: Matrix Formulation over $\mathbb{Q}$

Let a physical model involve $n$ variables and parameters $\mathbf{q} = [q_1, \dots, q_n]^T$. The dimensional matrix $\mathbf{D} \in \mathbb{Q}^{m \times n}$ has entries $D_{ij}$ representing the exponent of base dimension $i$ in quantity $q_j$:
$$[q_j] = \prod_{i=1}^m B_i^{D_{ij}}$$

A dimensionless product $\Pi = \prod_{j=1}^n q_j^{v_j}$ has dimensions:
$$[\Pi] = \prod_{i=1}^m B_i^{\sum_{j=1}^n D_{ij} v_j} = \prod_{i=1}^m B_i^0 \iff \mathbf{D} \mathbf{v} = \mathbf{0}$$

#### Buckingham $\Pi$ Theorem
By the Rank-Nullity Theorem, the dimension of the nullspace $\ker(\mathbf{D})$ over $\mathbb{Q}$ is:
$$p = n - \operatorname{rank}(\mathbf{D})$$
There exist exactly $p$ independent dimensionless groups $\Pi_1, \dots, \Pi_p$.

#### Exact Primitive Integer Vector Reduction
To ensure canonical numerical stability, any rational nullspace basis vector $\mathbf{v} \in \mathbb{Q}^n$ is scaled to a unique primitive integer vector $\mathbf{w} \in \mathbb{Z}^n$:
$$L = \operatorname{lcm}(\text{denom}(v_1), \dots, \text{denom}(v_n))$$
$$\tilde{w}_j = L \cdot v_j \in \mathbb{Z}$$
$$G = \operatorname{gcd}(\tilde{w}_1, \dots, \tilde{w}_n)$$
$$w_j = \frac{\tilde{w}_j}{G}$$
with orientation chosen such that the first non-zero component is positive ($w_{\text{first}} > 0$).

---

### 4.3 Continuous Transformation Groups and Invariant Symmetries (Lie Theory)

Consider a system of differential equations $\Delta_k(\mathbf{x}, \mathbf{u}, \mathbf{u}^{(1)}, \dots, \mathbf{u}^{(n)}) = 0$. A one-parameter continuous Lie group of point transformations is:
$$\mathbf{x}^* = \mathbf{X}(\mathbf{x}, \mathbf{u}; \epsilon), \quad \mathbf{u}^* = \mathbf{U}(\mathbf{x}, \mathbf{u}; \epsilon)$$
with identity at $\epsilon = 0$.

#### Infinitesimal Generator
The infinitesimal generator of the group is the first-order differential operator:
$$\mathbf{v}_{\text{Lie}} = \sum_{i=1}^p \xi_i(\mathbf{x}, \mathbf{u}) \frac{\partial}{\partial x_i} + \sum_{\alpha=1}^q \eta_\alpha(\mathbf{x}, \mathbf{u}) \frac{\partial}{\partial u_\alpha}$$
where $\xi_i = \left.\frac{\partial X_i}{\partial \epsilon}\right|_{\epsilon=0}$ and $\eta_\alpha = \left.\frac{\partial U_\alpha}{\partial \epsilon}\right|_{\epsilon=0}$.

#### Prolongation Formula
The action of the group on derivative coordinates $\mathbf{u}^{(n)}$ is generated by the $n$-th prolongation $\operatorname{pr}^{(n)} \mathbf{v}_{\text{Lie}}$:
$$\operatorname{pr}^{(n)} \mathbf{v}_{\text{Lie}} = \mathbf{v}_{\text{Lie}} + \sum_{\alpha=1}^q \sum_{J} \eta_\alpha^J \frac{\partial}{\partial u_\alpha^J}$$
where $J = (j_1, \dots, j_k)$ is a multi-index, and coefficients $\eta_\alpha^J$ satisfy the recursion:
$$\eta_\alpha^{J, i} = D_i \eta_\alpha^J - \sum_{j=1}^p D_i(\xi_j) u_\alpha^{J, j}$$
where $D_i$ is the total derivative operator with respect to $x_i$.

#### Lie Invariance Criterion
The differential equation system is invariant under the Lie group if and only if:
$$\left. \operatorname{pr}^{(n)} \mathbf{v}_{\text{Lie}} \left( \Delta_k \right) \right|_{\Delta = 0} = 0, \quad \forall k$$

---

### 4.4 Similarity Reductions and Traveling Wave Invariants

#### 1. Similarity Reduction Ansatz
For a PDE with time $\tau$, spatial coordinate $\xi$, and field $u(\xi, \tau)$, scaling invariance generates the dilatation group:
$$\tau^* = \lambda^a \tau, \quad \xi^* = \lambda^b \xi, \quad u^* = \lambda^c u$$
The characteristic equations for group invariants:
$$\frac{d\tau}{a \tau} = \frac{d\xi}{b \xi} = \frac{du}{c u}$$
integrate to the **similarity variable** $\zeta$ and reduced field ansatz $F(\zeta)$:
$$\zeta = \xi \tau^{-q}, \quad u(\xi, \tau) = \tau^p F(\zeta), \quad q = \frac{b}{a}, \quad p = \frac{c}{a}$$
Transforming partial derivatives:
$$\frac{\partial u}{\partial \xi} = \tau^{p-q} F'(\zeta), \quad \frac{\partial^2 u}{\partial \xi^2} = \tau^{p-2q} F''(\zeta)$$
$$\left. \frac{\partial u}{\partial \tau} \right|_{\xi} = p \tau^{p-1} F(\zeta) - q \tau^{p-1} \zeta F'(\zeta)$$
The PDE reduces strictly to an ordinary differential equation in $\zeta$ if and only if all terms in the equation factor the exact same power $\tau^{p-1}$.

#### 2. Traveling Wave Invariants
Under translation invariance in $\xi$ and $\tau$, the characteristic curve defines the traveling wave coordinate:
$$z = \xi - c \tau$$
where $c$ is the constant wave propagation speed. Substituting:
$$\frac{\partial u}{\partial \tau} = -c \frac{du}{dz}, \quad \frac{\partial u}{\partial \xi} = \frac{du}{dz}, \quad \frac{\partial^2 u}{\partial \xi^2} = \frac{d^2 u}{dz^2}$$
collapsing evolutionary PDEs into low-dimensional ODE dynamical systems in $z$.

---

### 4.5 Logarithmic Formulation of Normalization Objectives and Equivalence Certificates

The selection of characteristic scales $S_v$ for fields and coordinates enforces normalization objectives $|\text{effective coefficient}| = 1$.

#### Logarithmic Objective Matrix
In logarithmic space, scale relationships form a linear system over $\mathbb{Q}$:
$$\mathbf{B} \ln \mathbf{S} = \mathbf{r}$$
where $B_{ij}$ is the exponent of scale $S_j$ in the $i$-th target term, and $r_i = -\ln |c_i|$.
* If $\operatorname{rank}(\mathbf{B}) = \dim(\mathbf{S})$, scales are uniquely determined.
* If $\operatorname{rank}(\mathbf{B}) < \dim(\mathbf{S})$, the kernel defines a parametrized scale family.
* If $\mathbf{r} \notin \operatorname{range}(\mathbf{B})$, objectives are mathematically incompatible.

#### Certified Equivalence Proof
To certify mathematical equivalence between the original dimensional model and the dimensionless transformed model, the engine performs **symbolic inverse substitution**:
$$v = S_v v'$$
into the published dimensionless AST. Expanding fully via Cartesian polynomial algebra, clearing denominators, and subtracting from the original dimensional AST:
$$\Delta_{\text{AST}} = \text{AST}_{\text{orig}} - \mathcal{S}^{-1}\left( \text{AST}_{\text{dimless}} \right) \equiv 0$$
If $\Delta_{\text{AST}} = 0$, an exact mathematical certificate of equivalence is issued.

---

### 4.6 Kruskal's Method of Dominant Balance and Asymptotic Layer Analysis

Given a singularly perturbed differential equation containing a small parameter $\epsilon \to 0^+$, Kruskal's method of dominant balance identifies all asymptotic regimes without ad-hoc guesswork.

#### Newton Polygon and Upper Convex Envelope
Under local coordinate stretching $\xi = \xi_0 + \delta X$ with $s = \ln \delta \le 0$, a differential term of spatial order $p$ and coefficient magnitude $m$ scales as $m \delta^{-p} = \exp(\ln m - p s)$.

In the $(s, \ln \text{magnitude})$ plane, each term corresponds to the affine line:
$$\mathcal{L}_k(s) = \ln m_k - p_k s$$
At any local scale $s$, the dominant terms are those lying on the **upper convex envelope**:
$$\mathcal{E}(s) = \max_k \left( \ln m_k - p_k s \right)$$
The intersections (vertices) of the upper envelope define the **distinguished limits** where two or more physical mechanisms achieve dominant balance:
$$s^* = \frac{\ln m_j - \ln m_i}{p_j - p_i}$$

#### Boundary Layer Thickness and Location
* If the highest derivative term is negligible at unit scale ($\delta = 1$), the regular asymptotic reduction loses boundary conditions $\implies$ **singular perturbation**.
* The boundary layer thickness is given by the distinguished scale:
  $$\delta_{\text{layer}} = \exp(s^*)$$
* **Decay Direction Criteria:**
  - For $a u'' + b u' = 0$: characteristic root $\lambda = -b/a$. The boundary layer is at the left boundary $\xi = 0$ if $b/a > 0$; at the right boundary $\xi = L$ if $b/a < 0$.
  - For $a u'' + c u = 0$: characteristic roots $\lambda = \pm \sqrt{-c/a}$. If $c/a < 0$, layers form at both boundaries; if $c/a > 0$, the solution oscillates without boundary layers.

---

### 4.7 Linear Stability, Dynamical Systems, and Dispersion Relations

Consider a multi-field reaction-diffusion-convection system in evolution form:
$$\frac{\partial \mathbf{u}}{\partial \tau} = \mathbf{F}\left( \mathbf{u}, \frac{\partial \mathbf{u}}{\partial \xi}, \frac{\partial^2 \mathbf{u}}{\partial \xi^2} \right)$$

#### Complex-Step Spatial Operator Linearization
At a homogeneous steady state $\mathbf{u}^*$ ($\mathbf{F}(\mathbf{u}^*, \mathbf{0}, \mathbf{0}) = \mathbf{0}$), spatial derivatives are treated as independent variables $w_{j, n} = \frac{\partial^n u_j}{\partial \xi^n}$.
The Jacobian matrices are evaluated to machine precision via complex-step differentiation ($h_{\mathbb{C}} = 10^{-30}$):
$$\mathbf{J} = \left. \frac{\partial \mathbf{F}}{\partial \mathbf{u}} \right|_{\mathbf{u}^*}, \quad \mathbf{C}_n = \left. \frac{\partial \mathbf{F}}{\partial \mathbf{w}_n} \right|_{\mathbf{u}^*}$$

#### Spatial Dispersion Relation $\sigma(k)$
For Fourier perturbation modes $\delta \mathbf{u} = \hat{\mathbf{u}} \exp(i k \xi + \sigma \tau)$, spatial differentiation transforms as $\frac{\partial^n}{\partial \xi^n} \to (i k)^n$.
The growth rates $\sigma(k)$ are the eigenvalues of the characteristic matrix:
$$\mathbf{M}(k) = \mathbf{J} + \sum_{n=1}^{n_{\max}} (i k)^n \mathbf{C}_n = \mathbf{J} + i k \mathbf{C}_1 - k^2 \mathbf{C}_2 + \dots$$
The dispersion relation is given by the polynomial roots of:
$$\det\left( \sigma \mathbf{I} - \mathbf{M}(k) \right) = 0$$

#### Stability and Bifurcation Classification
* **Homogeneous Stability:** $\max_j \operatorname{Re}(\sigma_j(0)) < 0$.
* **Hopf Bifurcation:** $\operatorname{Re}(\sigma(0)) = 0$ with $\operatorname{Im}(\sigma(0)) = \omega_0 \ne 0$.
* **Turing Instability (Diffusion-Driven Instability):**
  1. System is stable to homogeneous perturbations: $\max_j \operatorname{Re}(\sigma_j(0)) < 0$.
  2. There exists a critical wavenumber $k_c > 0$ such that $\max_j \operatorname{Re}(\sigma_j(k_c)) > 0$ with $\operatorname{Im}(\sigma(k_c)) = 0$.
  This triggers spontaneous spatial pattern formation.

---

### 4.8 Pseudo-Arclength Numerical Continuation of Equilibrium Curves

To trace nonlinear equilibrium branches $\mathbf{F}(\mathbf{u}, \mu) = \mathbf{0}$ across fold points (limit points) where standard Newton-Raphson fails ($\det \mathbf{J}_{\mathbf{u}} = 0$):

#### Augmented Arclength System
We introduce the arclength parameter $s$ and augmented vector $\mathbf{x}(s) = [\mathbf{u}(s)^T, \mu(s)]^T \in \mathbb{R}^{n+1}$.
The augmented equilibrium system is:
$$\mathbf{H}(\mathbf{x}(s), s) = \begin{bmatrix} \mathbf{F}(\mathbf{u}(s), \mu(s)) \\ \langle \dot{\mathbf{x}}_0, \mathbf{x}(s) - \mathbf{x}_0 \rangle - \Delta s \end{bmatrix} = \mathbf{0}$$
where $\dot{\mathbf{x}}_0 = [\dot{\mathbf{u}}_0^T, \dot{\mu}_0]^T$ is the unit tangent vector to the curve at $s_0$:
$$\begin{bmatrix} \mathbf{J}_{\mathbf{u}}(\mathbf{x}_0) & \frac{\partial \mathbf{F}}{\partial \mu}(\mathbf{x}_0) \end{bmatrix} \dot{\mathbf{x}}_0 = \mathbf{0}, \quad \|\dot{\mathbf{x}}_0\|_2 = 1$$
oriented consistently: $\langle \dot{\mathbf{x}}_0, \dot{\mathbf{x}}_{-1} \rangle > 0$.

#### Corrector Newton Iteration
Newton-Raphson on the augmented system solves:
$$\begin{bmatrix} \mathbf{J}_{\mathbf{u}}(\mathbf{x}^{(m)}) & \frac{\partial \mathbf{F}}{\partial \mu}(\mathbf{x}^{(m)}) \\ \dot{\mathbf{u}}_0^T & \dot{\mu}_0 \end{bmatrix} \begin{bmatrix} \Delta \mathbf{u} \\ \Delta \mu \end{bmatrix} = -\begin{bmatrix} \mathbf{F}(\mathbf{u}^{(m)}, \mu^{(m)}) \\ \langle \dot{\mathbf{x}}_0, \mathbf{x}^{(m)} - \mathbf{x}_0 \rangle - \Delta s \end{bmatrix}$$
The augmented $(n+1) \times (n+1)$ Jacobian matrix remains strictly non-singular even at turning points ($\det \mathbf{J}_{\mathbf{u}} = 0$), allowing effortless continuation past limit folds.

---

### 4.9 Method of Lines (MOL) Numerical Simulation of Dimensionless Systems

PDEs in the Transform workspace are discretized in space to form systems of ODEs integrated in time.

#### Grid Generation and Node Sizing Heuristics
For domain $\xi \in [0, L]$, the spatial grid step $h = L / (N - 1)$ is constrained by two physical requirements:
1. **Cell Péclet Number Constraint (Oscillation Avoidance):**
   $$Pe_{\text{cell}} = \frac{V h}{D} \le 2 \implies N \ge \left\lceil \frac{L V}{2 D} \right\rceil + 1$$
2. **Internal Layer Resolution:** At least 10 nodes must span each internal boundary layer:
   $$N \ge \left\lceil \frac{10 L}{\ell_{\text{int}}} \right\rceil + 1, \quad \ell_{\text{int}} = \min\left( \frac{D}{V}, \sqrt{\frac{D}{r_J}} \right)$$

#### Second-Order Centered Finite Differences
$$\left. \frac{\partial u}{\partial \xi} \right|_i \approx \frac{u_{i+1} - u_{i-1}}{2h}, \quad \left. \frac{\partial^2 u}{\partial \xi^2} \right|_i \approx \frac{u_{i+1} - 2u_i + u_{i-1}}{h^2}$$

#### Ghost-Cell Formulation for General Boundary Conditions
For flux and Robin boundary conditions at $\xi = 0$:
$$\alpha u(0) + \beta \left. \frac{\partial u}{\partial \xi} \right|_{\xi=0} = \gamma \implies \alpha u_0 + \beta \frac{u_1 - u_{-1}}{2h} = \gamma$$
The fictitious ghost node $u_{-1}$ is eliminated:
$$u_{-1} = u_1 + \frac{2h}{\beta} (\alpha u_0 - \gamma)$$
and substituted into the interior stencil at $i = 0$.

#### Spatial Error Verification
The simulation is solved on grid $N$, then repeated on a refined grid $2N - 1$ containing all original nodes. The spatial error indicator is:
$$\mathcal{E}_{\text{spatial}} = \frac{\| \mathbf{u}_N(t_{\text{final}}) - \mathbf{u}_{2N-1}(t_{\text{final}}) \|_\infty}{\max\left( 1.0, \| \mathbf{u}_N(t_{\text{final}}) \|_\infty \right)}$$

---

## 5. Symbolic Model Compilation and Structural Index Theory

### 5.1 Typed Directed Acyclic Graph (DAG) Representation

In `core/compilador/`, equations are compiled into a typed Directed Acyclic Graph (DAG) separating:
* **Differential States:** $\mathbf{y}_d \in \mathbb{R}^{N_d}$ (e.g., inventories $n_{i, v}, U_v$).
* **Algebraic Closures:** $\mathbf{y}_a \in \mathbb{R}^{N_a}$ (e.g., temperatures, pressures, equilibrium phase splits).
* **Parameters & Constants:** $\boldsymbol{\theta} \in \mathbb{R}^{N_p}$.

```
                 [ Residual Eq: F_k = 0 ]
                       /          \
                [ Left Side ]    [ Right Side ]
                     │                  │
               [ d(n_i)/dt ]     [ ∑ B_vs ṅ_s x_si ]
```

---

### 5.2 Block Lower Triangularization via Tarjan's SCC Algorithm

To maximize numerical efficiency, large coupled algebraic systems $\mathbf{g}(\mathbf{y}_a) = \mathbf{0}$ are partitioned into irreducible sub-blocks using **Tarjan's Strongly Connected Components (SCC)** algorithm on the directed dependency graph.
1. Equations and variables form vertices $V$. Directed edges $(e_i, v_j)$ indicate variable $v_j$ is solved in equation $e_i$.
2. Tarjan's depth-first search identifies all strongly connected components in $O(|V| + |E|)$ time.
3. Permuting the incidence matrix into **Block Lower Triangular (BLT)** form:
   $$\mathbf{J}_{\text{BLT}} = \begin{bmatrix} \mathbf{A}_{11} & \mathbf{0} & \dots & \mathbf{0} \\ \mathbf{A}_{21} & \mathbf{A}_{22} & \dots & \mathbf{0} \\ \vdots & \vdots & \ddots & \vdots \\ \mathbf{A}_{m1} & \mathbf{A}_{m2} & \dots & \mathbf{A}_{mm} \end{bmatrix}$$
Instead of solving a coupled system of dimension $N$, the solver sequences $m$ small independent sub-problems of dimension $d_k = \dim(\mathbf{A}_{kk}) \ll N$.

---

### 5.3 Bipartite Matching, Dulmage-Mendelsohn Decomposition, and DOFs

The structural solvability of the compiled system is analyzed using the bipartite graph $G = (V_{\text{eq}}, V_{\text{var}}, E)$.
The **Dulmage-Mendelsohn decomposition** partitions $G$ into:
1. $G_{\text{under}}$: Under-determined subsystem (more variables than equations).
2. $G_{\text{square}}$: Well-determined square subsystem ($\det \mathbf{J} \neq 0$).
3. $G_{\text{over}}$: Over-determined subsystem (redundant constraints).

The system is solvable if and only if $G_{\text{under}} = \emptyset$ and $G_{\text{over}} = \emptyset$, corresponding to:
$$DOF = N_{\text{var}} - N_{\text{eq}} - N_{\text{param}} = 0$$

---

### 5.4 DAE Index Classification and Structural Pantelides Reduction

A general simulation model forms a Differential-Algebraic Equation (DAE):
$$\mathbf{F}(t, \mathbf{y}, \mathbf{y}') = \mathbf{0}$$
The **differential index** $\nu$ is the minimum differentiation order $k$ required to express $\mathbf{y}'$ as an explicit ODE $\mathbf{y}' = \boldsymbol{\psi}(t, \mathbf{y})$.

#### Semi-Explicit DAE of Index 1
$$\begin{aligned}
\frac{d\mathbf{y}_d}{dt} &= \mathbf{f}(t, \mathbf{y}_d, \mathbf{y}_a) \\
\mathbf{0} &= \mathbf{g}(t, \mathbf{y}_d, \mathbf{y}_a)
\end{aligned}$$
Differentiating the algebraic constraint with respect to time:
$$\mathbf{0} = \frac{\partial \mathbf{g}}{\partial t} + \frac{\partial \mathbf{g}}{\partial \mathbf{y}_d} \frac{d\mathbf{y}_d}{dt} + \frac{\partial \mathbf{g}}{\partial \mathbf{y}_a} \frac{d\mathbf{y}_a}{dt}$$
Substituting $\frac{d\mathbf{y}_d}{dt} = \mathbf{f}$:
$$\frac{\partial \mathbf{g}}{\partial \mathbf{y}_a} \frac{d\mathbf{y}_a}{dt} = -\frac{\partial \mathbf{g}}{\partial t} - \frac{\partial \mathbf{g}}{\partial \mathbf{y}_d} \mathbf{f}(t, \mathbf{y}_d, \mathbf{y}_a)$$
The system has **index 1** if and only if the algebraic Jacobian is non-singular:
$$\det\left( \frac{\partial \mathbf{g}}{\partial \mathbf{y}_a} \right) \neq 0$$

---

### 5.5 Mattsson-Söderlind Dummy Derivative Method

When Pantelides index reduction differentiates constraints to reduce higher-index DAEs ($\nu \ge 2$), the number of differential equations exceeds the true physical degrees of freedom, causing numerical drift away from the original algebraic manifold.
The **Mattsson-Söderlind method** selects a subset of state variables as algebraic "dummy variables", transforming higher-index invariants into stable index-1 representations without drift.

---

### 5.6 Algebraic Compatibility Constraints on Invariant Inventories

When invariant conditions are imposed on dynamic inventories, the system enforces:
$$\begin{aligned}
\frac{dI}{dt} &= \Phi(t, \mathbf{y}) \\
I(t) - I(t_0) &= 0 \\
\Phi(t, \mathbf{y}) &= 0
\end{aligned}$$
This forms a constrained semi-explicit index-1 DAE, retaining underlying dynamic formulation coordinates without dimensional reduction.

---

## 6. Numerical Solvers and Discontinuity Localization

### 6.1 Embedded Runge-Kutta-Fehlberg (RK45) Integration

In `core/solvers/integrador.py`, the explicit Dormand-Prince 5(4) pair integrates non-stiff systems with nested equilibrium closures.

#### Butcher Tableau
$$\begin{array}{c|ccccccc}
0 & \\
1/5 & 1/5 \\
3/10 & 3/40 & 9/40 \\
4/5 & 44/45 & -56/15 & 32/9 \\
8/9 & 19372/6561 & -25360/2187 & 64448/6561 & -212/729 \\
1 & 9017/3168 & -355/33 & 46732/5247 & 49/176 & -5103/18656 \\
1 & 35/384 & 0 & 500/1113 & 125/192 & -2187/6784 & 11/84 \\
\hline
\mathbf{y}_{n+1} & 35/384 & 0 & 500/1113 & 125/192 & -2187/6784 & 11/84 & 0 \\
\hat{\mathbf{y}}_{n+1} & 5179/57600 & 0 & 7571/16695 & 393/640 & -92097/339200 & 187/2100 & 1/40
\end{array}$$

#### Adaptive Error Control
Local truncation error:
$$\mathbf{e}_{n+1} = \mathbf{y}_{n+1} - \hat{\mathbf{y}}_{n+1} = h \sum_{i=1}^7 (b_i - \hat{b}_i) \mathbf{k}_i$$
Error norm:
$$\text{err} = \sqrt{\frac{1}{N} \sum_{i=1}^N \left( \frac{e_{n+1, i}}{\text{rtol} \max(|y_{n, i}|, |y_{n+1, i}|) + \text{atol}_i} \right)^2}$$
PI-step adaptation:
$$h_{\text{new}} = h \min\left( 5.0, \max\left( 0.2, 0.9 \cdot \text{err}^{-1/5} \right) \right)$$

---

### 6.2 Stiff Variable-Order Backward Differentiation Formulas (BDF)

For stiff systems, implicit BDF schemes of orders $k \in \{1, \dots, 5\}$ solve:
$$\sum_{j=0}^k \alpha_j \mathbf{y}_{n+1-j} = h \beta_0 \mathbf{f}(t_{n+1}, \mathbf{y}_{n+1})$$
At each time step, modified Newton iteration solves:
$$\left[ \mathbf{I} - h \beta_0 \mathbf{J} \right] \Delta \mathbf{y}^{(m)} = -\sum_{j=0}^k \alpha_j \mathbf{y}_{n+1-j}^{(m)} + h \beta_0 \mathbf{f}(t_{n+1}, \mathbf{y}_{n+1}^{(m)})$$
where Jacobian $\mathbf{J} = \frac{\partial \mathbf{f}}{\partial \mathbf{y}}$ is evaluated analytically or by difference quotients.

---

### 6.3 Fully Implicit Radau IIA Collocation for Index-1 and Index-2 DAEs

For stiff Differential-Algebraic Equations $\mathbf{M} \mathbf{y}' = \mathbf{f}(t, \mathbf{y})$, the engine provides the 3-stage Radau IIA implicit Runge-Kutta method (order 5, L-stable).
#### Radau IIA Butcher Tableau
$$\begin{array}{c|ccc}
\frac{4 - \sqrt{6}}{10} & \frac{88 - 7\sqrt{6}}{360} & \frac{296 - 169\sqrt{6}}{1800} & \frac{-2 + 3\sqrt{6}}{225} \\
\frac{4 + \sqrt{6}}{10} & \frac{296 + 169\sqrt{6}}{1800} & \frac{88 + 7\sqrt{6}}{360} & \frac{-2 - 3\sqrt{6}}{225} \\
1 & \frac{16 - \sqrt{6}}{36} & \frac{16 + \sqrt{6}}{36} & \frac{1}{9} \\
\hline
& \frac{16 - \sqrt{6}}{36} & \frac{16 + \sqrt{6}}{36} & \frac{1}{9}
\end{array}$$
Because $c_3 = 1$ and $a_{3j} = b_j$, Radau IIA is stiffly accurate, damping infinite high-frequency stiff eigenvalues and preserving algebraic constraints exactly at the end of each step.

---

### 6.4 Phase Signature Tracking and Event Bisection Across $C^1$ Kinks

Let $\mathcal{S}(t, \mathbf{y})$ be the discrete phase presence signature:
$$\mathcal{S}(t, \mathbf{y}) = \left( \mathcal{P}_1, \dots, \mathcal{P}_{N_v} \right)$$
When $\mathcal{S}(t_a) \neq \mathcal{S}(t_b)$, a phase boundary was crossed within $[t_a, t_b]$.

```
Step: [ t_a , t_b ]  ───►  Bisection: |t_hi - t_lo| ≤ 1e-12 max(1, |t_hi|)
                                       │
                                       ▼
                        Restart with h_0 = h_min
```

Bisection locates $t^*$ to tolerance:
$$|t_{\text{hi}} - t_{\text{lo}}| \le 10^{-12} \cdot \max(1.0, |t_{\text{hi}}|)$$
avoiding derivative kinks across phase appearances/disappearances.

---

### 6.5 Warm-Restart Protocol and Step-Size Re-Initialization

To prevent order reduction across $C^1$ kinks:
1. The trajectory is terminated at $t^* = t_{\text{hi}}$.
2. The exact state $\mathbf{y}^* = \mathbf{y}(t^*)$ is recorded.
3. A fresh integrator is instantiated at $(t^*, \mathbf{y}^*)$ with $h_0 = h_{\text{min}}$.
4. Historical multistep vectors (in BDF) and stage memory (in RK45) are purged, maintaining piecewise $C^1$ trajectory accuracy.

---

## 7. Numerical Verification and Analytical Benchmark Theorems

### 7.1 Global Integral Conservation Residuals of Mass and Energy

#### Mass Conservation Residual
$$\mathcal{R}_{M, i}(t) = \left[ m_i(t) - m_i(0) \right] - \int_0^t \left( \sum_{s \in \text{in}} \dot{m}_{i, s}(\tau) - \sum_{s \in \text{out}} \dot{m}_{i, s}(\tau) \right) d\tau - \int_0^t R_i(\tau) \, d\tau$$
Certified tolerance:
$$\epsilon_{M, i} = \frac{|\mathcal{R}_{M, i}(t)|}{\max\left( m_i(0), m_i(t), \int_0^t \sum \dot{m}_{\text{in}} d\tau \right)} \le 10^{-7}$$

#### Energy Conservation Residual
$$\mathcal{R}_E(t) = \left[ U(t) - U(0) \right] - \int_0^t \left( \sum_s B_{vs} \dot{n}_s h_s + \dot{Q} + \dot{W}_s - P \frac{dV}{d\tau} \right) d\tau$$
Under constant pressure heating:
$$H(t) = H(0) + \left( F_{\text{feed}} h_{\text{feed}} + \dot{Q} \right) t$$
Certified tolerance:
$$\epsilon_E = \frac{|\mathcal{R}_E(t)|}{|H(0)| + \dot{Q} t} \le 10^{-7}$$

---

### 7.2 Second Law Clausius-Duhem Entropy Generation Certification

To ensure physical realizability, the engine tracks total entropy generation:
$$\dot{S}_{\text{gen}} = \frac{dS_v}{dt} - \sum_{s \in \text{in}} \dot{n}_s s_s + \sum_{s \in \text{out}} \dot{n}_s s_s - \sum_k \frac{\dot{Q}_k}{T_{b, k}} \ge 0$$
Any violation ($\dot{S}_{\text{gen}} < -10^{-9}\text{ W/K}$) flags a Second Law exception (`segunda_ley_incumplida`).

---

### 7.3 Benchmark 1: Unsteady Multicomponent Batch Diffusion with Chemical Reaction

Consider 1D transient diffusion and first-order decay of species $A$ in a slab of thickness $2L$ with uniform initial concentration $C_0$ and zero surface concentrations:
$$\frac{\partial C_A}{\partial t} = D \frac{\partial^2 C_A}{\partial x^2} - k_1 C_A, \quad C_A(x, 0) = C_0, \quad C_A(\pm L, t) = 0$$
#### Analytical Solution
Transforming via $C_A(x, t) = e^{-k_1 t} \tilde{C}(x, t)$, the heat equation with Dirichlet boundaries yields the exact Fourier series:
$$C_A(x, t) = \frac{4 C_0}{\pi} e^{-k_1 t} \sum_{n=0}^\infty \frac{(-1)^n}{2n + 1} \exp\left( -\frac{(2n+1)^2 \pi^2 D t}{4 L^2} \right) \cos\left( \frac{(2n+1)\pi x}{2L} \right)$$
Used to audit spatial MOL convergence and operator splitting error.

---

### 7.4 Benchmark 2: Hydraulic Surge and Water Hammer in Pipe Networks

Consider instantaneous valve closure at $x = L$ in a straight pipe of length $L$ with initial steady velocity $v_0$. Neglecting friction, the hyperbolic acoustic wave equations are:
$$\frac{\partial P}{\partial t} + \rho c^2 \frac{\partial v}{\partial x} = 0, \quad \frac{\partial v}{\partial t} + \frac{1}{\rho} \frac{\partial P}{\partial x} = 0$$
where $c = \sqrt{K / \rho}$ is acoustic wave speed.
#### Analytical Joukowsky Solution
At closure ($t = 0$), the instantaneous pressure surge is given by Joukowsky's formula:
$$\Delta P_{\text{surge}} = \rho c v_0$$
The wave propagates back and forth with exact period $T_{\text{period}} = 4 L / c$.

---

### 7.5 Benchmark 3: Binary Vapor-Liquid Flash Equilibrium

Consider an equimolar binary mixture ($z_1 = z_2 = 0.5$) with constant relative volatility $\alpha = K_1 / K_2 > 1$.
The Rachford-Rice equation simplifies to:
$$\frac{0.5 (K_1 - 1)}{1 + \beta (K_1 - 1)} + \frac{0.5 (K_2 - 1)}{1 + \beta (K_2 - 1)} = 0$$
Substituting $K_2 = K_1 / \alpha$:
$$(K_1 - 1) [1 + \beta (K_1/\alpha - 1)] + (K_1/\alpha - 1) [1 + \beta (K_1 - 1)] = 0$$
#### Analytical Solution
$$\beta^* = \frac{K_1 + K_1/\alpha - 2}{2 (1 - K_1)(1 - K_1/\alpha)}$$
Used for testing machine-precision convergence of the flash solver.

---

### 7.6 Benchmark 4: The Classical Stefan Moving Boundary Problem

Consider 1D phase change (solidification of liquid in semi-infinite half-space $x > 0$) with interface position $s(t)$, liquid initially at melting temperature $T_m$, and wall held at $T_0 < T_m$:
$$\frac{\partial T}{\partial t} = \alpha_s \frac{\partial^2 T}{\partial x^2}, \quad 0 < x < s(t)$$
Interface energy balance (Stefan condition):
$$\rho \Delta h_{\text{fus}} \frac{ds}{dt} = \left. k_s \frac{\partial T}{\partial x} \right|_{x = s(t)^-}$$
#### Analytical Neumann Similarity Solution
$$T(x, t) = T_0 + (T_m - T_0) \frac{\operatorname{erf}\left( \frac{x}{2\sqrt{\alpha_s t}} \right)}{\operatorname{erf}(\lambda)}$$
$$s(t) = 2 \lambda \sqrt{\alpha_s t}$$
where $\lambda$ is the unique positive root of the transcendental equation:
$$\lambda e^{\lambda^2} \operatorname{erf}(\lambda) = \frac{C_{p, s} (T_m - T_0)}{\sqrt{\pi} \Delta h_{\text{fus}}} = \frac{\text{Ste}}{\sqrt{\pi}}$$
where $\text{Ste}$ is the dimensionless Stefan number.

---

### 7.7 Benchmark 5: Singularly Perturbed Boundary Layer with Exact Matched Asymptotics

Consider the boundary value problem:
$$\epsilon y''(x) + y'(x) + y(x) = 0, \quad x \in [0, 1], \quad y(0) = 0, \; y(1) = 1$$
with $0 < \epsilon \ll 1$.

#### 1. Exact Analytical Solution
The characteristic equation $\epsilon r^2 + r + 1 = 0$ has exact roots:
$$r_1 = \frac{-1 + \sqrt{1 - 4\epsilon}}{2\epsilon} = -1 - \epsilon + O(\epsilon^2)$$
$$r_2 = \frac{-1 - \sqrt{1 - 4\epsilon}}{2\epsilon} = -\frac{1}{\epsilon} + 1 + \epsilon + O(\epsilon^2)$$
The exact closed-form solution satisfying boundary conditions is:
$$y(x) = \frac{e^{r_1 x} - e^{r_2 x}}{e^{r_1} - e^{r_2}}$$

#### 2. Matched Asymptotic Expansion (Outer, Inner, and Composite)
* **Outer Solution ($x = O(1)$):**
  Setting $\epsilon = 0$: $y_{\text{out}}' + y_{\text{out}} = 0 \implies y_{\text{out}}(x) = C e^{-x}$. Satisfying $y(1) = 1 \implies C = e \implies y_{\text{out}}(x) = e^{1-x}$.
* **Inner Solution ($X = x/\epsilon$ near $x = 0$):**
  $Y''(X) + Y'(X) = 0 \implies Y(X) = A + B e^{-X}$. Satisfying $Y(0) = 0 \implies A + B = 0 \implies Y(X) = A(1 - e^{-X})$.
* **Prandtl Matching Principle:**
  $$\lim_{x \to 0} y_{\text{out}}(x) = e = \lim_{X \to \infty} Y(X) = A \implies A = e$$
* **Uniformly Valid Composite Solution:**
  $$y_{\text{comp}}(x) = y_{\text{out}}(x) + Y(x/\epsilon) - y_{\text{match}} = e^{1-x} - e \cdot e^{-x/\epsilon}$$
This benchmark directly verifies Kruskal's dominant balance and asymptotic layer detection.

---

## 8. Comprehensive Mathematical Proposal for Spatial Treatment, Generalized Meshes, and Multiphysics Discretization

The current core simulation engine (`core/compilador/compilador.py`) models physical systems primarily as lumped networks of homogeneous control volumes with non-spatial thermodynamic equilibrium closures. This chapter establishes the rigorous mathematical foundation and architectural design for extending the engine into **1D, 2D, and 3D distributed spatial domains**, supporting **generalized unstructured meshes** (Cartesian, hexagonal, simplicial, prismatic, and polyhedral), and modeling **fully coupled multiphysics** (matter, momentum, energy, and thermodynamics).

---

### 8.1 Architectural Paradigm and Pipeline Integration (Model $\to$ Transform $\to$ Solve $\to$ Results)

In conformance with the mandatory Four-Workspace Framework (Section 12 of `ARCHITECTURE.md`), spatial discretization is never hardcoded inside physical model equations.

```
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 1. MODEL WORKSPACE (Continuous Physics & Manifold Definition)          │
  │    • Microscopic balance laws: ∂(ρψ)/∂t + ∇·(ρψv) = -∇·J_ψ + S_ψ       │
  │    • Continuous Riemannian manifold M with metric tensor g_ij          │
  │    • Continuous boundary conditions on ∂M (Dirichlet, Neumann, Robin)  │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │ Abstract Field & Geometry Specs
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 2. TRANSFORM WORKSPACE (Spatial Meshing, Discretization & Reduction)   │
  │    • Mesh generation / import (Cartesian, Hexagonal, Polyhedral)       │
  │    • Metric tensor evaluation & face normal / volume integration       │
  │    • Cell-Centered FVM projection with high-resolution TVD limiters    │
  │    • Non-orthogonal & skewness gradient diffusion corrections          │
  │    • Spatial Method of Lines (MOL) reduction: PDE ──► Semi-Discrete DAE│
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │ Semi-Discrete DAE: M(dY/dt) = F(t, Y)
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 3. SOLVE WORKSPACE (Time Integration & Algebraic DAE Solvers)          │
  │    • Sparse block-structured Jacobian assembly (Newton-Krylov)         │
  │    • Stiff time integration (Radau IIA, BDF) with adaptive step size   │
  │    • Dynamic Adaptive Mesh Refinement (AMR) & load balancing           │
  │    • Monolithic vs. segregated multiphysics solver orchestration       │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │ State Trajectories Y(t_k)
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 4. RESULTS WORKSPACE (Spatial Reconstruction & Verification)           │
  │    • 1D axial profiles, 2D planar contour maps, 3D volumetric fields   │
  │    • Method of Manufactured Solutions (MMS) spatial order verification │
  │    • Global integral conservation & second-law entropy checks          │
  └────────────────────────────────────────────────────────────────────────┘
```

#### Contractual Invariants
1. **Model Invariance:** Authoring equations with spatial fields ($c_i(\mathbf{x}, t), T(\mathbf{x}, t), \mathbf{v}(\mathbf{x}, t)$) declares spatial domains $\mathcal{M}$ and boundary conditions $(\Gamma_D, \Gamma_N, \Gamma_R)$ without referencing discretization nodes, mesh sizes ($h$), or numerical schemes.
2. **Transform Discretization Metadata:** Spatial discretization converts PDEs into a semi-discrete DAE system $\mathbf{M} \frac{d\mathbf{Y}}{dt} = \mathbf{F}(t, \mathbf{Y})$. The resulting system is tagged with discretization metadata (mesh size $h$, cell Péclet number $Pe_{\text{cell}}$, limiter type) and recorded as an approximation, never certified as an exact mathematical equivalence.
3. **Common Results Contract:** Spatial solution fields are serialized under the common format (`results-format.md`) as tensor trajectories $\mathbf{Y}(t_k) \in \mathbb{R}^{N_{\text{nodes}} \times N_{\text{fields}}}$, enabling unified visualization in Results.

---

### 8.2 Differential Geometry, Manifolds, and Unified 1D, 2D, and 3D Formulations

To support arbitrary physical domains without ad-hoc case branching, spatial differential operators are formulated using **Riemannian differential geometry** on smooth manifolds $(\mathcal{M}, \mathbf{g})$ of dimension $d \in \{1, 2, 3\}$.

#### Curvilinear Coordinates and Metric Tensors
Let $\mathbf{x} = (x^1, \dots, x^d) \in \mathbb{R}^d$ be Cartesian coordinates, and let $\boldsymbol{\xi} = (\xi^1, \dots, \xi^d)$ be general curvilinear coordinates defined by the invertible diffeomorphism $\mathbf{x} = \boldsymbol{\chi}(\boldsymbol{\xi})$.

The **covariant tangent basis vectors** are:
$$\mathbf{g}_i = \frac{\partial \mathbf{x}}{\partial \xi^i}, \quad i = 1, \dots, d$$
The **contravariant normal basis vectors** are:
$$\mathbf{g}^i = \nabla \xi^i, \quad \mathbf{g}^i \cdot \mathbf{g}_j = \delta^i_j$$

The covariant components of the **Riemannian metric tensor** $g_{ij}$ and its contravariant inverse $g^{ij}$ are:
$$g_{ij} = \mathbf{g}_i \cdot \mathbf{g}_j = \sum_{k=1}^d \frac{\partial x^k}{\partial \xi^i} \frac{\partial x^k}{\partial \xi^j}, \quad g^{ij} = \mathbf{g}^i \cdot \mathbf{g}^j = (g_{ij})^{-1}$$
The Riemannian volume element is:
$$dV = \sqrt{g} \, d\xi^1 \dots d\xi^d, \quad g = \det(g_{ij})$$

#### Christoffel Symbols and Covariant Derivatives
The Christoffel symbols of the second kind (affine connection coefficients) are:
$$\Gamma_{jk}^i = \frac{1}{2} \sum_{l=1}^d g^{il} \left( \frac{\partial g_{lj}}{\partial \xi^k} + \frac{\partial g_{lk}}{\partial \xi^j} - \frac{\partial g_{jk}}{\partial \xi^l} \right)$$
The covariant derivative of a contravariant vector field $v^i$ is:
$$\nabla_j v^i = \frac{\partial v^i}{\partial \xi^j} + \sum_{k=1}^d \Gamma_{jk}^i v^k$$

#### Coordinate-Invariant Differential Operators
In any coordinate system and dimension $d$, the continuous physical transport operators expand as:
1. **Invariant Gradient of a Scalar Field $\phi$:**
   $$(\nabla \phi)^i = g^{ij} \frac{\partial \phi}{\partial \xi^j}, \quad \|\nabla \phi\|^2 = g^{ij} \frac{\partial \phi}{\partial \xi^i} \frac{\partial \phi}{\partial \xi^j}$$
2. **Invariant Divergence of a Vector Field $\mathbf{v}$:**
   $$\nabla \cdot \mathbf{v} = \frac{1}{\sqrt{g}} \sum_{i=1}^d \frac{\partial}{\partial \xi^i} \left( \sqrt{g} v^i \right)$$
3. **Invariant Laplace-Beltrami Operator ($\nabla^2 \phi$):**
   $$\nabla^2 \phi = \frac{1}{\sqrt{g}} \sum_{i=1}^d \frac{\partial}{\partial \xi^i} \left( \sqrt{g} \sum_{j=1}^d g^{ij} \frac{\partial \phi}{\partial \xi^j} \right)$$
4. **Invariant Convective Derivative ($(\mathbf{v} \cdot \nabla) \mathbf{u}$):**
   $$\left( (\mathbf{v} \cdot \nabla) \mathbf{u} \right)^i = \sum_{j=1}^d v^j \nabla_j u^i = \sum_{j=1}^d v^j \left( \frac{\partial u^i}{\partial \xi^j} + \sum_{k=1}^d \Gamma_{jk}^i u^k \right)$$

#### Explicit Canonical Reductions for 1D, 2D, and 3D Domains

| Dimension & Geometry | Coordinates $\boldsymbol{\xi}$ | Metric Tensor $g_{ij}$ | Volume Element $\sqrt{g}$ | Laplace-Beltrami Operator $\nabla^2 \phi$ |
|---|---|---|---|---|
| **1D Planar Slab** | $x \in [0, L]$ | $[1]$ | $1$ | $\frac{\partial^2 \phi}{\partial x^2}$ |
| **1D Cylindrical Radial** | $r \in [R_i, R_o]$ | $[1]$ | $r$ | $\frac{1}{r} \frac{\partial}{\partial r}\left( r \frac{\partial \phi}{\partial r} \right)$ |
| **1D Spherical Radial** | $r \in [0, R_p]$ | $[1]$ | $r^2$ | $\frac{1}{r^2} \frac{\partial}{\partial r}\left( r^2 \frac{\partial \phi}{\partial r} \right)$ |
| **2D Planar Cartesian** | $(x, y)$ | $\operatorname{diag}(1, 1)$ | $1$ | $\frac{\partial^2 \phi}{\partial x^2} + \frac{\partial^2 \phi}{\partial y^2}$ |
| **2D Axisymmetric** | $(r, z)$ | $\operatorname{diag}(1, 1)$ | $r$ | $\frac{1}{r} \frac{\partial}{\partial r}\left( r \frac{\partial \phi}{\partial r} \right) + \frac{\partial^2 \phi}{\partial z^2}$ |
| **2D Polar Plane** | $(r, \theta)$ | $\operatorname{diag}(1, r^2)$ | $r$ | $\frac{1}{r} \frac{\partial}{\partial r}\left( r \frac{\partial \phi}{\partial r} \right) + \frac{1}{r^2} \frac{\partial^2 \phi}{\partial \theta^2}$ |
| **3D Cartesian** | $(x, y, z)$ | $\operatorname{diag}(1, 1, 1)$ | $1$ | $\frac{\partial^2 \phi}{\partial x^2} + \frac{\partial^2 \phi}{\partial y^2} + \frac{\partial^2 \phi}{\partial z^2}$ |
| **3D Cylindrical** | $(r, \theta, z)$ | $\operatorname{diag}(1, r^2, 1)$ | $r$ | $\frac{1}{r} \frac{\partial}{\partial r}\left( r \frac{\partial \phi}{\partial r} \right) + \frac{1}{r^2} \frac{\partial^2 \phi}{\partial \theta^2} + \frac{\partial^2 \phi}{\partial z^2}$ |
| **3D Spherical** | $(r, \theta, \varphi)$ | $\operatorname{diag}(1, r^2, r^2 \sin^2\theta)$ | $r^2 \sin\theta$ | $\frac{1}{r^2}\frac{\partial}{\partial r}\left(r^2 \frac{\partial \phi}{\partial r}\right) + \frac{1}{r^2 \sin\theta}\frac{\partial}{\partial \theta}\left(\sin\theta \frac{\partial \phi}{\partial \theta}\right) + \frac{1}{r^2 \sin^2\theta}\frac{\partial^2 \phi}{\partial \varphi^2}$ |

##### Geometric Singularity Treatment at Radial Origin ($r = 0$)
In cylindrical and spherical geometries, the metric determinant vanishes at $r = 0$ ($\sqrt{g} = 0$). By physical symmetry, radial flux vanishes at the centerline/center:
$$\left. \frac{\partial \phi}{\partial r} \right|_{r=0} = 0$$
Applying L'Hôpital's rule to the radial Laplace-Beltrami terms:
* **Cylindrical Origin ($r \to 0$):**
  $$\lim_{r \to 0} \frac{1}{r} \frac{\partial \phi}{\partial r} = \left. \frac{\partial^2 \phi}{\partial r^2} \right|_{r=0} \implies \left. \nabla^2 \phi \right|_{r=0} = 2 \left. \frac{\partial^2 \phi}{\partial r^2} \right|_{r=0} + \left. \frac{\partial^2 \phi}{\partial z^2} \right|_{r=0}$$
* **Spherical Pellet Center ($r \to 0$):**
  $$\lim_{r \to 0} \frac{2}{r} \frac{\partial \phi}{\partial r} = 2 \left. \frac{\partial^2 \phi}{\partial r^2} \right|_{r=0} \implies \left. \nabla^2 \phi \right|_{r=0} = 3 \left. \frac{\partial^2 \phi}{\partial r^2} \right|_{r=0}$$
This algebraic regularization guarantees non-singular finite volume stencils without ad-hoc numerical clipping.

---

### 8.3 Mathematical Theory of Generalized Meshes: Cartesian, Hexagonal, Simplicial, and Polyhedral

Spatial discretization requires tiling the continuous manifold $\mathcal{M}$ into a discrete collection of control volumes $\{\Omega_P\}_{P=1}^{N_{\text{cells}}}$ satisfying:
$$\bigcup_{P=1}^{N_{\text{cells}}} \bar{\Omega}_P = \bar{\mathcal{M}}, \quad \Omega_P \cap \Omega_Q = \emptyset \quad (\forall P \ne Q)$$

```
     1. CARTESIAN / QUAD              2. HEXAGONAL HONEYCOMB             3. GENERAL POLYHEDRAL
         ┌─────────┬─────────┐                 / \     / \                   ┌─────────┐
         │         │         │               /     \ /     \                /           \
         │    P    │    E    │              |   P   |   E   |              /      P      \
         │    •    │    •    │              |   •   │   •   |             │       •       │
         │         │         │               \     / \     /              \             /
         └─────────┴─────────┘                 \ /     \ /                 └───────────┘
```

#### 8.3.1 Structured Cartesian and Curvilinear Orthogonal Meshes
On orthogonal Cartesian grids, cell faces are aligned with coordinate planes.
* **Cell Volume:** $V_P = \Delta x \, \Delta y \, \Delta z$ (in 3D) or $\Delta x \, \Delta y$ (in 2D).
* **Orthogonality Property:** The centroid connector vector $\mathbf{d}_{PE} = \mathbf{x}_E - \mathbf{x}_P$ is strictly parallel to the face area vector $\mathbf{A}_f$:
  $$\mathbf{d}_{PE} \times \mathbf{A}_f = \mathbf{0} \implies \frac{\mathbf{A}_f}{\|\mathbf{d}_{PE}\|} = \frac{A_f}{d_{PE}} \mathbf{n}_f$$
  Non-orthogonal cross-diffusion errors are identically zero.
* **Bandwidth:** Generates regular banded Toeplitz block matrices (tridiagonal in 1D, pentadiagonal in 2D, heptadiagonal in 3D), optimized for alternating direction implicit (ADI) or line-SOR solvers.

#### 8.3.2 Hexagonal Honeycomb Meshes and Voronoi Dual Tessellations
Hexagonal meshes in 2D (and extruded prism honeycomb in 3D) offer distinct mathematical advantages over standard square Cartesian grids in transport modeling:

##### 1. Geometry of the Regular Hexagonal Cell
For a regular hexagon with edge length $s$:
* **Area:** $A_{\text{hex}} = \frac{3 \sqrt{3}}{2} s^2 \approx 2.598 s^2$
* **Perimeter:** $P_{\text{hex}} = 6 s$
* **Isoperimetric Quotient:** $\mathcal{Q} = \frac{4 \pi A}{P^2} = \frac{\pi \sqrt{3}}{6} \approx 0.9069$ (compared to $\frac{\pi}{4} \approx 0.7854$ for a square). Hexagons minimize perimeter-to-area ratio among all regular space-filling polygons, minimizing numerical boundary dissipation.
* **Neighbors:** Exactly 6 adjacent neighboring cells with identical centroid-to-centroid distance:
  $$d_{PE} = \sqrt{3} s \quad \forall E \in \mathcal{N}(P)$$

##### 2. Perfect Six-Fold Spatial Isotropy
On Cartesian square grids, the distance to diagonal neighbors ($\sqrt{2} \Delta x$) differs by $41.4\%$ from face neighbors ($\Delta x$), introducing artificial grid-alignment anisotropy in wave propagation and diffusive spreading.
On regular hexagonal grids, the orientation dyadic of face normals satisfies exact second-order isotropy:
$$\sum_{k=1}^6 \mathbf{n}_k \otimes \mathbf{n}_k = 3 \mathbf{I}$$
where $\mathbf{I}$ is the $2 \times 2$ identity tensor. Consequently, numerical diffusion and dispersion errors are completely invariant to spatial coordinate rotation.

##### 3. Voronoi Dual Tessellation and Zero Cross-Diffusion
Let $\{\mathbf{x}_i\}_{i=1}^N$ be a set of generator seed points in $\mathbb{R}^d$. The **Voronoi cell** $\mathcal{V}_i$ associated with seed $\mathbf{x}_i$ is defined by:
$$\mathcal{V}_i = \left\{ \mathbf{x} \in \mathbb{R}^d : \|\mathbf{x} - \mathbf{x}_i\| \le \|\mathbf{x} - \mathbf{x}_j\| \quad \forall j \ne i \right\}$$
* **Theorem (Orthogonal Bisector Property):** *The interface facet $f_{ij} = \mathcal{V}_i \cap \mathcal{V}_j$ between two adjacent Voronoi cells lies in the perpendicular bisector hyperplane of the segment $\overline{\mathbf{x}_i \mathbf{x}_j}$.*
* **Mathematical Consequence:**
  $$\mathbf{d}_{ij} \parallel \mathbf{n}_{f_{ij}} \implies \mathbf{d}_{ij} \cdot \mathbf{n}_{f_{ij}} = \|\mathbf{d}_{ij}\|$$
  The non-orthogonality angle $\theta = \arccos\left( \frac{\mathbf{d}_{ij} \cdot \mathbf{n}_f}{\|\mathbf{d}_{ij}\|} \right) \equiv 0$.
  Therefore, on Voronoi grids, the non-orthogonal cross-diffusion correction $\mathbf{k}_f \equiv \mathbf{0}$, eliminating secondary gradient calculations and guaranteeing unconditional diagonal dominance of the diffusion stiffness matrix.

#### 8.3.3 Unstructured Simplicial Meshes: Triangles (2D) and Tetrahedra (3D)
Simplicial meshes conform to arbitrary, complex curved boundaries.
* A triangle in 2D is defined by 3 vertices; a tetrahedron in 3D is defined by 4 vertices.
* **Volume:** $V_{\text{tet}} = \frac{1}{6} \left| \det\left[ \mathbf{x}_1 - \mathbf{x}_4, \mathbf{x}_2 - \mathbf{x}_4, \mathbf{x}_3 - \mathbf{x}_4 \right] \right|$.
* **Circumcenter vs. Centroid:** In Delaunay simplicial meshes, if an obtuse angle exists, the circumcenter lies outside the simplex, forcing the use of the centroid ($\mathbf{x}_P = \frac{1}{4} \sum_{k=1}^4 \mathbf{x}_k$). This introduces non-orthogonality ($\mathbf{d}_{PE} \not\parallel \mathbf{n}_f$), requiring explicit non-orthogonal gradient corrections.

#### 8.3.4 Boundary-Layer Prismatic Elements (Pentahedra)
Near solid walls in high-Péclet or high-Reynolds flows, viscous and thermal boundary layers exhibit extreme anisotropy: gradients normal to the wall ($\frac{\partial \phi}{\partial n}$) are orders of magnitude larger than tangential gradients ($\frac{\partial \phi}{\partial s}$).
* **Prism Geometry:** Triangular base in the tangential plane extruded in the normal direction.
* **Aspect Ratio:** Allows high aspect ratios ($AR = \Delta s / \Delta n \sim 100 - 1000$) near walls without cell skewness errors, maintaining structured 1D-like resolution normal to the boundary while seamlessly coupling to isotropic tetrahedral or polyhedral meshes in the bulk.

#### 8.3.5 Generalized Unstructured Polyhedral Cell Mathematics
For arbitrary polyhedral control volumes $\Omega_P$ bounded by $N_f$ planar polygonal faces with $N_v$ vertices:

##### 1. Face Area Vector and Face Centroid
For an arbitrary planar polygonal face $f$ with ordered vertices $\mathbf{v}_1, \dots, \mathbf{v}_{N_v}$:
$$\mathbf{A}_f = A_f \mathbf{n}_f = \frac{1}{2} \sum_{k=1}^{N_v} (\mathbf{v}_k - \mathbf{v}_0) \times (\mathbf{v}_{k+1} - \mathbf{v}_0)$$
where $\mathbf{v}_{N_v+1} \equiv \mathbf{v}_1$, and $\mathbf{v}_0$ is any reference point on the face plane (e.g. vertex average $\mathbf{v}_0 = \frac{1}{N_v} \sum \mathbf{v}_k$).
The **face centroid** $\mathbf{x}_f$ is:
$$\mathbf{x}_f = \frac{1}{3 A_f} \sum_{k=1}^{N_v} A_{\Delta k} (\mathbf{v}_k + \mathbf{v}_{k+1} + \mathbf{v}_0)$$
where $A_{\Delta k} = \frac{1}{2} \| (\mathbf{v}_k - \mathbf{v}_0) \times (\mathbf{v}_{k+1} - \mathbf{v}_0) \|$.

##### 2. Cell Volume via Divergence Theorem
Applying the Gauss divergence theorem to the identity $\nabla \cdot \mathbf{x} = d$ in $\mathbb{R}^d$:
$$\int_{\Omega_P} (\nabla \cdot \mathbf{x}) \, dV = d \, V_P = \oint_{\partial \Omega_P} \mathbf{x} \cdot \mathbf{n} \, dA = \sum_{f \in \mathcal{F}(P)} \int_f (\mathbf{x} \cdot \mathbf{n}_f) \, dA$$
Since $\mathbf{n}_f$ is constant over planar face $f$:
$$V_P = \frac{1}{d} \sum_{f \in \mathcal{F}(P)} \mathbf{x}_f \cdot \mathbf{A}_f$$

##### 3. Cell Centroid
Decomposing the polyhedron into sub-pyramids connecting the cell centroid to face centroids:
$$\mathbf{x}_P = \frac{1}{d + 1} \frac{1}{V_P} \sum_{f \in \mathcal{F}(P)} (\mathbf{x}_f \cdot \mathbf{A}_f) \left( \frac{d}{d + 1} \mathbf{x}_f + \frac{1}{d + 1} \mathbf{x}_0 \right)$$

#### 8.3.6 Secondary Gradients, Over-Relaxed Non-Orthogonal Corrections, and Skewness Limiters
On arbitrary polyhedral meshes, two geometric imperfections must be corrected to maintain second-order accuracy:

```
                         Face f with area vector A_f
                                     │
           Cell P                    │ f' (Line Intersection)    Cell E
             •───────────────────────┼───────►                     •
            x_P                      │\                           x_E
                                     │ \ δ_skew
                                     │  ▼
                                     │   • x_f (Face Centroid)
                                     │
                               d_PE = x_E - x_P
```

##### 1. Non-Orthogonal Diffusion Decomposition
When $\mathbf{d}_{PE} = \mathbf{x}_E - \mathbf{x}_P$ is not parallel to $\mathbf{A}_f$, the face area vector is split into an orthogonal component $\boldsymbol{\Delta}_{PE}$ and a cross-diffusion component $\mathbf{k}_f$:
$$\mathbf{A}_f = \boldsymbol{\Delta}_{PE} + \mathbf{k}_f$$
* **Over-Relaxed Formulation (Recommended for Stability):**
  $$\boldsymbol{\Delta}_{PE} = \frac{\mathbf{A}_f \cdot \mathbf{A}_f}{\mathbf{d}_{PE} \cdot \mathbf{A}_f} \mathbf{d}_{PE}, \quad \mathbf{k}_f = \mathbf{A}_f - \boldsymbol{\Delta}_{PE}$$
  This ensures that $\boldsymbol{\Delta}_{PE} \cdot \mathbf{n}_f \ge \|\mathbf{A}_f\|$, maximizing the implicit diagonal contribution and guaranteeing robust M-matrix convergence in iterative solvers even for severe mesh non-orthogonality ($> 70^\circ$).

##### 2. Face Skewness Correction
When the line segment connecting centroids $\overline{\mathbf{x}_P \mathbf{x}_E}$ does not intersect face $f$ at its geometric centroid $\mathbf{x}_f$, face interpolation based solely on $\overline{\mathbf{x}_P \mathbf{x}_E}$ introduces first-order geometric skewness errors.
Let $\mathbf{x}_{f'}$ be the intersection point of $\overline{\mathbf{x}_P \mathbf{x}_E}$ with the face plane. The **skewness displacement vector** is:
$$\boldsymbol{\delta}_{\text{skew}} = \mathbf{x}_f - \mathbf{x}_{f'}$$
The face value $\phi_f$ is reconstructed to second-order accuracy via:
$$\phi_f = \phi_{f'} + \boldsymbol{\delta}_{\text{skew}} \cdot (\overline{\nabla \phi})_f$$
where $\phi_{f'}$ is linearly interpolated between $P$ and $E$, and $(\overline{\nabla \phi})_f$ is the cell-averaged gradient reconstructed via Green-Gauss or least-squares stencils.

---

### 8.4 The Multiphysics Coupling Framework: 4-Way Balance Interactions and Conjugate Transports

A true multiphysics continuum integrates **Matter, Momentum, Energy, and Thermodynamics** into a tightly coupled conservation system.

```
                         ┌─────────────────────────────┐
                         │       THERMODYNAMICS        │
                         │  (Engine of Engines / EOS)  │
                         └──────────────┬──────────────┘
                                        │ (T, P, z) ──► Phase Split, μ_i, ρ, c_p, h
                 ┌──────────────────────┼──────────────────────┐
                 │                      │                      │
                 ▼                      ▼                      ▼
        ┌────────────────┐    Viscous Work / Bouyancy    ┌────────────────┐
        │    MOMENTUM    │ ◄───────────────────────────► │     ENERGY     │
        │(Navier-Stokes) │                               │(Total Enthalpy)│
        └───────┬────────┘                               └────────┬───────┘
                │            Reaction Heat / Arrhenius            │
                └───────────────► ┌──────────┐ ◄──────────────────┘
                                  │  MATTER  │
                                  │ (Species)│
                                  └──────────┘
```

#### 8.4.1 Comprehensive Multiphysics Field Equation System
In conservative Eulerian differential form, the coupled system is:
$$\frac{\partial \mathbf{U}}{\partial t} + \nabla \cdot \mathbf{F}_{\text{conv}}(\mathbf{U}) = \nabla \cdot \mathbf{F}_{\text{diff}}(\mathbf{U}, \nabla \mathbf{U}) + \mathbf{S}(\mathbf{U})$$
where the global state vector $\mathbf{U} \in \mathbb{R}^{N_c + d + 1}$ is:
$$\mathbf{U} = \begin{bmatrix} \rho_1 \\ \vdots \\ \rho_{N_c} \\ \rho \mathbf{v} \\ \rho E \end{bmatrix}, \quad \rho = \sum_{i=1}^{N_c} \rho_i, \quad E = u + \frac{1}{2}\|\mathbf{v}\|^2$$

#### 8.4.2 Matter $\leftrightarrow$ Momentum Coupling
1. **Variable Fluid Properties:** Mixture density $\rho(\mathbf{z}, T, P)$ and dynamic viscosity $\mu(\mathbf{z}, T)$ are direct functions of species local composition:
   $$\rho = \left( \sum_{i=1}^{N_c} \frac{w_i}{\rho_i(T, P)} \right)^{-1}, \quad \mu = \mu_{\text{UNIFAC}}(T, \mathbf{x})$$
2. **Brinkman-Forchheimer Porous Resistance (Packed Beds & Catalyst Pellets):**
   In catalytic fixed beds or packed distillation zones, the momentum balance incorporates macroscopic drag:
   $$\mathbf{S}_{\text{mom}} = -\frac{\mu}{\mathbf{K}_{\text{perm}}} \mathbf{v} - \rho \mathbf{C}_F |\mathbf{v}| \mathbf{v}$$
   where $\mathbf{K}_{\text{perm}}$ is the permeability tensor and $\mathbf{C}_F$ is the Forchheimer inertial drag coefficient.
3. **Solutal and Thermal Buoyancy (Natural Convection):**
   Density variations drive the momentum source via the generalized gravity body force:
   $$\rho \mathbf{g} = \rho_0 \left[ 1 - \beta_T (T - T_0) - \sum_{i=1}^{N_c} \beta_{c,i} (c_i - c_{i,0}) \right] \mathbf{g}$$
   where $\beta_T = -\frac{1}{\rho_0} \left( \frac{\partial \rho}{\partial T} \right)$ is thermal expansion and $\beta_{c,i} = \frac{1}{\rho_0} \left( \frac{\partial \rho}{\partial c_i} \right)$ is solutal expansion.

#### 8.4.3 Matter $\leftrightarrow$ Energy Coupling
1. **Chemical Reaction Enthalpy Source:**
   Heterogeneous and homogeneous reactions generate or consume thermal energy:
   $$\dot{S}_{\text{thermal}} = \sum_{r=1}^{N_{\text{rxn}}} \left( -\Delta H_{\text{rxn},r}(T) \right) r_r(T, \mathbf{c})$$
2. **Species Interdiffusion Enthalpy Flux:**
   Multicomponent diffusive fluxes $\mathbf{j}_i$ transport their respective partial molar enthalpies:
   $$\mathbf{q}_{\text{interdiff}} = \sum_{i=1}^{N_c} \mathbf{j}_i \bar{h}_i(T, P, \mathbf{x})$$
   Omitting this term in non-isothermal multicomponent diffusion creates up to $15\%$ error in interface temperature predictions.
3. **The Dufour Effect (Diffusion-Thermo Effect):**
   Concentration gradients directly induce conductive heat fluxes via the Onsager cross-transport reciprocity relations:
   $$\mathbf{q}_{\text{Dufour}} = R T \sum_{i=1}^{N_c} \sum_{j=1}^{N_c} \frac{x_i \mathcal{D}_{ij}^T}{c_t M_i M_j} \nabla x_j$$
   where $\mathcal{D}_{ij}^T$ is the thermal diffusion coefficient tensor.
4. **Arrhenius Temperature Feedback:**
   Reaction rates depend exponentially on temperature ($r \propto \exp(-E_a/RT)$), creating steep non-linear feedback loops that lead to ignition, extinction, and thermal runaway.

#### 8.4.4 Momentum $\leftrightarrow$ Energy Coupling
1. **Viscous Dissipation Function ($\Phi_v$):**
   Mechanical shear stresses are converted irreversibly into internal thermal energy:
   $$\Phi_v = \boldsymbol{\tau} : \nabla \mathbf{v} = 2 \mu \mathbf{D} : \mathbf{D} - \frac{2}{3} \mu (\nabla \cdot \mathbf{v})^2 \ge 0$$
   where $\mathbf{D} = \frac{1}{2}(\nabla \mathbf{v} + (\nabla \mathbf{v})^T)$ is the strain rate tensor.
2. **Compressible Pressure Work:**
   Expansion and compression work exchange energy between kinetic and internal modes:
   $$\dot{W}_{\text{comp}} = -P (\nabla \cdot \mathbf{v})$$
3. **Temperature-Dependent Rheology:**
   Viscosity exhibits exponential decay with temperature:
   $$\mu(T) = \mu_0 \exp\left[ B \left( \frac{1}{T} - \frac{1}{T_0} \right) \right]$$
   Coupled with viscous dissipation, this induces hydrodynamic thermoviscous runaway in high-shear channels.

#### 8.4.5 Thermodynamic Closure Coupling (The Engine of Engines)
At every cell centroid $\mathbf{x}_P$ and time step $t$, the conservative state $\mathbf{U}_P = (\rho_{1,P}, \dots, \rho_{N_c,P}, \rho_P \mathbf{v}_P, \rho_P E_P)$ must be converted into physical intensive state variables:
1. **Internal Energy Extraction:**
   $$\rho_P u_P = \rho_P E_P - \frac{1}{2} \rho_P \|\mathbf{v}_P\|^2$$
2. **State Inversion via UV Flash:**
   Solving the non-linear thermodynamic inversion:
   $$\begin{cases} u(\mathbf{z}_P, T_P, v_P) - u_P = 0 \\ v(\mathbf{z}_P, T_P, P_P) - \frac{1}{\rho_P} = 0 \end{cases} \implies (T_P, P_P, \alpha_V, \mathbf{x}_P, \mathbf{y}_P)$$
3. **Phase Discovery and Stability:**
   The Michelsen Tangent Plane Distance ($TPD$, Section 3.2) is evaluated at $\mathbf{x}_P$. If $TPD < 0$, a phase split occurs, partitioning cell volume $V_P$ into vapor and liquid sub-fractions with conjugate interface mass transfer.

#### 8.4.6 Conjugate Multi-Domain Interfaces
In multi-domain simulations (such as a fluid stream in contact with a solid pipe wall or catalyst carrier), conservation across the shared boundary $\Gamma_{fs}$ is strictly enforced:
* **Thermal Continuity:**
  $$T_f|_{\Gamma_{fs}} = T_s|_{\Gamma_{fs}}, \quad -k_f \left. \frac{\partial T_f}{\partial n} \right|_{\Gamma_{fs}} = -k_s \left. \frac{\partial T_s}{\partial n} \right|_{\Gamma_{fs}}$$
* **Species Jump with Surface Catalysis:**
  $$-(\mathbf{j}_i \cdot \mathbf{n})|_{\Gamma_{fs}} = r_{i,\text{surface}}(T_s, \mathbf{c}_s)$$
* **Moving Phase Fronts (Stefan Condition):**
  $$\llbracket \rho (\mathbf{v} - \mathbf{w}_I) \cdot \mathbf{n} \rrbracket = 0, \quad \llbracket \rho (\mathbf{v} - \mathbf{w}_I) \cdot \mathbf{n} h + \mathbf{q} \cdot \mathbf{n} \rrbracket = 0$$
  where $\mathbf{w}_I$ is the physical interface velocity.

---

### 8.5 Rigorous Cell-Centered Finite Volume Method (FVM) on Arbitrary Grids

Let $\Omega_P$ be an arbitrary polyhedral control volume with centroid $\mathbf{x}_P$ and volume $V_P = \int_{\Omega_P} dV$. The boundary $\partial \Omega_P$ is partitioned into planar faces $f \in \mathcal{F}(P)$, each having surface area $A_f$, outward unit normal vector $\mathbf{n}_f$, and surface area vector $\mathbf{A}_f = A_f \mathbf{n}_f$.

Integrating the general multiphysics transport equation over $\Omega_P$:
$$\frac{d}{dt} \int_{\Omega_P} \phi \, dV + \oint_{\partial \Omega_P} \left( \phi \mathbf{v} - \boldsymbol{\Gamma} \nabla \phi \right) \cdot \mathbf{n} \, dA = \int_{\Omega_P} S(\phi) \, dV$$
Defining the cell-average state $\bar{\phi}_P = \frac{1}{V_P} \int_{\Omega_P} \phi \, dV$, Gauss's divergence theorem yields:
$$V_P \frac{d\bar{\phi}_P}{dt} + \sum_{f \in \mathcal{F}(P)} \mathcal{F}_f = V_P \bar{S}_P$$
where the total numerical face flux is partitioned into convective and diffusive parts:
$$\mathcal{F}_f = \mathcal{F}_{f, \text{conv}} + \mathcal{F}_{f, \text{diff}}$$

#### Convective Face Flux
$$\mathcal{F}_{f, \text{conv}} = \dot{m}_f \phi_f$$
where $\dot{m}_f = \rho_f (\mathbf{v}_f \cdot \mathbf{A}_f)$ is the mass flow rate through face $f$, and $\phi_f$ is reconstructed using high-resolution monotonic limiters.

#### Diffusive Face Flux with Over-Relaxed Non-Orthogonal Correction
$$\mathcal{F}_{f, \text{diff}} = -\Gamma_f \left[ \frac{\phi_E - \phi_P}{\|\mathbf{d}_{PE}\|} \frac{\mathbf{A}_f \cdot \mathbf{A}_f}{\mathbf{d}_{PE} \cdot \mathbf{n}_f} + \mathbf{k}_f \cdot (\overline{\nabla \phi})_f \right]$$
where the cell-centroid gradients $(\overline{\nabla \phi})_f = \frac{1}{2}(\nabla \phi_P + \nabla \phi_E)$ are computed via the Green-Gauss theorem on arbitrary polyhedra:
$$\nabla \phi_P = \frac{1}{V_P} \sum_{f \in \mathcal{F}(P)} \phi_f \mathbf{A}_f$$

---

### 8.6 High-Resolution Monotonic TVD Schemes and Multidimensional Flux Limiters

Linear spatial discretization schemes of second or higher order inevitably produce unphysical oscillations near sharp fronts, violating the physical bounds of chemical concentrations ($c_i \ge 0$) and absolute temperatures ($T > 0$).

#### Godunov's Barrier Theorem
**Theorem (Godunov, 1959):** *No linear numerical convection scheme of formal accuracy order higher than one can be monotonicity-preserving.*

To achieve second-order accuracy in smooth regions while strictly preventing spurious oscillations near reaction fronts and shocks, the proposal mandates **Total Variation Diminishing (TVD)** schemes with non-linear flux limiters.

#### Total Variation and Sweby's Monotonicity Region
The total variation of a spatial discrete field $\boldsymbol{\phi}$ is defined by:
$$TV(\boldsymbol{\phi}) = \sum_{i} |\phi_{i+1} - \phi_i|$$
A scheme is TVD if and only if $TV(\boldsymbol{\phi}^{n+1}) \le TV(\boldsymbol{\phi}^n)$.

Let $r_f$ be the ratio of consecutive gradients across face $f$ along the upwind flow direction:
$$r_f = \begin{cases} \displaystyle \frac{\phi_P - \phi_W}{\phi_E - \phi_P}, & \text{if } \dot{m}_f > 0 \\[1em] \displaystyle \frac{\phi_{EE} - \phi_E}{\phi_E - \phi_P}, & \text{if } \dot{m}_f < 0 \end{cases}$$
The face value $\phi_f$ is reconstructed via:
$$\phi_f = \phi_{\text{upwind}} + \frac{1}{2} \psi(r_f) (\phi_{\text{downwind}} - \phi_{\text{upwind}})$$
where $\psi(r)$ is the **flux limiter function**.

A scheme is second-order accurate and strictly TVD if $\psi(r)$ lies within **Sweby's monotonicity envelope**:
$$\psi(r) \le 2r, \quad \psi(r) \le 2, \quad \psi(r) \ge 0, \quad \forall r \ge 0; \quad \psi(r) = 0 \quad (\forall r < 0)$$

#### Multidimensional Gradient Ratio on Unstructured Meshes
On arbitrary polyhedral meshes, the consecutive gradient ratio $r_f$ is generalized via projection of the upwind cell gradient:
$$r_f = \frac{2 (\nabla \phi_U) \cdot \mathbf{d}_{PE}}{\phi_E - \phi_P} - 1$$
where $U$ denotes the upwind cell centroid.

| Limiter Name | Functional Form $\psi(r)$ | Properties & Application Regimes |
|---|---|---|
| **Minmod** | $\max\left( 0, \min(1, r) \right)$ | Most diffusive TVD limiter; guaranteed monotone; ideal for rugged initial transients. |
| **Superbee (Roe)** | $\max\left( 0, \min(2r, 1), \min(r, 2) \right)$ | Over-compressive; sharpest resolution for contact discontinuities and phase fronts. |
| **Van Leer** | $\displaystyle \frac{r + |r|}{1 + |r|}$ | Smooth, continuously differentiable limiter; avoids derivative kinks during Newton solves. |
| **Koren** | $\max\left( 0, \min\left( 2r, \frac{1 + 2r}{3}, 2 \right) \right)$ | Third-order accurate for smooth solutions; optimal for catalytic fixed-bed reactors. |
| **Monotonized Central (MC)** | $\max\left( 0, \min\left( 2r, \frac{1+r}{2}, 2 \right) \right)$ | Symmetric limiter balancing steep gradient capture with minimal dissipation. |

---

### 8.7 Boundary Conditions and Conjugate Phase Interface Jumps

Boundary conditions on boundary faces $f_b \subset \partial \mathcal{M}$ are enforced directly into the discrete flux balance without modifying interior volume equations.

#### 1. Dirichlet Boundary (Specified Value)
$$\phi|_{\Gamma_D} = \phi_{\text{spec}} \implies \phi_{f_b} = \phi_{\text{spec}}$$
The boundary diffusive flux evaluates as:
$$\mathcal{F}_{f_b, \text{diff}} = -\Gamma_{f_b} \frac{\phi_{\text{spec}} - \bar{\phi}_P}{\delta n_{Pf_b}} A_{f_b}$$
where $\delta n_{Pf_b} = (\mathbf{x}_{f_b} - \mathbf{x}_P) \cdot \mathbf{n}_{f_b}$ is the normal distance from cell centroid $P$ to face $f_b$.

#### 2. Neumann Boundary (Specified Flux)
$$-\left. \boldsymbol{\Gamma} \nabla \phi \cdot \mathbf{n} \right|_{\Gamma_N} = q_{\text{spec}}''$$
The diffusive flux is directly substituted:
$$\mathcal{F}_{f_b, \text{diff}} = q_{\text{spec}}'' A_{f_b}$$
For an adiabatic or impermeable wall, $q_{\text{spec}}'' = 0 \implies \mathcal{F}_{f_b, \text{diff}} = 0$.

#### 3. Robin Boundary (Convective Mass / Heat Transfer)
$$-\left. \boldsymbol{\Gamma} \nabla \phi \cdot \mathbf{n} \right|_{\Gamma_R} = h_{\text{trans}} (\phi_{f_b} - \phi_\infty)$$
Equating numerical interior diffusion to external transfer yields the boundary face state:
$$\phi_{f_b} = \frac{\frac{\Gamma_{f_b}}{\delta n_{Pf_b}} \bar{\phi}_P + h_{\text{trans}} \phi_\infty}{\frac{\Gamma_{f_b}}{\delta n_{Pf_b}} + h_{\text{trans}}}$$

---

### 8.8 Adaptive Mesh Refinement (AMR) on Generalized Mesh Topologies

In multi-phase flow and chemical fronts, steep spatial gradients occupy a tiny fraction of the spatial domain. To optimize computational resources, **Adaptive Mesh Refinement (AMR)** dynamically refines the grid where gradients are severe and coarsens where solutions are smooth.

```
       UNREFINED CELL                          QUADTREE BISECTION (2D)
     ┌─────────────────┐                         ┌────────┬────────┐
     │                 │                         │        │        │
     │                 │   Refine (η_P > θ_r)    ├────────┼────────┤
     │        P        │  ────────────────────►  │        │        │
     │                 │                         └────────┴────────┘
     └─────────────────┘                         4 Children Cells (2^d)
```

#### Curvature Error Estimator
For each cell $P$, the local truncation error indicator $\eta_P$ is computed:
$$\eta_P = h_P^2 \frac{\|\nabla^2 \bar{\phi}_P\|_2}{\max\left( \|\nabla \bar{\phi}_P\|_2 \cdot h_P, \; \epsilon_0 |\bar{\phi}_P| \right)}$$
where $h_P = (V_P)^{1/d}$ is the cell characteristic length.
* **Refinement Criterion:** If $\eta_P > \theta_{\text{refine}} = 0.05$, cell $P$ is bisected into $2^d$ children cells ($4$ for 2D quads, $8$ for 3D hexahedra, or edge-bisection for triangles/tetrahedra).
* **Coarsening Criterion:** If all sibling children have $\eta_c < \theta_{\text{coarsen}} = 0.01$, they are merged back into the parent cell.
* **2:1 Ratio Restriction:** Adjacent cells across any face cannot differ by more than one refinement level, preventing grid distortion.

#### Telescopic Conservative Prolongation and Restriction
Mass conservation during mesh restructuring is preserved to machine precision:
* **Restriction (Coarsening):** The parent cell average is the exact volume-weighted sum of children:
  $$\bar{\phi}_{\text{parent}} = \frac{1}{V_{\text{parent}}} \sum_{c=1}^{2^d} V_c \bar{\phi}_c$$
* **Prolongation (Refinement):** Child cell values are interpolated using the parent gradient:
  $$\bar{\phi}_c = \bar{\phi}_{\text{parent}} + \nabla \phi_{\text{parent}} \cdot (\mathbf{x}_c - \mathbf{x}_{\text{parent}})$$
  Since $\sum_c V_c (\mathbf{x}_c - \mathbf{x}_{\text{parent}}) = \mathbf{0}$, $\sum_c V_c \bar{\phi}_c \equiv V_{\text{parent}} \bar{\phi}_{\text{parent}}$ exactly.

---

### 8.9 Semi-Discrete DAE Assembly, Monolithic vs. Partitioned Structuring, and Block Solvers

Applying FVM spatial discretization to all $N_{\text{cells}}$ control volumes converts the continuum PDEs into a coupled semi-discrete system of Differential-Algebraic Equations:
$$\mathbf{M}_{\text{spatial}} \frac{d\mathbf{Y}}{dt} = \mathbf{F}_{\text{spatial}}(t, \mathbf{Y})$$
where the global state vector is:
$$\mathbf{Y}(t) = \begin{bmatrix} \bar{\mathbf{y}}_1(t) \\ \vdots \\ \bar{\mathbf{y}}_{N_{\text{cells}}}(t) \end{bmatrix} \in \mathbb{R}^{N_{\text{cells}} \cdot N_v}$$
where $N_v = N_c + d + 1$ is the number of field variables per cell.

#### Sparse Block Jacobian Structure
The system Jacobian matrix $\mathbf{J} = \frac{\partial \mathbf{F}_{\text{spatial}}}{\partial \mathbf{Y}}$ has a block-sparse structure:
$$\mathbf{J}_{P, E} = \begin{cases} \displaystyle \frac{\partial \mathbf{F}_P}{\partial \mathbf{y}_P}, & \text{if } P = E \quad (\text{Diagonal Block } N_v \times N_v) \\[1em] \displaystyle \frac{\partial \mathbf{F}_P}{\partial \mathbf{y}_E}, & \text{if } E \in \mathcal{N}(P) \quad (\text{Off-Diagonal Block } N_v \times N_v) \\[1em] \mathbf{0}, & \text{otherwise} \end{cases}$$

#### Monolithic vs. Segregated Multi-Physics Strategies
1. **Monolithic Fully-Coupled Strategy (Recommended for Stiff Reactive Fronts):**
   Solves the complete coupled $(N_{\text{cells}} \cdot N_v) \times (N_{\text{cells}} \cdot N_v)$ Newton system:
   $$\left[ \mathbf{M}_{\text{spatial}} - \gamma h \mathbf{J} \right] \Delta \mathbf{Y}^{(m)} = -\mathbf{R}^{(m)}$$
   via preconditioned Krylov methods (GMRES or BiCGSTAB) accelerated with **Algebraic Multigrid (AMG)** or Block-Incomplete LU ($\text{ILU}(0)$) preconditioners.
2. **Segregated Partitioned Strategy (Recommended for Large 3D Grids):**
   Splits the system into sequentially solved physics blocks (PISO/SIMPLE for Momentum $\to$ Species Transport $\to$ Energy $\to$ Local Flash Closure) with outer Picard iterations until convergence.

---

### 8.10 Spatial Verification: Method of Manufactured Solutions (MMS) for 1D, 2D, and 3D Multiphysics

To verify the mathematical correctness and spatial convergence order of the spatial discretization engine independently of physical experimental error, the platform implements the **Method of Manufactured Solutions (MMS)**.

#### Manufactured Analytic Continuum Solutions
Smooth synthetic test solutions are prescribed across the continuous domain $\mathcal{M}$:
* **1D Verification Field:**
  $$\phi_{\text{MMS}}(x, t) = \phi_0 + \phi_1 \sin\left( \frac{\pi x}{L} \right) \exp\left( -\frac{t}{\tau_0} \right)$$
* **2D Verification Field:**
  $$\phi_{\text{MMS}}(x, y, t) = \phi_0 + \phi_1 \sin\left( \frac{\pi x}{L_x} \right) \cos\left( \frac{\pi y}{L_y} \right) \exp\left( -\frac{t}{\tau_0} \right)$$
* **3D Verification Field:**
  $$\phi_{\text{MMS}}(x, y, z, t) = \phi_0 + \phi_1 \sin\left( \frac{\pi x}{L_x} \right) \sin\left( \frac{\pi y}{L_y} \right) \cos\left( \frac{\pi z}{L_z} \right) \exp\left( -\frac{t}{\tau_0} \right)$$

#### Analytic Source Term Injection
Operating the continuum differential operator on the manufactured solution yields the analytical source term:
$$S_{\text{MMS}}(\mathbf{x}, t) \equiv \frac{\partial \phi_{\text{MMS}}}{\partial t} + \nabla \cdot (\phi_{\text{MMS}} \mathbf{v}) - \nabla \cdot (\boldsymbol{\Gamma} \nabla \phi_{\text{MMS}}) + R(\phi_{\text{MMS}})$$
$S_{\text{MMS}}$ is evaluated via symbolic algebra and injected into the FVM right-hand side.

#### Spatial Order of Convergence Certification
The semi-discrete system is solved on a sequence of systematically refined meshes with grid spacings $h_1 > h_2 > h_3 > h_4$ (refinement ratio $r = h_k / h_{k+1} = 2$).
The discrete spatial error norms are:
$$E_{L_1}(h) = \frac{1}{V_{\text{tot}}} \sum_{P=1}^{N_{\text{cells}}} V_P |\bar{\phi}_P - \phi_{\text{MMS}}(\mathbf{x}_P)|$$
$$E_{L_2}(h) = \sqrt{\frac{1}{V_{\text{tot}}} \sum_{P=1}^{N_{\text{cells}}} V_P |\bar{\phi}_P - \phi_{\text{MMS}}(\mathbf{x}_P)|^2}$$
$$E_{L_\infty}(h) = \max_{1 \le P \le N_{\text{cells}}} |\bar{\phi}_P - \phi_{\text{MMS}}(\mathbf{x}_P)|$$

The **observed spatial convergence order** is:
$$p_{\text{obs}} = \frac{\ln\left( E(h_k) / E(h_{k+1}) \right)}{\ln(2)}$$
The spatial discretization engine is accepted if and only if:
$$|p_{\text{obs}} - 2.0| \le 0.05 \quad (\text{for second-order FVM with smooth limiters})$$

#### Telescopic Conservation Certification
For any closed system without boundary fluxes, the discrete integral balance is audited across all time steps:
$$\mathcal{R}_{\text{AMR}}(t) = \left| \sum_{P=1}^{N_{\text{cells}}(t)} V_P(t) \bar{\phi}_P(t) - \sum_{P=1}^{N_{\text{cells}}(0)} V_P(0) \bar{\phi}_P(0) - \int_0^t \sum_{P} V_P S_P \, d\tau \right| \le 10^{-14}$$
guaranteeing exact numerical conservation across dynamic mesh restructuring events.



---

### 8.11 Pressure-Velocity-Density Coupling on Colocated Generalized Meshes (Rhie-Chow, PISO, and SIMPLE)

When solving the coupled Navier-Stokes equations with mass conservation on colocated (cell-centered) meshes—where pressure, velocity, density, and species concentrations are all stored at cell centroids $\mathbf{x}_P$—standard linear central interpolations suffer from the well-known **odd-even pressure decoupling (checkerboard instability)**.

```
       CELL P (P_P, v_P)             FACE f (m_f)              CELL E (P_E, v_E)
     ┌───────────────────┐                 │                 ┌───────────────────┐
     │                   │                 │                 │                   │
     │         •         │─────────────────┼────────────────►│         •         │
     │        x_P        │                 │                 │        x_E        │
     │                   │                 │                 │                   │
     └───────────────────┘                 │                 └───────────────────┘
                                   d_PE = x_E - x_P
```

#### 8.11.1 The Checkerboard Pressure Decoupling Theorem
**Theorem (Pressure Checkerboard Theorem):** *On a uniform 1D, 2D, or 3D colocated grid, evaluating the discrete pressure gradient at cell $P$ via symmetric central differencing $\left. \frac{\partial P}{\partial x} \right|_P = \frac{P_{i+1} - P_{i-1}}{2 \Delta x}$ and continuity via cell-averaged face velocities $v_f = \frac{v_P + v_E}{2}$ allows a highly oscillatory spurious pressure field $P_i = P_0 + (-1)^i \delta P$ to satisfy the discrete momentum equations with zero gradient residual ($\frac{\partial P}{\partial x} \equiv 0$).*

To suppress this unphysical null-space mode on arbitrary polyhedral and hexagonal meshes without resorting to complex staggered grids, the solver platform implements the **generalized Rhie-Chow momentum interpolation**.

#### 8.11.2 Generalized Rhie-Chow Momentum Face Interpolation on Arbitrary Polyhedra
Let the semi-discrete momentum equation at cell $P$ be written as:
$$a_P^{\mathbf{v}} \mathbf{v}_P = \mathbf{H}(\mathbf{v})_P - V_P \nabla P_P$$
where $a_P^{\mathbf{v}} = \frac{\rho_P V_P}{\Delta t} + \sum_f a_f^{\mathbf{v}}$ contains diagonal unsteady and convective/diffusive contributions, and $\mathbf{H}(\mathbf{v})_P = \sum_{f} a_f^{\mathbf{v}} \mathbf{v}_E + \mathbf{S}_{\text{mom}} V_P$ contains neighbor velocity and body force terms.
The cell velocity is:
$$\mathbf{v}_P = \frac{\mathbf{H}(\mathbf{v})_P}{a_P^{\mathbf{v}}} - \frac{V_P}{a_P^{\mathbf{v}}} \nabla P_P = \hat{\mathbf{v}}_P - d_P \nabla P_P$$
where $\hat{\mathbf{v}}_P \equiv \mathbf{H}(\mathbf{v})_P / a_P^{\mathbf{v}}$ and $d_P \equiv V_P / a_P^{\mathbf{v}}$.

The face velocity $\mathbf{v}_f$ is reconstructed by interpolating $\hat{\mathbf{v}}$ and adding a pressure Laplacian damping term proportional to the difference between the face pressure gradient and the interpolated cell gradients:
$$\mathbf{v}_f = \overline{\hat{\mathbf{v}}}_f - d_f \left( \nabla P_f - \overline{\nabla P}_f \right)$$
where:
* $\overline{\hat{\mathbf{v}}}_f = f_x \hat{\mathbf{v}}_P + (1 - f_x) \hat{\mathbf{v}}_E$ (geometric linear interpolation, $f_x = \frac{\|\mathbf{x}_E - \mathbf{x}_f\|}{\|\mathbf{d}_{PE}\|}$).
* $d_f = f_x d_P + (1 - f_x) d_E$.
* $\overline{\nabla P}_f = f_x \nabla P_P + (1 - f_x) \nabla P_E$.
* $\nabla P_f \cdot \mathbf{n}_f = \frac{P_E - P_P}{\|\mathbf{d}_{PE}\|}$ (compact face gradient).

The conservative mass flux through face $f$ becomes:
$$\dot{m}_f = \rho_f \left[ \overline{\mathbf{v}}_f \cdot \mathbf{A}_f - d_f \left( \frac{P_E - P_P}{\|\mathbf{d}_{PE}\|} A_f - (\overline{\nabla P}_f \cdot \mathbf{n}_f) A_f \right) \right]$$
This fourth-order pressure dissipation term identically suppresses the $(-1)^i$ checkerboard null-space while vanishing asymptotically at rate $\mathcal{O}(h^2)$ as the grid is refined.

#### 8.11.3 The Unstructured PISO Algorithm for Transient Multiphysics
For time-accurate transient multiphysics simulation, the **Pressure-Implicit with Splitting of Operators (PISO)** predictor-corrector sequence is executed at each time step:

1. **Momentum Predictor:**
   Solve the implicit momentum balance using pressure from the previous time step $P^n$ to obtain intermediate velocity field $\mathbf{v}^*$:
   $$a_P^{\mathbf{v}} \mathbf{v}_P^* = \mathbf{H}(\mathbf{v}^*)_P - V_P \nabla P_P^n$$
2. **First Pressure Poisson Equation (PISO Corrector 1):**
   Substitute Rhie-Chow flux $\dot{m}_f^*$ into continuity equation $\frac{V_P}{\Delta t}(\rho_P^{n+1} - \rho_P^n) + \sum_{f} \dot{m}_f^* = 0$, yielding the discrete Poisson equation for corrected pressure $P^*$:
   $$\sum_{f \in \mathcal{F}(P)} \rho_f d_f \frac{\mathbf{A}_f \cdot \mathbf{A}_f}{\mathbf{d}_{PE} \cdot \mathbf{n}_f} (P_E^* - P_P^*) = \sum_{f \in \mathcal{F}(P)} \rho_f \overline{\mathbf{v}}_f^* \cdot \mathbf{A}_f + \frac{V_P}{\Delta t}(\rho_P^{n+1} - \rho_P^n) - \sum_{f \in \mathcal{F}(P)} \rho_f d_f \mathbf{k}_f \cdot (\overline{\nabla P^n})_f$$
3. **First Explicit Velocity and Flux Correction:**
   Update cell velocities and face mass fluxes:
   $$\mathbf{v}_P^{**} = \mathbf{v}_P^* - d_P \nabla (P^* - P^n), \quad \dot{m}_f^{**} = \dot{m}_f^* - \rho_f d_f \frac{\mathbf{A}_f \cdot \mathbf{A}_f}{\mathbf{d}_{PE} \cdot \mathbf{n}_f} (P_E^* - P_P^*)$$
4. **Second Pressure Poisson Equation (PISO Corrector 2):**
   Re-evaluate $\mathbf{H}(\mathbf{v}^{**})$ to account for neighbor velocity updates and solve for final pressure $P^{n+1}$:
   $$\sum_{f \in \mathcal{F}(P)} \rho_f d_f \frac{\mathbf{A}_f \cdot \mathbf{A}_f}{\mathbf{d}_{PE} \cdot \mathbf{n}_f} (P_E^{n+1} - P_P^{n+1}) = \sum_{f \in \mathcal{F}(P)} \rho_f \overline{\hat{\mathbf{v}}^{**}}_f \cdot \mathbf{A}_f + \frac{V_P}{\Delta t}(\rho_P^{n+1} - \rho_P^n)$$
5. **Thermodynamic Density and Species Coupling:**
   Solve the advection-diffusion-reaction balances for species $\rho_i$ and energy $\rho E$ using updated conservative mass fluxes $\dot{m}_f^{n+1}$, followed by the local thermodynamic UV flash to update mixture density $\rho^{n+1}(T, P, \mathbf{z})$.

---

### 8.12 High-Order Discontinuous Galerkin (DG) and Multidimensional Riemann Solvers

For hyperbolic-dominated convective transport, shock-capturing, and high-order wave phenomena on arbitrary 2D/3D grids, the **Discontinuous Galerkin (DG-FEM)** method combines finite element local polynomial approximations with finite volume numerical fluxes.

#### 8.12.1 Weak Variational Formulation on Polyhedral Elements
Let $\mathcal{M}$ be partitioned into elements $\{K\}$. On each element $K$, the state vector $\mathbf{U}_h$ is represented by a local polynomial basis of degree $p$:
$$\mathbf{U}_h(\mathbf{x}, t) = \sum_{j=1}^{N_p} \mathbf{U}_j^K(t) \psi_j^K(\mathbf{x}), \quad N_p = \binom{p + d}{d}$$
where $\psi_j^K$ are orthogonal modal Legendre polynomials or nodal Lagrange polynomials.

Multiplying the conservation law by test function $\phi_i \in \mathbb{P}^p(K)$, integrating over element $K$, and applying integration by parts:
$$\int_K \frac{\partial \mathbf{U}_h}{\partial t} \phi_i \, dV - \int_K \mathbf{F}(\mathbf{U}_h) \cdot \nabla \phi_i \, dV + \oint_{\partial K} \widehat{\mathbf{F}}(\mathbf{U}_h^-, \mathbf{U}_h^+) \cdot \mathbf{n} \, \phi_i \, dA = \int_K \mathbf{S}(\mathbf{U}_h) \phi_i \, dV$$
where:
* $\mathbf{U}_h^-$ is the internal trace of the state on face $\partial K$.
* $\mathbf{U}_h^+$ is the external trace from the neighboring element.
* $\widehat{\mathbf{F}}(\mathbf{U}_h^-, \mathbf{U}_h^+)$ is the **approximate Riemann numerical flux**.

#### 8.12.2 Multi-Dimensional Approximate Riemann Flux Functions

##### 1. The Roe Numerical Flux with Entropy Fix
$$\widehat{\mathbf{F}}_{\text{Roe}}(\mathbf{U}_L, \mathbf{U}_R, \mathbf{n}) = \frac{1}{2}\left( \mathbf{F}(\mathbf{U}_L) \cdot \mathbf{n} + \mathbf{F}(\mathbf{U}_R) \cdot \mathbf{n} \right) - \frac{1}{2} |\mathbf{A}_{\text{Roe}}(\mathbf{U}_L, \mathbf{U}_R, \mathbf{n})| (\mathbf{U}_R - \mathbf{U}_L)$$
where $\mathbf{A}_{\text{Roe}} = \mathbf{R} \boldsymbol{\Lambda} \mathbf{R}^{-1}$ is the Roe-averaged Jacobian matrix satisfying the Rankine-Hugoniot property $\mathbf{F}(\mathbf{U}_R)\cdot\mathbf{n} - \mathbf{F}(\mathbf{U}_L)\cdot\mathbf{n} = \mathbf{A}_{\text{Roe}} (\mathbf{U}_R - \mathbf{U}_L)$, and $|\mathbf{A}_{\text{Roe}}| = \mathbf{R} |\boldsymbol{\Lambda}| \mathbf{R}^{-1}$.

##### 2. The HLLC (Harten-Lax-van Leer-Contact) Flux
The HLLC solver resolves contact discontinuities and phase boundaries exactly by restoring the intermediate contact wave ($S_*$):
$$\widehat{\mathbf{F}}_{\text{HLLC}} = \begin{cases} \mathbf{F}_L \cdot \mathbf{n}, & \text{if } 0 \le S_L \\ \mathbf{F}_{*L} \cdot \mathbf{n} = \mathbf{F}_L \cdot \mathbf{n} + S_L (\mathbf{U}_{*L} - \mathbf{U}_L), & \text{if } S_L \le 0 \le S_* \\ \mathbf{F}_{*R} \cdot \mathbf{n} = \mathbf{F}_R \cdot \mathbf{n} + S_R (\mathbf{U}_{*R} - \mathbf{U}_R), & \text{if } S_* \le 0 \le S_R \\ \mathbf{F}_R \cdot \mathbf{n}, & \text{if } 0 \ge S_R \end{cases}$$
where wave speeds $S_L$ and $S_R$ bound the fastest acoustic waves, and contact speed $S_*$ satisfies:
$$S_* = \frac{P_R - P_L + \rho_L v_{n,L} (S_L - v_{n,L}) - \rho_R v_{n,R} (S_R - v_{n,R})}{\rho_L (S_L - v_{n,L}) - \rho_R (S_R - v_{n,R})}$$

---

### 8.13 Implicit-Explicit (IMEX) Time Integration for Stiff Multiphysics Systems

In coupled reacting flows, chemical kinetics and molecular diffusion operate on time scales of nanoseconds ($\tau_{\text{rxn}} \sim 10^{-9} \, \text{s}, \Delta t_{\text{diff}} \sim \frac{h^2}{2 \mathcal{D}}$), while convective fluid transport operates on advective time scales of seconds ($\tau_{\text{conv}} \sim \frac{L}{\|\mathbf{v}\|}$).
Integrating the entire system explicitly forces an impractically tiny time step ($\Delta t < 10^{-10} \, \text{s}$), while integrating the entire system implicitly requires solving massive non-symmetric Jacobians for non-stiff advection at high computational cost.

The platform architecture formulates **Implicit-Explicit (IMEX) Additive Runge-Kutta (ARK)** schemes.

#### 8.13.1 Additive Operator Splitting
The semi-discrete ODE/DAE system is partitioned into explicit non-stiff advection $\mathbf{f}(\mathbf{Y})$ and implicit stiff diffusion/reaction $\mathbf{g}(\mathbf{Y})$:
$$\mathbf{M} \frac{d\mathbf{Y}}{dt} = \mathbf{f}(t, \mathbf{Y}) + \mathbf{g}(t, \mathbf{Y})$$
* $\mathbf{f}(t, \mathbf{Y})$: convective hyperbolic fluxes $\nabla \cdot (\rho \psi \mathbf{v})$, discretized with explicit TVD schemes.
* $\mathbf{g}(t, \mathbf{Y})$: parabolic diffusion $\nabla \cdot (\boldsymbol{\Gamma} \nabla \phi)$, stiff chemical source terms $\mathbf{S}_{\text{rxn}}$, and fast acoustic terms.

#### 8.13.2 IMEX Runge-Kutta Butcher Tableaus
An $s$-stage IMEX-ARK scheme is defined by two Butcher tableaus: an Explicit Runge-Kutta (ERK) tableau $(\tilde{\mathbf{A}}, \tilde{\mathbf{b}}, \tilde{\mathbf{c}})$ for $\mathbf{f}$, and a Diagonally Implicit Runge-Kutta (DIRK) tableau $(\mathbf{A}, \mathbf{b}, \mathbf{c})$ for $\mathbf{g}$:

```
     EXPLICIT TABLEAU (f)                   IMPLICIT TABLEAU (g)
      c̃ |  Ã                                  c |  A
     ───┼─────────────────────               ───┼─────────────────────
      0 │  0                                  c₁│  a₁₁
     c̃₂ │ ã₂₁ 0                               c₂│  a₂₁ a₂₂
     c̃₃ │ ã₃₁ ã₃₂ 0                           c₃│  a₃₁ a₃₂ a₃₃
     ───┼─────────────────────               ───┼─────────────────────
        │ b̃₁  b̃₂  b̃₃                            │  b₁  b₂  b₃
```

The stage values $\mathbf{Y}_i$ ($i = 1, \dots, s$) are computed sequentially:
$$\mathbf{Y}_i = \mathbf{Y}^n + \Delta t \sum_{j=1}^{i-1} \tilde{a}_{ij} \mathbf{f}(t^n + \tilde{c}_j \Delta t, \mathbf{Y}_j) + \Delta t \sum_{j=1}^{i-1} a_{ij} \mathbf{g}(t^n + c_j \Delta t, \mathbf{Y}_j) + \Delta t \, a_{ii} \mathbf{g}(t^n + c_i \Delta t, \mathbf{Y}_i)$$
At each stage $i$, only the non-linear algebraic system for $\mathbf{g}(\mathbf{Y}_i)$ must be inverted:
$$\mathbf{F}_{\text{stage}}(\mathbf{Y}_i) \equiv \mathbf{M} \mathbf{Y}_i - \Delta t \, a_{ii} \mathbf{g}(t^n + c_i \Delta t, \mathbf{Y}_i) - \mathbf{R}_i^{\text{known}} = \mathbf{0}$$
Since $a_{ii} > 0$ and $\mathbf{g}$ contains symmetric negative-definite diffusion operators, the Newton-Krylov linear system is symmetric positive-definite and solved with rapid multigrid convergence.

The final time-step update is:
$$\mathbf{Y}^{n+1} = \mathbf{Y}^n + \Delta t \sum_{i=1}^s \tilde{b}_i \mathbf{f}(t^n + \tilde{c}_i \Delta t, \mathbf{Y}_i) + \Delta t \sum_{i=1}^s b_i \mathbf{g}(t^n + c_i \Delta t, \mathbf{Y}_i)$$

##### Stability Guarantee
The time step is constrained solely by the mild advective CFL condition:
$$\Delta t \le C_{\text{CFL}} \frac{h}{\|\mathbf{v}\|}$$
completely removing the severe parabolic diffusive stiffness constraint ($\Delta t \le \frac{h^2}{2 \mathcal{D}}$) and reaction half-life stiffness.

---

### 8.14 Dynamic Interface and Free Surface Tracking: VOF, Level Set, and CLSVOF

When simulating multiphase flows with topological changes—such as liquid droplet breakup in spray columns, bubble rising in aerated distillation trays, or liquid film condensation—the platform formulates dynamic interface capturing methods.

#### 8.14.1 The Volume of Fluid (VOF) Method
The distribution of liquid phase is defined by the cell volumetric fraction indicator $\alpha_L(\mathbf{x}, t) \in [0, 1]$:
$$\alpha_L = \begin{cases} 1, & \text{pure liquid phase} \\ 0, & \text{pure gas/vapor phase} \\ \in (0, 1), & \text{two-phase interface cell} \end{cases}$$
The phase fraction satisfies the conservative advection equation:
$$\frac{\partial \alpha_L}{\partial t} + \nabla \cdot (\alpha_L \mathbf{v}) + \nabla \cdot \left( \alpha_L (1 - \alpha_L) \mathbf{v}_r \right) = \frac{\dot{m}_{\text{phase}}}{\rho_L}$$
where $\mathbf{v}_r = \mathbf{v}_L - \mathbf{v}_G$ is the artificial compressive relative velocity acting strictly normal to the interface to prevent numerical diffusion blurring.

##### Geometric Interface Reconstruction (PLIC)
In each interface cell, the interface is reconstructed as a planar cut:
$$\mathbf{n}_{\Sigma} \cdot \mathbf{x} = C_{\text{plane}}$$
where the interface unit normal $\mathbf{n}_{\Sigma}$ is computed via Youngs' or Parker-Youngs' gradient convolution:
$$\mathbf{n}_{\Sigma} = -\frac{\nabla \alpha_L}{\|\nabla \alpha_L\|}$$
The plane constant $C_{\text{plane}}$ is uniquely determined by clipping the polyhedral cell volume such that the truncated volume fraction equals $\alpha_L$.

#### 8.14.2 The Level Set (LS) Method
To obtain continuous, infinitely differentiable geometric interface properties, the interface is represented as the zero contour of a continuous **signed distance function** $\phi(\mathbf{x}, t)$:
$$\phi(\mathbf{x}, t) = \begin{cases} +d(\mathbf{x}, \Sigma), & \text{in liquid phase} \\ 0, & \text{on interface } \Sigma \\ -d(\mathbf{x}, \Sigma), & \text{in vapor phase} \end{cases}$$
The level set field evolves via the Hamilton-Jacobi advection equation:
$$\frac{\partial \phi}{\partial t} + \mathbf{v} \cdot \nabla \phi = 0$$

##### Interface Curvature and Surface Tension (CSF Model)
The unit normal and mean curvature $\kappa$ are evaluated analytically without numerical differentiation kinks:
$$\mathbf{n}_{\Sigma} = \frac{\nabla \phi}{\|\nabla \phi\|}, \quad \kappa = -\nabla \cdot \mathbf{n}_{\Sigma} = -\nabla \cdot \left( \frac{\nabla \phi}{\|\nabla \phi\|} \right)$$
Surface tension force is modeled as a continuous body force via Brackbill's **Continuum Surface Force (CSF)** formulation:
$$\mathbf{f}_{\sigma} = \sigma \kappa \delta_{\Sigma}(\phi) \nabla \phi$$
where $\delta_{\Sigma}(\phi)$ is a regularized Dirac delta function with support thickness $2 \epsilon = 3 h$:
$$\delta_{\Sigma}(\phi) = \begin{cases} \displaystyle \frac{1}{2\epsilon} \left( 1 + \cos\left( \frac{\pi \phi}{\epsilon} \right) \right), & \text{if } |\phi| \le \epsilon \\ 0, & \text{otherwise} \end{cases}$$

#### 8.14.3 The Coupled Level Set and Volume of Fluid (CLSVOF) Formulation
The platform combines the exact mass-conserving properties of VOF with the sharp, non-oscillatory curvature computation of Level Set:
1. VOF volume fraction $\alpha_L$ guarantees strict telescopic mass conservation.
2. Level set distance $\phi$ is reconstructed from the VOF-PLIC interface planes.
3. Curvature $\kappa$ and surface tension capillary forces are computed from $\phi$, completely eliminating spurious parasitic capillary currents at phase boundaries.

---

### 8.15 Parallel Domain Decomposition and Nonlinear Preconditioning (PETSc/Trilinos Architecture)

For large 2D and 3D industrial reactors with millions of grid cells, parallel distributed-memory high-performance computing (MPI) is indispensable.

```
       GLOBAL 3D MESH                          MPI GRAPH PARTITIONING (METIS)
     ┌────────────────────────┐                 ┌───────────┐ ┌───────────┐
     │                        │                 │ Process 0 │ │ Process 1 │
     │                        │   Partition     │  (Sub-Ω₁) │ │  (Sub-Ω₂) │
     │       Ω = ⋃ Ω_p        │ ─────────────►  └───────────┘ └───────────┘
     │                        │                 ┌───────────┐ ┌───────────┐
     │                        │                 │ Process 2 │ │ Process 3 │
     └────────────────────────┘                 │  (Sub-Ω₃) │ │  (Sub-Ω₄) │
                                                └───────────┘ └───────────┘
```

#### 8.15.1 Mesh Partitioning via Graph Duals
The unstructured polyhedral mesh is mapped to a dual connectivity graph $\mathcal{G} = (\mathcal{V}, \mathcal{E})$, where each vertex $v_P \in \mathcal{V}$ represents cell $P$, and each edge $e_{PE} \in \mathcal{E}$ represents shared face $f$.
Using k-way multilevel graph partitioning (ParMETIS or Scotch), the domain is decomposed into $N_{\text{proc}}$ subdomains $\{\Omega_p\}_{p=1}^{N_{\text{proc}}}$ minimizing edge cut communication while balancing cell workload:
$$\min \sum_{e_{PE} \in \mathcal{E}_{\text{cut}}} \text{weight}(e_{PE}) \quad \text{subject to } \max_{p} |\Omega_p| \le (1 + \epsilon_{\text{tol}}) \frac{N_{\text{cells}}}{N_{\text{proc}}}$$

#### 8.15.2 Restricted Additive Schwarz (RAS) Preconditioner
The distributed linear system $\mathbf{A} \mathbf{x} = \mathbf{b}$ across subdomains is preconditioned via the **Restricted Additive Schwarz (RAS)** operator:
$$\mathbf{M}_{\text{RAS}}^{-1} = \sum_{p=1}^{N_{\text{proc}}} \mathbf{R}_p^T \mathbf{A}_p^{-1} \widetilde{\mathbf{R}}_p$$
where:
* $\mathbf{R}_p$ is the overlapping restriction operator gathering subdomain and halo ghost cells.
* $\mathbf{A}_p = \mathbf{R}_p \mathbf{A} \mathbf{R}_p^T$ is the local subdomain matrix, factored via sparse direct solvers (MUMPS / SuperLU_DIST).
* $\widetilde{\mathbf{R}}_p$ is the non-overlapping restriction operator, preventing redundant duplicate communication across halo boundaries.

#### 8.15.3 Additive Schwarz Preconditioned Inexact Newton (ASPIN)
Standard Newton-Raphson solvers frequently fail to converge or stall on global 3D multiphysics simulations when localized, intense chemical reaction fronts or steep shock waves occur in a small region of the domain.
**ASPIN** solves independent non-linear problems on each subdomain before executing global updates:
1. Define the non-linear subdomain residual $\mathbf{F}_p(\mathbf{Y}_p) = \mathbf{R}_p \mathbf{F}(\mathbf{Y})$.
2. Compute non-linear subdomain corrections $\mathbf{g}_p(\mathbf{Y})$ such that $\mathbf{F}_p(\mathbf{Y} + \mathbf{R}_p^T \mathbf{g}_p) = \mathbf{0}$.
3. Solve the globally preconditioned non-linear problem:
   $$\mathbf{G}(\mathbf{Y}) \equiv \sum_{p=1}^{N_{\text{proc}}} \mathbf{g}_p(\mathbf{Y}) = \mathbf{0}$$
   using an inexact Newton-Krylov iteration.
ASPIN completely insulates the global simulation from local non-linear stagnation, providing robust global convergence across arbitrary multi-scale reactive multiphysics regimes.

---

---

## 9. Mathematical Derivation of Unit Operations and Reactive Separation Systems from Fundamental Laws

In accordance with Principle 10 of the Unified Architecture (Section 2), no unit operation equation or empirical shortcut may be postulated *ad hoc*. Every classical chemical engineering unit operation model—from equilibrium stages and packed columns to catalytic reactors, tubular heat exchangers, and piping networks—is deduced through a rigorous sequence of formal mathematical assumptions applied directly to the Reynolds Transport Theorem and the microscopic field equations established in Chapters 2 and 8.

---

### 9.1 Fundamental Derivation Methodology: From First Principles to Unit Envelopes

The general macroscopic unit operation envelope is defined over an open, connected control volume $\Omega_k(t) \subset \mathbb{R}^3$ with boundary $\partial \Omega_k(t) = \Gamma_{k,\text{ports}}(t) \cup \Gamma_{k,\text{walls}}(t) \cup \Sigma_{kj}(t)$, where $\Gamma_{k,\text{ports}}$ represents discrete inlet/outlet flow manifolds, $\Gamma_{k,\text{walls}}$ represents solid confining boundaries, and $\Sigma_{kj}$ represents phase interfaces with adjacent fluid phases.

#### The Reynolds Reduction Theorem for Unit Operations
For any intensive property $\psi \in \{1, \mathbf{v}, u + \frac{1}{2}v^2, x_i\}$, the integral conservation law states:
$$\frac{d}{dt} \int_{\Omega_k(t)} \rho \psi \, dV + \int_{\partial \Omega_k(t)} \rho \psi (\mathbf{v} - \mathbf{w}) \cdot \mathbf{n} \, dA = -\int_{\partial \Omega_k(t)} \mathbf{J}_\psi \cdot \mathbf{n} \, dA + \int_{\Omega_k(t)} \dot{S}_\psi \, dV$$

The reduction to standard unit operation forms follows four canonical projection operations:
1. **Spatial Averaging Operator $\langle \cdot \rangle$:**
   $$\langle \phi \rangle_k(t) \equiv \frac{1}{V_k(t)} \int_{\Omega_k(t)} \phi(\mathbf{x}, t) \, dV$$
   Under the *well-mixed assumption* ($\|\nabla \phi\| \cdot L_{\text{char}} \ll \bar{\phi}$), the field inside $\Omega_k$ is replaced by its spatial average, and the exit port state is identical to the bulk volume state: $\phi_{\text{out}}(t) = \langle \phi \rangle_k(t)$.
2. **Boundary Flux Partitioning:**
   The surface integral over $\partial \Omega_k$ is partitioned into discrete convective streams and interphase transfer areas:
   $$\int_{\partial \Omega_k} \rho \psi (\mathbf{v} - \mathbf{w}) \cdot \mathbf{n} \, dA = \sum_{j \in \text{out}} \dot{m}_j \psi_j - \sum_{j \in \text{in}} \dot{m}_j \psi_j + \int_{\Sigma_{kj}} \rho (\mathbf{v} - \mathbf{w}_I) \cdot \mathbf{n}_I \, dA$$
3. **Phase Interface Jump Coupling:**
   Applying the Rankine-Hugoniot jump condition (Section 2.7) across phase interface $\Sigma_{kj}$:
   $$\llbracket \rho (\mathbf{v} - \mathbf{w}_I) \cdot \mathbf{n}_I \psi + \mathbf{J}_\psi \cdot \mathbf{n}_I \rrbracket = \dot{\Omega}_{\psi, \Sigma}$$
   which enforces interphase mass, momentum, and heat transfer rates between adjacent phases (e.g., vapor-liquid, liquid-liquid, or fluid-solid).
4. **Constitutive Closure Injection:**
   Replacing abstract diffusive fluxes $\mathbf{J}_\psi$ with Stefan-Maxwell multicomponent diffusion, Fourier conduction, or empirical mass/heat transfer coefficients ($k_c, U$), and source terms $\dot{S}_\psi$ with chemical reaction kinetics $\sum_r \nu_{ir} r_r$.

---

### 9.2 Reactive Distillation and Equilibrium Stage Separations (MESH-D Formulation)

Reactive distillation couples multicomponent separation and chemical reaction within a single spatial column shell. Consider stage $j \in \{1, \dots, N_T\}$ numbered from top (condenser $j=1$) to bottom (reboiler $j=N_T$).

```
                    Vapor from stage j+1: V_{j+1}, y_{i,j+1}, h_{j+1}^V
                                   ^
                                   |
                         +-------------------+
                         |                   | ---> Vapor Side-draw: W_j, y_{i,j}
   Feed: F_j, z_{i,j} -> |      STAGE j      |
   Heat Duty: Q_j     -> |                   | ---> Liquid Side-draw: U_j, x_{i,j}
                         +-------------------+
                                   |
                                   v
                    Liquid to stage j+1: L_j, x_{i,j}, h_j^L
```

#### 9.2.1 Material Balance (M-Equations)
Applying the species mass conservation law to control volume $\Omega_j$ enclosing the liquid holdup $M_{L,j}$ (mol) and vapor holdup $M_{V,j}$ (mol):
$$\frac{d M_{i,j}}{dt} = \frac{d}{dt} \left( M_{L,j} x_{i,j} + M_{V,j} y_{i,j} \right) = L_{j-1} x_{i,j-1} + V_{j+1} y_{i,j+1} + F_j z_{i,j} - (L_j + U_j) x_{i,j} - (V_j + W_j) y_{i,j} + R_{i,j}$$
where $R_{i,j}$ is the net generation rate of species $i$ on stage $j$ by all $N_{\text{rxn}}$ homogeneous and heterogeneous reactions:
$$R_{i,j} = M_{L,j} \sum_{r=1}^{N_{\text{rxn}}} \nu_{i,r} r_{r,j}(T_j, P_j, \mathbf{x}_j) + \epsilon_{\text{cat}} V_{\text{stage}} \sum_{r=1}^{N_{\text{rxn}}} \nu_{i,r} r_{r,\text{het}}(T_j, P_j, \mathbf{x}_j)$$

##### Vapor Holdup Asymptotic Reduction
In high-pressure or supercritical distillation, $M_{V,j}$ must be retained. However, for low to moderate pressures ($P < 20 \, \text{bar}$), the phase density ratio satisfies $\rho_V / \rho_L \sim \mathcal{O}(10^{-3})$. Under the formal asymptotic limit $\varepsilon = \frac{\rho_V V_V}{\rho_L V_L} \to 0$:
$$\frac{d M_{i,j}}{dt} = \frac{d (M_{L,j} x_{i,j})}{dt} + \mathcal{O}(\varepsilon) = M_{L,j} \frac{d x_{i,j}}{dt} + x_{i,j} \frac{d M_{L,j}}{dt}$$
Summing over all $N_c$ species gives the total molar holdup continuity equation:
$$\frac{d M_{L,j}}{dt} = L_{j-1} + V_{j+1} + F_j - (L_j + U_j) - (V_j + W_j) + M_{L,j} \sum_{r=1}^{N_{\text{rxn}}} \left( \sum_{i=1}^{N_c} \nu_{i,r} \right) r_{r,j}$$
Defining the overall reaction stoichiometric change $\Delta \nu_r \equiv \sum_{i=1}^{N_c} \nu_{i,r}$, we obtain:
$$\frac{d M_{L,j}}{dt} = L_{j-1} + V_{j+1} + F_j - (L_j + U_j) - (V_j + W_j) + M_{L,j} \sum_{r=1}^{N_{\text{rxn}}} \Delta \nu_r r_{r,j}$$

#### 9.2.2 Phase Equilibrium Relations (E-Equations)
At thermodynamic equilibrium between leaving liquid and vapor streams:
$$f_i^V(T_j, P_j, \mathbf{y}_j) = f_i^L(T_j, P_j, \mathbf{x}_j) \quad \forall i \in \{1, \dots, N_c\}$$
Substituting the fugacity coefficient $\Phi_{i,j}^V$ and liquid activity coefficient $\gamma_{i,j}^L$:
$$y_{i,j}^* \Phi_{i,j}^V(T_j, P_j, \mathbf{y}_j^*) P_j = x_{i,j} \gamma_{i,j}^L(T_j, P_j, \mathbf{x}_j) P_i^{\text{sat}}(T_j) \phi_i^{\text{sat}}(T_j) \exp\left[ \frac{\bar{v}_i^L(P_j - P_i^{\text{sat}}(T_j))}{R T_j} \right]$$
The equilibrium distribution ratio is defined as:
$$K_{i,j} \equiv \frac{y_{i,j}^*}{x_{i,j}} = \frac{\gamma_{i,j}^L P_i^{\text{sat}} \phi_i^{\text{sat}} \exp\left[ \frac{\bar{v}_i^L(P_j - P_i^{\text{sat}})}{R T_j} \right]}{\Phi_{i,j}^V P_j}$$

##### Murphree Tray Efficiency Departure
When stage departure from thermodynamic equilibrium is modeled via Murphree vapor efficiency $E_{MV,i,j} \in (0, 1]$:
$$y_{i,j} = y_{i,j+1} + E_{MV,i,j} \left( y_{i,j}^* - y_{i,j+1} \right) \iff \frac{y_{i,j} - y_{i,j+1}}{K_{i,j} x_{i,j} - y_{i,j+1}} - E_{MV,i,j} = 0$$

#### 9.2.3 Summation Constraints (S-Equations)
Mole fractions in both bulk phases must satisfy partition of unity:
$$\sum_{i=1}^{N_c} x_{i,j} - 1 = 0, \quad \sum_{i=1}^{N_c} y_{i,j} - 1 = 0$$

#### 9.2.4 Enthalpy / Energy Balances (H-Equations)
Applying the first law of thermodynamics to control volume $\Omega_j$:
$$\frac{d U_j}{dt} = \frac{d}{dt}\left( M_{L,j} u_j^L + M_{V,j} u_j^V \right) = L_{j-1} h_{j-1}^L + V_{j+1} h_{j+1}^V + F_j h_{F,j} - (L_j + U_j) h_j^L - (V_j + W_j) h_j^V + Q_j$$
Since $u = h - P v = h - \frac{P}{\rho}$, and neglecting mechanical work terms $\frac{d(P V_j)}{dt}$ under isobaric stage operations:
$$\frac{d (M_{L,j} h_j^L)}{dt} = L_{j-1} h_{j-1}^L + V_{j+1} h_{j+1}^V + F_j h_{F,j} - (L_j + U_j) h_j^L - (V_j + W_j) h_j^V + Q_j$$
Applying the chain rule to the differential enthalpy accumulation term:
$$\frac{d (M_{L,j} h_j^L)}{dt} = h_j^L \frac{d M_{L,j}}{dt} + M_{L,j} \left[ C_{p,j}^L \frac{d T_j}{dt} + \sum_{i=1}^{N_c} \bar{h}_{i,j}^L \frac{d x_{i,j}}{dt} \right]$$
where $\bar{h}_{i,j}^L = \left( \frac{\partial (M_L h^L)}{\partial n_i^L} \right)_{T, P, n_{k \ne i}}$ is the partial molar enthalpy of component $i$.

##### Reaction Enthalpy Consistency
When partial molar enthalpies $\bar{h}_{i}^L(T)$ are referenced to pure elements in their standard states ($\Delta H_{f,i}^\circ$), the heat of reaction is automatically accounted for by the enthalpy difference:
$$\sum_{i=1}^{N_c} R_{i,j} \bar{h}_{i,j}^L = \sum_{r=1}^{N_{\text{rxn}}} r_{r,j} M_{L,j} \left( \sum_{i=1}^{N_c} \nu_{i,r} \bar{h}_{i,j}^L \right) = -\sum_{r=1}^{N_{\text{rxn}}} r_{r,j} M_{L,j} \Delta H_{\text{rxn},r}(T_j)$$
preventing double-counting errors in the energy equation.

#### 9.2.5 Dynamic Tray Hydraulics and Pressure Drops (D-Equations)
Stage exit liquid flow $L_j$ is governed by the liquid height over the weir $h_{ow,j}$ via the Francis weir formula (Section 2.11):
$$L_j = \frac{2}{3} C_w \left( \frac{\rho_{L,j}}{M_{w,L,j}} \right) \sqrt{2 g} \, W_{\text{weir}} \, \left[ \max\left(0, h_{\text{liq},j} - h_{\text{weir}}\right) \right]^{3/2}$$
where the clear liquid height is related to the dynamic molar holdup by:
$$h_{\text{liq},j} = \frac{M_{L,j} M_{w,L,j}}{\rho_{L,j} A_{\text{active}}}$$

The total vapor pressure drop across stage $j$ is the sum of dry tray pressure drop and aerated liquid head:
$$\Delta P_j = P_{j+1} - P_j = \Delta P_{\text{dry},j} + \Delta P_{\text{liq},j}$$
1. **Dry Tray Pressure Drop (Perforated Orifice):**
   $$\Delta P_{\text{dry},j} = \frac{\xi_{\text{dry}}}{2} \rho_{V,j+1} \left( \frac{V_{j+1} M_{w,V,j+1}}{\rho_{V,j+1} A_{\text{holes}}} \right)^2$$
   where $\xi_{\text{dry}} \approx \frac{1}{C_0^2} \left( 1 - \frac{A_{\text{holes}}}{A_{\text{active}}} \right)$.
2. **Aerated Liquid Head Pressure Drop:**
   $$\Delta P_{\text{liq},j} = \beta_{\text{aer}} \rho_{L,j} g h_{\text{liq},j}$$
   where $\beta_{\text{aer}} \in [0.4, 0.7]$ is the aeration factor accounting for froth two-phase void fraction.

##### Hydraulic Operability Envelope: Weeping and Flooding Boundaries
The MESH-D algebraic-differential solver continuously audits the local stage state against hydraulic operating limits:
* **Weeping Boundary:** Occurs when vapor kinetic energy is insufficient to support liquid over the perforations:
  $$F_{\text{hole}} \equiv u_{\text{hole}} \sqrt{\rho_V} = \left( \frac{V_{j+1} M_{w,V,j+1}}{\rho_{V,j+1} A_{\text{holes}}} \right) \sqrt{\rho_{V,j+1}} < F_{\text{weep}} \approx 3.0 \, \text{Pa}^{1/2}$$
  Below this threshold, liquid drips through tray holes, bypassing cross-flow contact and causing catastrophic stage efficiency collapse.
* **Entrainment Flooding Boundary:** Occurs when vapor velocity exceeds the droplet terminal settling velocity, carrying massive liquid droplets to the stage above. Evaluated via Fair's capacity factor $C_{sb}$:
  $$C_{sb} \equiv u_V \sqrt{\frac{\rho_V}{\rho_L - \rho_V}} = \left( \frac{V_j M_{w,V,j}}{\rho_{V,j} A_{\text{net}}} \right) \sqrt{\frac{\rho_{V,j}}{\rho_{L,j} - \rho_{V,j}}} \ge C_{sb,\text{flood}}$$
  where $C_{sb,\text{flood}} = f(\text{tray spacing } H_s, \text{flow parameter } F_{LV} = \frac{L_j}{V_j}\sqrt{\frac{\rho_V}{\rho_L}}, \text{surface tension } \sigma)$.

#### 9.2.6 Reactive Azeotrope Formation and Distillation Boundaries
The chemical reaction couples species generation with phase separation. Introducing transformed composition variables (Doherty & Malone):
$$X_i \equiv \frac{x_i - \nu_i (\nu_{\text{ref}})^{-1} x_{\text{ref}}}{1 - \Delta \nu (\nu_{\text{ref}})^{-1} x_{\text{ref}}}, \quad Y_i \equiv \frac{y_i - \nu_i (\nu_{\text{ref}})^{-1} y_{\text{ref}}}{1 - \Delta \nu (\nu_{\text{ref}})^{-1} y_{\text{ref}}}$$
A **reactive azeotrope** occurs at the stationary point where transformed liquid and vapor compositions coincide:
$$X_i = Y_i \quad \forall i \in \{1, \dots, N_c - 1\}$$
In physical mole fractions, this condition is equivalent to the coplanarity of the vapor-liquid equilibrium vector and the stoichiometric reaction vector:
$$\frac{y_1 - x_1}{\nu_1 - x_1 \Delta \nu} = \frac{y_2 - x_2}{\nu_2 - x_2 \Delta \nu} = \dots = \frac{y_{N_c} - x_{N_c}}{\nu_{N_c} - x_{N_c} \Delta \nu}$$
The Damköhler number of stage $j$,
$$Da_j \equiv \frac{k_f(T_j) M_{L,j}}{L_j}$$
governs the topological deformation of the distillation boundary: as $Da \to 0$, classical non-reactive VLE boundaries govern; as $Da \to \infty$, reactive equilibrium surfaces constrain the feasible separation products.

---

### 9.3 Non-Equilibrium Rate-Based Transport Modeling (Two-Film Theory)

When multicomponent mixtures exhibit significant thermodynamic non-ideality, large interphase flux rates, or disparate molecular sizes, the equilibrium stage assumption ($E_{MV} = 1$) fails qualitatively. The rate-based approach models each stage as two distinct continuous fluid bulk phases (vapor $V$ and liquid $L$) coupled across a phase interface $\Sigma_{\text{int}}$.

```
         BULK VAPOR                          INTERPHASE FILMS                          BULK LIQUID
      (T_V, P_V, y_{i,V})                 Vapor Film  |  Liquid Film                (T_L, P_L, x_{i,L})
             |                                        |                                      |
             | ----> Convective Flux N_i^V ---------> | ----> Convective Flux N_i^L -------> |
             | ----> Heat Flux q^V -----------------> | ----> Heat Flux q^L ---------------> |
             |                                        |                                      |
             z = 0                              z = \delta_V  z = \delta_L                   z = \delta_V + \delta_L
                                                INTERFACE (\Sigma)
                                             T^I, P^I, y_{i}^I, x_{i}^I
```

#### 9.3.1 Multicomponent Mass Transfer in the Vapor Film
The 1D stationary mass transfer across the vapor film thickness $\delta_V$ is governed by the 1D Stefan-Maxwell equations (Section 2.2):
$$-\frac{d y_i}{d z} = \sum_{k=1}^{N_c} \frac{y_k N_i^V - y_i N_k^V}{c_t^V \bigoplus_{ik}^V}$$
Integrating across the film from bulk vapor ($z=0, y_{i}=y_{i,V}$) to interface ($z=\delta_V, y_{i}=y_{i}^I$) yields the matrix film transfer equation:
$$(N^V) = c_t^V [R^V]^{-1} [\Gamma^V] (y_V - y^I) + N_{\text{tot}}^V (y_V)$$
where $[R^V]$ is the $(N_c-1) \times (N_c-1)$ multicomponent mass transfer resistance matrix with elements:
$$R_{ii}^V = \frac{y_i^V}{k_{i,N_c}^V} + \sum_{\substack{k=1 \\ k \ne i}}^{N_c} \frac{y_k^V}{k_{ik}^V}, \quad R_{ij}^V = -y_i^V \left( \frac{1}{k_{ij}^V} - \frac{1}{k_{i,N_c}^V} \right) \quad (i \ne j)$$
and binary mass transfer coefficients are $k_{ik}^V = \bigoplus_{ik}^V / \delta_V$.

#### 9.3.2 Multicomponent Mass Transfer in the Liquid Film
In the liquid film, chemical potential gradients drive diffusion. Applying the generalized Maxwell-Stefan relations with thermodynamic non-ideality matrix $[\Gamma^L]$:
$$(N^L) = c_t^L [R^L]^{-1} [\Gamma^L] (x^I - x_L) + N_{\text{tot}}^L (x_L)$$
where $[\Gamma^L]$ is the matrix of thermodynamic factor derivatives computed from UNIFAC or NRTL:
$$\Gamma_{ij}^L = \delta_{ij} + x_i \left( \frac{\partial \ln \gamma_i^L}{\partial x_j} \right)_{T, P, x_{k \ne j, N_c}}$$

#### 9.3.3 Interface Continuity and Thermodynamic Equilibrium
Assuming negligible interface mass storage, mass continuity across $\Sigma_{\text{int}}$ requires:
$$N_i^V = N_i^L \equiv N_i \quad \forall i \in \{1, \dots, N_c\}$$
Thermodynamic phase equilibrium is enforced strictly at the phase boundary coordinates $z_I$:
$$y_i^I \Phi_i^V(T^I, P, \mathbf{y}^I) = x_i^I \gamma_i^L(T^I, P, \mathbf{x}^I) P_i^{\text{sat}}(T^I) \phi_i^{\text{sat}}(T^I) \exp\left[ \frac{\bar{v}_i^L (P - P_i^{\text{sat}})}{R T^I} \right]$$

#### 9.3.4 Interphase Energy Transfer Continuity with Ackermann Correction
Energy conservation across the interface requires continuity of conductive, convective, and latent heat fluxes:
$$q^V + \sum_{i=1}^{N_c} N_i \bar{h}_i^V(T^I) = q^L + \sum_{i=1}^{N_c} N_i \bar{h}_i^L(T^I)$$
The net conductive heat fluxes $q^V$ and $q^L$ are modified by the net mass transfer flux via the **Ackermann high-flux correction factors**:
$$q^V = h_V \cdot \Xi_V \cdot (T_V - T^I), \quad \Xi_V = \frac{\Theta_V}{\exp(\Theta_V) - 1}, \quad \Theta_V = \frac{\sum_{i=1}^{N_c} N_i C_{p,i}^V}{h_V}$$
$$q^L = h_L \cdot \Xi_L \cdot (T^I - T_L), \quad \Xi_L = \frac{\Theta_L}{1 - \exp(-\Theta_L)}, \quad \Theta_L = \frac{\sum_{i=1}^{N_c} N_i C_{p,i}^L}{h_L}$$
When mass flux is directed from liquid to vapor (evaporation, $N_{\text{tot}} > 0$), $\Theta_V > 0 \implies \Xi_V < 1$, which retards vapor conductive heat transfer, while $\Xi_L > 1$, which accelerates liquid conduction toward the evaporating interface.

---

### 9.4 Chemical Reaction Engineering: CSTR, PFR, and Heterogeneous Catalysis

The mathematical representation of chemical reactors is derived directly from the fundamental conservation balances by imposing specific fluid mixing and spatial constraint assumptions.

#### 9.4.1 Continuous Stirred Tank Reactor (CSTR)
The ideal CSTR is defined by the infinite macromixing assumption ($\mathcal{D}_{\text{eff}} \to \infty$), rendering spatial concentration and temperature gradients zero throughout the reactor volume $V_R$.

##### Dynamic Formulation
$$\frac{d(V_R C_i)}{dt} = \dot{V}_{\text{in}} C_{i,\text{in}} - \dot{V}_{\text{out}} C_i + V_R \sum_{r=1}^{N_{\text{rxn}}} \nu_{i,r} r_r(T, \mathbf{C})$$
$$\frac{d(V_R \rho c_p T)}{dt} = \dot{V}_{\text{in}} \rho_{\text{in}} c_{p,\text{in}} T_{\text{in}} - \dot{V}_{\text{out}} \rho c_p T + V_R \sum_{r=1}^{N_{\text{rxn}}} (-\Delta H_{\text{rxn},r}) r_r(T, \mathbf{C}) - U A_{\text{jacket}} (T - T_j)$$

##### Steady-State van Heerden Thermal Runaway and Multiplicity
For a single exothermic irreversible first-order reaction ($A \to B$) at constant volume, steady state requires the heat generation curve $Q_G(T)$ to intersect the heat removal line $Q_R(T)$:
$$Q_G(T) = (-\Delta H_{\text{rxn}}) V_R \frac{k_0 e^{-E_a/RT} C_{A,\text{in}}}{1 + \tau k_0 e^{-E_a/RT}}$$
$$Q_R(T) = \dot{m} c_p (T - T_{\text{in}}) + U A (T - T_j) = (\dot{m} c_p + U A) \left[ T - \frac{\dot{m} c_p T_{\text{in}} + U A T_j}{\dot{m} c_p + U A} \right]$$
where $\tau = V_R / \dot{V}$ is space time.
* **Ignition and Extinction Bifurcation:** Limit points occur when both values and slopes match:
  $$Q_G(T^*) = Q_R(T^*) \quad \text{and} \quad \left. \frac{d Q_G}{d T} \right|_{T^*} = \left. \frac{d Q_R}{d T} \right|_{T^*}$$
* **Local Stability Criterion:** An equilibrium point $T^*$ is asymptotically stable if:
  $$\left. \frac{d Q_R}{d T} \right|_{T^*} > \left. \frac{d Q_G}{d T} \right|_{T^*}$$
  When $\frac{d Q_G}{dT} > \frac{d Q_R}{dT}$, positive thermal feedback causes exponential divergence (thermal runaway).

#### 9.4.2 Plug Flow Reactor (PFR) with Axial Dispersion
The 1D axial dispersion model accounts for non-ideal velocity profiles and turbulent back-mixing in tubular reactors.

##### Field Equations
$$\frac{\partial C_i}{\partial t} + u_z \frac{\partial C_i}{\partial z} = \mathcal{D}_{\text{ax}} \frac{\partial^2 C_i}{\partial z^2} + \sum_{r=1}^{N_{\text{rxn}}} \nu_{i,r} r_r(T, \mathbf{C})$$
$$\rho c_p \left( \frac{\partial T}{\partial t} + u_z \frac{\partial T}{\partial z} \right) = k_{\text{ax}} \frac{\partial^2 T}{\partial z^2} + \sum_{r=1}^{N_{\text{rxn}}} (-\Delta H_{\text{rxn},r}) r_r - \frac{4 U}{d_t} (T - T_w)$$
where $\mathcal{D}_{\text{ax}}$ is the axial dispersion coefficient, $k_{\text{ax}}$ is axial thermal conductivity, and $d_t$ is tube diameter.

##### Danckwerts Boundary Conditions
At the tube entrance ($z = 0$), continuity of total convective plus diffusive flux across the physical discontinuity requires:
$$\left. \left( u_z C_i - \mathcal{D}_{\text{ax}} \frac{\partial C_i}{\partial z} \right) \right|_{z=0^+} = u_z C_{i,0}$$
$$\left. \left( \rho c_p u_z T - k_{\text{ax}} \frac{\partial T}{\partial z} \right) \right|_{z=0^+} = \rho c_p u_z T_0$$
At the tube exit ($z = L$), the absence of physical downstream diffusion sources imposes zero gradient:
$$\left. \frac{\partial C_i}{\partial z} \right|_{z=L^-} = 0, \quad \left. \frac{\partial T}{\partial z} \right|_{z=L^-} = 0$$

#### 9.4.3 Heterogeneous Catalysis: Diffusion and Reaction in Porous Pellets
For solid catalyzed reactions, transport through the porous pellet structure interacts with surface kinetics.

##### Microscopic Pellet Balance
Inside a spherical catalyst pellet of radius $R_p$, under steady state:
$$\frac{1}{r^2} \frac{d}{dr} \left( r^2 \mathcal{D}_{\text{eff}} \frac{d C_A}{dr} \right) + r_A(C_A, T) = 0, \quad r \in [0, R_p]$$
with symmetry at center and external surface boundary:
$$\left. \frac{d C_A}{dr} \right|_{r=0} = 0, \quad C_A(R_p) = C_{A,s}$$

##### First-Order Analytical Solution and Thiele Modulus
For an isothermal, first-order reaction ($r_A = -k_1 C_A$):
$$\frac{d^2 C_A}{dr^2} + \frac{2}{r} \frac{d C_A}{dr} - \frac{k_1}{\mathcal{D}_{\text{eff}}} C_A = 0$$
Transforming via $u(r) = r C_A(r)$ yields the exact concentration profile:
$$C_A(r) = C_{A,s} \left( \frac{R_p}{r} \right) \frac{\sinh\left( \phi \frac{r}{R_p} \right)}{\sinh \phi}$$
where the **Thiele Modulus** $\phi$ is defined as:
$$\phi \equiv R_p \sqrt{\frac{k_1}{\mathcal{D}_{\text{eff}}}}$$

##### Internal Effectiveness Factor ($\eta$)
The effectiveness factor measures the ratio of actual reaction rate to the rate if the entire pellet interior were exposed to surface conditions $C_{A,s}$:
$$\eta \equiv \frac{\int_0^{R_p} 4 \pi r^2 k_1 C_A(r) \, dr}{\frac{4}{3} \pi R_p^3 k_1 C_{A,s}} = \frac{3}{\phi} \left( \frac{1}{\tanh \phi} - \frac{1}{\phi} \right)$$
* **Asymptotic Limits:**
  $$\eta \approx 1 - \frac{\phi^2}{15} \to 1 \quad \text{as } \phi \to 0 \quad (\text{reaction-limited regime})$$
  $$\eta \approx \frac{3}{\phi} \to 0 \quad \text{as } \phi \to \infty \quad (\text{strong pore diffusion limitation})$$

##### Weisz-Prater Criterion for Diffusion Limitation
To evaluate diffusion limitations experimentally without prior knowledge of the intrinsic rate constant $k_1$, the **Weisz-Prater parameter** $\Phi_{\text{WP}}$ is computed directly from observable reaction rates $r_{\text{obs}}$:
$$\Phi_{\text{WP}} \equiv \eta \phi^2 = \frac{r_{\text{obs}} R_p^2}{\mathcal{D}_{\text{eff}} C_{A,s}}$$
* If $\Phi_{\text{WP}} \ll 1$, internal concentration gradients are negligible ($C_A \approx C_{A,s}, \eta \approx 1$).
* If $\Phi_{\text{WP}} \gg 1$, severe internal pore diffusion resistance limits the reaction.

##### Non-Isothermal Pellet Behavior: Prater and Arrhenius Numbers
When reaction heat release inside the pellet is significant, internal temperature elevation is governed by the Prater relation:
$$T(r) - T_s = \frac{(-\Delta H_{\text{rxn}}) \mathcal{D}_{\text{eff}}}{k_{\text{eff}}} \left( C_{A,s} - C_A(r) \right)$$
Defining the **Prater number** $\beta_P$ and **Arrhenius number** $\gamma_A$:
$$\beta_P \equiv \frac{(-\Delta H_{\text{rxn}}) \mathcal{D}_{\text{eff}} C_{A,s}}{k_{\text{eff}} T_s}, \quad \gamma_A \equiv \frac{E_a}{R T_s}$$
For strongly exothermic reactions with large $\beta_P \gamma_A$, internal temperatures can exceed surface temperature sufficiently to accelerate kinetics, producing effectiveness factors $\eta > 1$ before falling to asymptotic $3/\phi$ behavior.

---

### 9.5 Heat Exchange Networks, LMTD, and Conjugate Thermal Walls

Heat transfer equipment is governed by coupled convective and conductive energy equations across dividing solid boundaries.

```
       Fluid 1 (Hot): \dot{m}_h, C_{p,h}, T_h(x) --->
     ================================================ Solid Wall (T_w)
       Fluid 2 (Cold): \dot{m}_c, C_{p,c}, T_c(x) ---> (Co-current) or <--- (Counter-current)
```

#### 9.5.1 One-Dimensional Distributed Balances along Stream Coordinate
For a differential length $dx$ of a two-fluid heat exchanger:
$$\dot{m}_h C_{p,h} \frac{d T_h}{dx} = -U P_{\text{perim}} (T_h(x) - T_c(x))$$
$$\pm \dot{m}_c C_{p,c} \frac{d T_c}{dx} = +U P_{\text{perim}} (T_h(x) - T_c(x))$$
where the sign on the cold stream is positive for co-current flow and negative for counter-current flow, and $P_{\text{perim}}$ is the heat transfer perimeter such that $d A = P_{\text{perim}} dx$.

The overall heat transfer coefficient $U$ is given by the series thermal resistance network:
$$\frac{1}{U A} = \frac{1}{h_h A_h} + R_{\text{foul},h} + \frac{\ln(r_o/r_i)}{2 \pi k_{\text{wall}} L} + R_{\text{foul},c} + \frac{1}{h_c A_c}$$

#### 9.5.2 Exact Mathematical Derivation of the Logarithmic Mean Temperature Difference (LMTD)
Let the local temperature driving force be defined as $\Delta T(x) \equiv T_h(x) - T_c(x)$.
Differentiating with respect to $x$:
$$\frac{d(\Delta T)}{dx} = \frac{d T_h}{dx} - \frac{d T_c}{dx}$$
Substituting the distributed balances:
$$\frac{d(\Delta T)}{dx} = -U P_{\text{perim}} \left( \frac{1}{\dot{m}_h C_{p,h}} \mp \frac{1}{\dot{m}_c C_{p,c}} \right) \Delta T(x)$$
Assuming constant fluid heat capacities $C_{p,h}, C_{p,c}$ and overall coefficient $U$, the bracketed expression is constant. Let:
$$K \equiv U P_{\text{perim}} \left( \frac{1}{\dot{m}_h C_{p,h}} \mp \frac{1}{\dot{m}_c C_{p,c}} \right)$$
Then the driving force satisfies the linear ODE:
$$\frac{d(\Delta T)}{dx} = -K \Delta T(x) \implies \ln\left( \frac{\Delta T(L)}{\Delta T(0)} \right) = -K L$$
Total steady-state heat duty transferred over the entire exchanger area $A = P_{\text{perim}} L$ is:
$$Q = \dot{m}_h C_{p,h} (T_{h,\text{in}} - T_{h,\text{out}}) = \pm \dot{m}_c C_{p,c} (T_{c,\text{out}} - T_{c,\text{in}})$$
Therefore:
$$\frac{1}{\dot{m}_h C_{p,h}} = \frac{T_{h,\text{in}} - T_{h,\text{out}}}{Q}, \quad \mp \frac{1}{\dot{m}_c C_{p,c}} = \frac{T_{c,\text{in}} - T_{c,\text{out}}}{Q}$$
Summing both equations yields:
$$\frac{1}{\dot{m}_h C_{p,h}} \mp \frac{1}{\dot{m}_c C_{p,c}} = \frac{(T_{h,\text{in}} - T_{c,\text{in}}) - (T_{h,\text{out}} - T_{c,\text{out}})}{Q} = \frac{\Delta T_a - \Delta T_b}{Q}$$
where $\Delta T_a, \Delta T_b$ are the terminal temperature differences at ends $a$ and $b$ of the exchanger.
Multiplying by $U A$:
$$K L = U A \left( \frac{\Delta T_a - \Delta T_b}{Q} \right)$$
Equating to the logarithmic solution $-K L = \ln(\Delta T_b / \Delta T_a)$:
$$-\ln\left( \frac{\Delta T_b}{\Delta T_a} \right) = \ln\left( \frac{\Delta T_a}{\Delta T_b} \right) = U A \frac{\Delta T_a - \Delta T_b}{Q}$$
Rearranging for $Q$ yields the exact LMTD equation:
$$Q = U A \, \Delta T_{\text{LMTD}}, \quad \Delta T_{\text{LMTD}} \equiv \frac{\Delta T_a - \Delta T_b}{\ln\left( \frac{\Delta T_a}{\Delta T_b} \right)}$$

##### Numerical Singularity Removal
When terminal temperature differences approach equality ($\Delta T_a \to \Delta T_b$), direct evaluation of $\Delta T_{\text{LMTD}}$ produces floating-point loss of significance ($0/0$). The solver automatically shifts to a high-order Taylor series:
Let $\delta \equiv \frac{\Delta T_a - \Delta T_b}{\Delta T_a + \Delta T_b}$. Then $\frac{\Delta T_a}{\Delta T_b} = \frac{1+\delta}{1-\delta}$.
$$\ln\left( \frac{1+\delta}{1-\delta} \right) = 2 \left( \delta + \frac{\delta^3}{3} + \frac{\delta^5}{5} + \mathcal{O}(\delta^7) \right)$$
$$\Delta T_{\text{LMTD}} = \frac{\Delta T_a + \Delta T_b}{2} \left[ 1 - \frac{\delta^2}{3} - \frac{4 \delta^4}{45} - \mathcal{O}(\delta^6) \right]$$
which evaluates with zero loss of significance to machine precision for $|\delta| < 10^{-4}$.

#### 9.5.3 The Effectiveness-NTU ($\epsilon$-NTU) Method
When terminal exit temperatures are unknown *a priori*, the $\epsilon$-NTU method eliminates iterative shooting solves.
* **Heat Capacity Rates:** $C_h = \dot{m}_h C_{p,h}, \quad C_c = \dot{m}_c C_{p,c}$
* **Minimum and Maximum Capacities:** $C_{\min} = \min(C_h, C_c), \quad C_{\max} = \max(C_h, C_c), \quad C_r = \frac{C_{\min}}{C_{\max}} \in [0, 1]$
* **Number of Transfer Units (NTU):**
  $$NTU \equiv \frac{U A}{C_{\min}}$$
* **Effectiveness ($\epsilon$):**
  $$\epsilon \equiv \frac{Q}{Q_{\max}} = \frac{Q}{C_{\min} (T_{h,\text{in}} - T_{c,\text{in}})}$$
For counter-current flow, analytical integration yields:
$$\epsilon = \frac{1 - \exp\left( -NTU (1 - C_r) \right)}{1 - C_r \exp\left( -NTU (1 - C_r) \right)} \quad (C_r < 1)$$
$$\epsilon = \frac{NTU}{1 + NTU} \quad (C_r = 1)$$
For phase-change heat exchangers (condensers, reboilers), $C_{\max} \to \infty \implies C_r = 0$, reducing to:
$$\epsilon = 1 - \exp(-NTU)$$
regardless of flow configuration.

#### 9.5.4 Conjugate Transient Wall Conduction
In dynamic heat exchanger operations, solid wall thermal inertia induces significant phase lag. The transient wall temperature $T_w(x, t)$ satisfies:
$$\rho_w C_{p,w} A_w \frac{\partial T_w}{\partial t} = k_w A_w \frac{\partial^2 T_w}{\partial x^2} + h_h P_h (T_h(x, t) - T_w(x, t)) - h_c P_c (T_w(x, t) - T_c(x, t))$$
proving that steady-state LMTD is the asymptotic temporal limit $\frac{\partial T_w}{\partial t} \to 0$ with negligible axial wall conduction ($k_w \to 0$).

---

### 9.6 Fluid Machinery and Piping Manifold Networks

Hydraulic networks connect multiple unit operations through conduits, manifolds, and turbomachinery.

#### 9.6.1 Graph-Theoretic Network Formulation
A piping network is modeled as a connected directed graph $\mathcal{G} = (\mathcal{V}, \mathcal{E})$ with $N_n = |\mathcal{V}|$ nodes and $N_e = |\mathcal{E}|$ directed branch conduits.
The topology is represented by the **Node-Arc Incidence Matrix** $\mathbf{A} \in \{-1, 0, +1\}^{N_n \times N_e}$:
$$A_{ie} = \begin{cases} +1 & \text{if branch } e \text{ terminates at node } i \\ -1 & \text{if branch } e \text{ originates at node } i \\ 0 & \text{if branch } e \text{ is not incident on node } i \end{cases}$$

#### 9.6.2 Kirchhoff Continuity and Loop Momentum Balances
1. **Kirchhoff's Flow Law (Continuity at Nodes):**
   For every internal node $i \in \{1, \dots, N_n\}$:
   $$\sum_{e=1}^{N_e} A_{ie} \dot{m}_e + \dot{m}_{\text{source},i} = 0$$
   where $\dot{m}_e$ is the mass flow rate through branch $e$, and $\dot{m}_{\text{source},i}$ is external supply or demand.
2. **Kirchhoff's Pressure Law (Momentum along Branches):**
   Across branch $e$ connecting node $j$ to node $k$:
   $$P_j - P_k + \Delta P_{\text{pump},e} = \Delta P_{\text{friction},e} + \Delta P_{\text{minor},e} + \rho_e g (z_k - z_j) + I_e \frac{d \dot{m}_e}{dt}$$
   where $I_e = \frac{L_e}{A_e}$ is hydraulic inertance (Section 2.9).

The frictional pressure loss $\Delta P_{\text{friction},e}$ is given by the Darcy-Weisbach equation with Churchill's friction factor $f_{D,e}(\text{Re}_e, \epsilon/D_e)$ (Section 2.10):
$$\Delta P_{\text{friction},e} = f_{D,e} \frac{L_e}{D_e} \frac{\dot{m}_e |\dot{m}_e|}{2 \rho_e A_e^2}$$
Minor losses across valves, fittings, and contractions are:
$$\Delta P_{\text{minor},e} = \sum K_{\text{minor}} \frac{\dot{m}_e |\dot{m}_e|}{2 \rho_e A_e^2}$$

#### 9.6.3 Turbomachinery Characteristics and Euler Turbomachine Equation
Pumps and compressors supply head according to angular momentum transfer described by the Euler equation (Section 2.9):
$$H_{\text{Euler}} = \frac{u_2 v_{\theta 2} - u_1 v_{\theta 1}}{g}$$
The actual head curve $\Delta H_{\text{pump}}(\dot{V}, \omega)$ is parameterized by affinity laws across operational angular velocity $\omega$:
$$\Delta H_{\text{pump}}(\dot{V}, \omega) = a_0 \left( \frac{\omega}{\omega_0} \right)^2 + a_1 \left( \frac{\omega}{\omega_0} \right) \dot{V} + a_2 \dot{V}^2$$
The mechanical power consumed and fluid temperature rise are:
$$\dot{W}_{\text{shaft}} = \frac{\rho g \dot{V} \Delta H_{\text{pump}}}{\eta_{\text{pump}}(\dot{V}, \omega)}$$
$$\Delta T_{\text{fluid}} = \frac{g \Delta H_{\text{pump}}}{c_p} \left( \frac{1 - \eta_{\text{pump}}}{\eta_{\text{pump}}} \right)$$

##### Net Positive Suction Head (NPSH) and Cavitation Avoidance
Cavitation occurs if static pressure falls below the fluid vapor pressure at local suction temperature. The available Net Positive Suction Head ($NPSH_A$) must exceed the manufacturer required head ($NPSH_R$):
$$NPSH_A = \frac{P_{\text{suction}} - P^{\text{sat}}(T)}{\rho g} + \frac{v_{\text{suction}}^2}{2 g} > NPSH_R$$
The simulation engine audits $NPSH_A - NPSH_R \ge \Delta H_{\text{margin}}$ at every Newton-Raphson iteration step.


---

### 9.7 Shortcut Distillation and Multicomponent Design Methods

When preliminary design, initialization, or real-time optimization does not warrant solving the full non-linear dynamic MESH-D DAE system, rigorous asymptotic reductions yield classical shortcut distillation formulations.

#### 9.7.1 The McCabe-Thiele Method from MESH-D Asymptotics
The McCabe-Thiele graphical and algebraic method is deduced from the general stage equations (Section 9.2) under the **Constant Molar Overflow (CMO)** assumption:
1. Pure component molar heats of vaporization are approximately equal: $\Delta h_{\text{vap},i} \approx \Delta h_{\text{vap},j}$.
2. Sensible heat effects are negligible compared to latent heat: $C_{p,L} (T_j - T_{j-1}) \ll \Delta h_{\text{vap}}$.
3. Heat of mixing is negligible: $\Delta h_{\text{mix}} \approx 0$.
4. Stage heat losses are zero: $Q_j = 0$ (except condenser and reboiler).

Under these four assumptions, the stage enthalpy balance reduces to constant molar liquid and vapor flows in each section:
$$L_j = L_{j-1} = L \quad \text{and} \quad V_{j+1} = V_j = V$$

##### Operating Lines
* **Rectifying Section Operating Line (ROL):**
  Applying species continuity over an envelope enclosing the condenser down to stage $n$:
  $$y_{n+1} = \frac{L}{V} x_n + \frac{D x_D}{V} = \frac{R}{R + 1} x_n + \frac{x_D}{R + 1}$$
  where $R \equiv L/D$ is the external reflux ratio.
* **Stripping Section Operating Line (SOL):**
  Applying species continuity over an envelope enclosing the reboiler up to stage $m$:
  $$y_{m+1} = \frac{\bar{L}}{\bar{V}} x_m - \frac{B x_B}{\bar{V}} = \frac{V_B + 1}{V_B} x_m - \frac{x_B}{V_B}$$
  where $V_B \equiv \bar{V}/B$ is the boilup ratio.

##### Derivation of the Feed Thermal Condition ($q$-line)
Let $q$ denote the thermal condition parameter of the feed, defined as the moles of liquid entering the stripping section per mole of fresh feed:
$$q \equiv \frac{\bar{L} - L}{F}$$
From the stage energy balance around the feed stage:
$$F h_F + L h_L + \bar{V} h_V = \bar{L} h_L + V h_V$$
Rearranging using $\bar{V} - V = F(1 - q)$:
$$q = \frac{h_V - h_F}{h_V - h_L} = \frac{h_V - h_F}{\Delta h_{\text{vap}}}$$
Subtracting the stripping operating line from the rectifying operating line at the intersection $(x, y)$:
$$V y - \bar{V} y = (L x - \bar{L} x) + (D x_D + B x_B)$$
Using total material balance $D x_D + B x_B = F z_F$:
$$(V - \bar{V}) y = (L - \bar{L}) x + F z_F \implies F (q - 1) y = F q x - F z_F$$
Dividing by $F(q - 1)$ yields the **$q$-line equation**:
$$y = \frac{q}{q - 1} x - \frac{z_F}{q - 1}$$
* If $q > 1$: subcooled liquid feed ($T_F < T_b$).
* If $q = 1$: saturated liquid feed at bubble point ($h_F = h_L$).
* If $0 < q < 1$: two-phase vapor-liquid mixture (vapor fraction $\alpha_V = 1 - q$).
* If $q = 0$: saturated vapor feed at dew point ($h_F = h_V$).
* If $q < 0$: superheated vapor feed ($T_F > T_d$).

##### Minimum Reflux Ratio ($R_{\min}$)
As reflux ratio decreases, the operating lines rotate toward the $q$-line intersection $(x_q, y_q)$. The **minimum reflux ratio** $R_{\min}$ occurs when the operating line intersects the equilibrium curve $y^*(x)$ at the pinch point $(x_p, y_p)$:
$$R_{\min} = \frac{x_D - y_p}{y_p - x_p}$$
where for saturated liquid feed ($q = 1$), the pinch point occurs at $x_p = z_F, y_p = y^*(z_F)$.

#### 9.7.2 The Ponchon-Savarit Method: Enthalpy-Concentration Formulations
When the CMO assumptions fail (significant difference in component heats of vaporization or large heats of mixing), the Ponchon-Savarit method solves simultaneous material and energy balances on the Enthalpy-Concentration ($H-x-y$) diagram.

Let the total enthalpy coordinates of liquid and vapor phases be:
$$h_L(x) = \sum_{i} x_i h_i^L(T) + \Delta h_{\text{mix}}^L, \quad H_V(y) = \sum_{i} y_i H_i^V(T) + \Delta h_{\text{mix}}^V$$
* **Rectifying Difference Point (Distillate Pole $\Delta_D$):**
  Combining overall and component material and energy balances over the top envelope:
  $$x_{\Delta D} = x_D, \quad Q'_D \equiv \frac{Q_C}{D} + h_D$$
* **Stripping Difference Point (Bottoms Pole $\Delta_B$):**
  $$x_{\Delta B} = x_B, \quad Q'_B \equiv -\frac{Q_B}{B} + h_B$$
By the collinearity theorem on the $(x, H)$ plane, the line connecting $\Delta_D$, Feed $F(z_F, h_F)$, and $\Delta_B$ must be straight:
$$F + \Delta_B = \Delta_D \implies \frac{D}{B} = \frac{z_F - x_B}{x_D - z_F} = \frac{h_F - Q'_B}{Q'_D - h_F}$$
Stages are stepped off between the bubble-point and dew-point tie lines and the ray lines originating from $\Delta_D$ and $\Delta_B$.

#### 9.7.3 The Fenske-Underwood-Gilliland (FUG) Multicomponent Shortcut Method
For multicomponent columns ($N_c \ge 3$), the FUG method provides the standard rigorous shortcut solution.

##### 1. The Fenske Equation for Minimum Stages
At total reflux ($R \to \infty, D \to 0, B \to 0$), liquid and vapor flows are infinite, and operating lines collapse to the diagonal $y_{i,j} = x_{i,j-1}$.
For any two components $i$ and $k$, the stage separation ratio is:
$$\frac{y_{i,j}}{y_{k,j}} = \alpha_{ik,j} \frac{x_{i,j}}{x_{k,j}}$$
Since $y_{i,j} = x_{i,j-1}$ and $y_{k,j} = x_{k,j-1}$:
$$\frac{x_{i,j-1}}{x_{k,j-1}} = \alpha_{ik,j} \frac{x_{i,j}}{x_{k,j}}$$
Multiplying across all $N_{\min}$ stages from reboiler ($j = N_{\min}$) to condenser ($j = 1$):
$$\frac{x_{i,D}}{x_{k,D}} = \left( \prod_{j=1}^{N_{\min}} \alpha_{ik,j} \right) \frac{x_{i,B}}{x_{k,B}} = (\bar{\alpha}_{ik})^{N_{\min}} \frac{x_{i,B}}{x_{k,B}}$$
where $\bar{\alpha}_{ik} = (\alpha_{ik,\text{top}} \alpha_{ik,\text{feed}} \alpha_{ik,\text{bottom}})^{1/3}$.
Selecting the Light Key (LK) and Heavy Key (HK) components and solving for $N_{\min}$:
$$N_{\min} = \frac{\ln\left[ \left( \frac{d_{\text{LK}}}{b_{\text{LK}}} \right) \left( \frac{b_{\text{HK}}}{d_{\text{HK}}} \right) \right]}{\ln \bar{\alpha}_{\text{LK,HK}}} = \frac{\ln\left[ \left( \frac{x_{\text{LK},D}}{x_{\text{HK},D}} \right) \left( \frac{x_{\text{HK},B}}{x_{\text{LK},B}} \right) \right]}{\ln \bar{\alpha}_{\text{LK,HK}}}$$

Once $N_{\min}$ is determined, the distribution of all non-key components $i$ is calculated directly from Fenske's ratio:
$$\frac{d_i}{b_i} = \frac{d_{\text{HK}}}{b_{\text{HK}}} (\bar{\alpha}_{i,\text{HK}})^{N_{\min}}$$

##### 2. The Underwood Equations for Minimum Reflux
At minimum reflux $R_{\min}$, an infinite number of stages is required, causing an internal pinch zone where flow rates and compositions satisfy:
$$V_{\min} y_{i} - L_{\min} x_{i} = d_i$$
Substituting the phase equilibrium relationship $y_i = \frac{\alpha_i x_i}{\sum \alpha_k x_k}$ and defining the characteristic parameter $\theta$:
$$1 - q = \sum_{i=1}^{N_c} \frac{\alpha_i z_{i,F}}{\alpha_i - \theta}$$
For $N_c$ components, this polynomial has $N_c$ roots. The active roots $\theta_k$ lie strictly bounded between adjacent relative volatilities:
$$\alpha_1 > \theta_1 > \alpha_2 > \theta_2 > \dots > \alpha_{N_c-1} > \theta_{N_c-1} > \alpha_{N_c}$$
For non-distributed keys where only components between LK and HK split, the single relevant root $\theta$ satisfies $\alpha_{\text{HK}} < \theta < \alpha_{\text{LK}}$.
The minimum vapor flow and reflux ratio $R_{\min}$ are then determined from the second Underwood equation:
$$V_{m,\min} = \sum_{i=1}^{N_c} \frac{\alpha_i d_i}{\alpha_i - \theta} \implies R_{\min} = \frac{V_{m,\min}}{D} - 1 = \sum_{i=1}^{N_c} \frac{\alpha_i x_{i,D}}{\alpha_i - \theta} - 1$$

##### 3. The Gilliland Empirical Correlation
The actual stage count $N$ at a specified operating reflux $R > R_{\min}$ is related to $N_{\min}$ and $R_{\min}$ via Gilliland's empirical curve. Molokanov et al. provided the exact analytical representation:
$$Y = 1 - \exp\left[ \left( \frac{1 + 54.4 X}{11 + 117.2 X} \right) \left( \frac{X - 1}{\sqrt{X}} \right) \right]$$
where the dimensionless coordinates are:
$$X \equiv \frac{R - R_{\min}}{R + 1}, \quad Y \equiv \frac{N - N_{\min}}{N + 1}$$
Inverting for the theoretical stage count $N$:
$$N = \frac{N_{\min} + Y}{1 - Y}$$

##### 4. Kirkbride's Formula for Optimal Feed Stage Location
The ratio of rectifying stages $N_R$ to stripping stages $N_S$ ($N = N_R + N_S$) is estimated from Kirkbride's empirical power law:
$$\frac{N_R}{N_S} = \left[ \left( \frac{z_{\text{HK}}}{z_{\text{LK}}} \right) \left( \frac{x_{\text{LK},B}}{x_{\text{HK},D}} \right)^2 \left( \frac{B}{D} \right) \right]^{0.206}$$

---

### 9.8 Transient Batch Distillation and the Rayleigh Equation

Batch distillation processes a fixed initial charge $W_0$ (moles) of composition $\mathbf{x}_0$ over a finite batch duration $t \in [0, t_{\text{batch}}]$.

```
                     Vapor Boilup: V(t), y^*(t)
                                 ^
                                 |
                        +-----------------+
                        |                 |
                        |    STILL POT    |
                        |   W(t), x(t)    |
                        +-----------------+
```

#### 9.8.1 The Simple Differential Rayleigh Distillation Equation
Consider a differential charge of vapor $dW < 0$ boiled off from the liquid inventory $W(t)$ at instantaneous composition $y^*(t)$ in equilibrium with pot liquid $x(t)$.
The differential material balance is:
$$d(W x) = y^* dW \implies W dx + x dW = y^* dW$$
Separating variables:
$$\frac{dW}{W} = \frac{dx}{y^* - x}$$
Integrating from initial state $(W_0, x_0)$ to remaining state $(W, x_W)$:
$$\ln\left( \frac{W_0}{W} \right) = \int_{x_W}^{x_0} \frac{dx}{y^*(x) - x}$$
which is the classical **Rayleigh Equation**.

##### Analytical Solution for Constant Relative Volatility
For an ideal binary system with constant relative volatility $\alpha \equiv \frac{y / (1 - y)}{x / (1 - x)}$:
$$y^*(x) = \frac{\alpha x}{1 + (\alpha - 1) x}$$
The denominator driving force is:
$$y^* - x = \frac{\alpha x - x - (\alpha - 1) x^2}{1 + (\alpha - 1) x} = \frac{(\alpha - 1) x (1 - x)}{1 + (\alpha - 1) x}$$
Substituting into the Rayleigh integral:
$$\ln\left( \frac{W_0}{W} \right) = \int_{x_W}^{x_0} \frac{1 + (\alpha - 1) x}{(\alpha - 1) x (1 - x)} \, dx$$
Resolving by partial fractions:
$$\frac{1 + (\alpha - 1) x}{x (1 - x)} = \frac{1}{x} + \frac{\alpha}{1 - x}$$
Integrating both terms analytically:
$$\ln\left( \frac{W_0}{W} \right) = \frac{1}{\alpha - 1} \left[ \ln\left( \frac{x_0}{x_W} \right) + \alpha \ln\left( \frac{1 - x_W}{1 - x_0} \right) \right]$$

##### Cumulative Distillate Composition
By overall species balance, total distillate collected $D(t) = W_0 - W(t)$ has average composition:
$$\bar{x}_D(t) = \frac{W_0 x_0 - W(t) x_W(t)}{W_0 - W(t)}$$

#### 9.8.2 Dynamic Batch Rectification with Internal Holdup
When a fractionating column with $N_T$ stages is placed above the still pot, column dynamics interact with pot depletion:
$$\frac{d W}{dt} = -V(t) + L_1(t)$$
$$\frac{d(W x_{W,i})}{dt} = L_1(t) x_{1,i}(t) - V(t) y_{W,i}(t) + R_{W,i}$$
On each tray $j \in \{1, \dots, N_T\}$:
$$H_{\text{tray}} \frac{d x_{j,i}}{dt} = V (y_{j-1,i} - y_{j,i}) + L (x_{j+1,i} - x_{j,i})$$
Two classical operation policies are optimized:
1. **Constant Reflux Ratio ($R(t) = R_{\text{spec}}$):** Distillate composition $x_D(t)$ decreases monotonically over time as pot is depleted in light components.
2. **Variable Reflux Policy ($x_D(t) = x_{D,\text{spec}}$):** Reflux ratio $R(t)$ is continuously increased via feedback control until $R(t) \to R_{\max}$, maintaining on-spec product distillate throughout the run.

---

### 9.9 Continuous Packed Columns and Differential Mass Transfer

Packed columns provide continuous differential contact between counter-current vapor and liquid streams without discrete stage pool discretization.

```
       Vapor Out: V(Z), y(Z)                  Liquid In: L(Z), x(Z)
               ^                                      |
               |                                      v
          +------------------------------------------------+
          |  PACKED BED: Continuous Differential Volume    |
          |  Height: z \in [0, Z], Cross-Section: A_{col}  |
          |  Specific Packing Area: a_{pack} [m^2/m^3]     |
          +------------------------------------------------+
               ^                                      |
               |                                      v
       Vapor In: V(0), y(0)                   Liquid Out: L(0), x(0)
```

#### 9.9.1 Differential Balance Equations along Bed Coordinate
Consider a differential slice of packing height $dz$. The volumetric interphase transfer area is $d A_{\text{int}} = a_{\text{pack}} A_{\text{col}} dz$.
Differential steady-state mass balances:
$$\frac{d V}{dz} = -N_{\text{tot}} a_{\text{pack}} A_{\text{col}}, \quad \frac{d L}{dz} = -N_{\text{tot}} a_{\text{pack}} A_{\text{col}}$$
For species $i$:
$$\frac{d(V y_i)}{dz} = -N_i a_{\text{pack}} A_{\text{col}}, \quad \frac{d(L x_i)}{dz} = -N_i a_{\text{pack}} A_{\text{col}}$$
where $N_i$ is the interphase molar flux derived from two-film Stefan-Maxwell transport (Section 9.3).

#### 9.9.2 HTU-NTU Concept for Dilute or Equimolar Counter-Current Systems
Under dilute or equimolar conditions ($V, L \approx \text{const}$), the overall vapor-phase driving force formulation gives:
$$N_A = K_{OG} (y^* - y)$$
Substituting into the differential balance:
$$V \frac{dy}{dz} = K_{OG} a_{\text{pack}} A_{\text{col}} (y^*(x) - y)$$
Separating variables and integrating from $z = 0$ to $z = Z$:
$$Z = \left( \frac{V}{K_{OG} a_{\text{pack}} A_{\text{col}}} \right) \int_{y_{\text{in}}}^{y_{\text{out}}} \frac{dy}{y^*(x) - y}$$
This yields the classical decomposition:
$$Z = HTU_{OG} \times NTU_{OG}$$
where:
* **Height of an Overall Transfer Unit ($HTU_{OG}$):** Measures separation efficiency of packing geometry and fluid properties:
  $$HTU_{OG} \equiv \frac{V / A_{\text{col}}}{K_{OG} a_{\text{pack}}}$$
* **Number of Overall Transfer Units ($NTU_{OG}$):** Measures separation difficulty:
  $$NTU_{OG} \equiv \int_{y_{\text{in}}}^{y_{\text{out}}} \frac{dy}{y^*(x) - y}$$

##### Two-Film Resistance Addition Rule
The overall gas-phase mass transfer coefficient $K_{OG}$ is related to individual film coefficients $k_G$ and $k_L$ by:
$$\frac{1}{K_{OG}} = \frac{1}{k_G} + \frac{m}{k_L}$$
where $m \equiv \frac{dy^*}{dx}$ is the slope of the equilibrium curve.
In terms of individual transfer units:
$$HTU_{OG} = HTU_G + \lambda \, HTU_L, \quad \lambda \equiv \frac{m V}{L}$$
where $\lambda$ is the **stripping factor**.

#### 9.9.3 Hydraulic Pressure Drop in Packings: The Billet & Schultes Model
The frictional pressure drop across irrigated structured or random packing beds is modeled by Billet & Schultes:
$$\frac{\Delta P}{Z} = \psi_0 \frac{a_{\text{pack}}}{\epsilon_{\text{bed}}^3} \frac{\rho_V u_V^2}{2} \cdot \left( \frac{1}{1 - \frac{h_L}{\epsilon_{\text{bed}}}} \right)^3 \cdot \left[ 1 + 2 \left( \frac{h_L}{d_h} \right) \right]$$
where $\psi_0$ is the dry packing drag coefficient, $\epsilon_{\text{bed}}$ is bed void fraction, $h_L$ is operational volumetric liquid holdup ($m^3_{\text{liq}}/m^3_{\text{bed}}$), and $d_h = 4 \epsilon_{\text{bed}} / a_{\text{pack}}$ is hydraulic diameter.
* **Loading Point:** Occurs when liquid holdup begins to accumulate rapidly due to vapor drag: $\frac{d h_L}{d u_V} \to \infty$.
* **Flooding Point:** Occurs when pressure drop diverges ($\frac{\Delta P}{Z} \ge 2000 \, \text{Pa/m}$), causing liquid backup and column blowout.

---

### 9.10 Liquid-Liquid Extraction (LLE) and Immiscible Decanters

Liquid-Liquid Extraction exploits differences in chemical potentials between two mutually immiscible or partially miscible liquid phases (Feed carrier $F$, Solvent $S$, Extract $E$, Raffinate $R$).

#### 9.10.1 Phase Equilibrium and Distribution Ratios
Equilibrium between light liquid phase ($L_1$) and heavy liquid phase ($L_2$):
$$x_i^{L1} \gamma_i^{L1}(T, P, \mathbf{x}^{L1}) = x_i^{L2} \gamma_i^{L2}(T, P, \mathbf{x}^{L2}) \quad \forall i \in \{1, \dots, N_c\}$$
The distribution coefficient (partition ratio) is:
$$K_{i,LL} \equiv \frac{x_i^{L1}}{x_i^{L2}} = \frac{\gamma_i^{L2}(T, P, \mathbf{x}^{L2})}{\gamma_i^{L1}(T, P, \mathbf{x}^{L1})}$$
The separation selectivity (relative separation factor) between solute $i$ and carrier $j$ is:
$$\beta_{ij} \equiv \frac{K_{i,LL}}{K_{j,LL}} = \left( \frac{\gamma_i^{L2}}{\gamma_j^{L2}} \right) \left( \frac{\gamma_j^{L1}}{\gamma_i^{L1}} \right)$$
Separation by liquid extraction is thermodynamically feasible if and only if $\beta_{ij} \ne 1$.

#### 9.10.2 Multistage Counter-Current Extraction and the Kremser Equation
For an $N$-stage counter-current extraction cascade with straight operating and equilibrium lines ($y = K x$):
The **Extraction Factor** is defined as:
$$E_F \equiv \frac{S \cdot K_{LL}}{F}$$
Solute recovery in the raffinate leaving stage $N$ is given by the Kremser analytical equation:
$$\frac{x_N - y_0 / K}{x_F - y_0 / K} = \frac{E_F - 1}{E_F^{N+1} - 1} \quad (E_F \ne 1)$$
$$\frac{x_N - y_0 / K}{x_F - y_0 / K} = \frac{1}{N + 1} \quad (E_F = 1)$$
Solving for the required number of theoretical stages $N$:
$$N = \frac{\ln\left[ \left( \frac{x_F - y_0 / K}{x_N - y_0 / K} \right) \left( 1 - \frac{1}{E_F} \right) + \frac{1}{E_F} \right]}{\ln E_F}$$

#### 9.10.3 Continuous Gravity Decanter Hydrodynamics
In heterogeneous azeotropic distillation, condensed overhead vapor splits into two immiscible liquid phases inside a gravity decanter.

```
       Feed Mixture: \dot{m}_{\text{tot}} --->  +-----------------------+
                                                |  Light Phase (\rho_L) | ---> Light Overflow: h_{\text{tot}}
                                                | ~~~~~~~~~~~~~~~~~~~~~ | (Interface: z_{\text{int}})
                                                |  Heavy Phase (\rho_H) |
                                                +-----------------------+
                                                            |
                                                            v
                                                  Heavy Underflow Leg: h_{\text{heavy}}
```

##### Hydrostatic Equilibrium and Interface Location
Let the decanter total liquid height be $h_{\text{tot}}$, heavy liquid density be $\rho_H$, light liquid density be $\rho_L$ ($\rho_H > \rho_L$), and interface height from bottom be $z_{\text{int}}$.
Hydrostatic pressure at the decanter vessel floor is:
$$P_{\text{floor}} = P_{\text{head}} + \rho_L g (h_{\text{tot}} - z_{\text{int}}) + \rho_H g z_{\text{int}}$$
Hydrostatic pressure at the base of the external heavy liquid underflow leg of height $h_{\text{heavy}}$ is:
$$P_{\text{floor}} = P_{\text{head}} + \rho_H g h_{\text{heavy}}$$
Equating pressures and dividing by $g$:
$$\rho_L (h_{\text{tot}} - z_{\text{int}}) + \rho_H z_{\text{int}} = \rho_H h_{\text{heavy}}$$
Solving for the interface height $z_{\text{int}}$:
$$z_{\text{int}} = \frac{h_{\text{heavy}} - h_{\text{tot}} \left( \frac{\rho_L}{\rho_H} \right)}{1 - \frac{\rho_L}{\rho_H}}$$
To guarantee a stable interface strictly within vessel bounds ($0 < z_{\text{int}} < h_{\text{tot}}$), the underflow overflow leg height must be calibrated:
$$h_{\text{tot}} \left( \frac{\rho_L}{\rho_H} \right) < h_{\text{heavy}} < h_{\text{tot}}$$

---

### 9.11 Compressible Conduit Gas Dynamics, Fanno/Rayleigh Flow, and Sonic Choking

When vapor velocities in piping manifolds, relief valves, or column chimneys approach the local speed of sound ($c = \sqrt{\gamma R T / M_w}$), fluid compressibility effects dominate.

#### 9.11.1 The One-Dimensional Compressible Euler System with Friction and Heat Transfer
From the 1D steady Navier-Stokes reduction with cross-sectional area $A(x)$, friction factor $f_D$, and heat addition $d q$:
* **Continuity:** $\frac{d\rho}{\rho} + \frac{d v}{v} + \frac{dA}{A} = 0$
* **Momentum:** $\rho v \, dv + dP = -\frac{f_D \rho v^2}{2 D} dx$
* **Energy:** $d h_0 = d\left( h + \frac{v^2}{2} \right) = d q$
* **Equation of State:** $\frac{dP}{P} = \frac{d\rho}{\rho} + \frac{dT}{T}$

Introducing the Mach number $M \equiv v / c = v / \sqrt{\gamma R T}$:
$$\frac{d(M^2)}{M^2} = \frac{2 (1 + \frac{\gamma - 1}{2} M^2)}{1 - M^2} \left[ -\frac{dA}{A} + \frac{\gamma M^2}{2} \left( \frac{4 f_D \, dx}{D} \right) + \frac{1 + \gamma M^2}{2} \frac{d q}{c_p T} \right]$$

#### 9.11.2 Adiabatic Flow with Friction (Fanno Flow)
In a constant-area duct ($dA = 0$) with adiabatic walls ($dq = 0$), wall friction drives flow toward the sonic point:
$$\frac{d(M^2)}{M^2} = \frac{\gamma M^2 \left( 1 + \frac{\gamma - 1}{2} M^2 \right)}{1 - M^2} \left( \frac{4 f_D \, dx}{D} \right)$$
* If $M < 1$ (subsonic): friction accelerates flow ($dM/dx > 0$).
* If $M > 1$ (supersonic): friction decelerates flow ($dM/dx < 0$).
* At $M = 1$: the denominator vanishes ($1 - M^2 \to 0$), indicating **sonic choking**.

Integrating from arbitrary Mach number $M$ to the sonic state $M = 1$ over critical pipe length $L^*$:
$$\frac{4 \bar{f} L^*}{D} = \frac{1 - M^2}{\gamma M^2} + \frac{\gamma + 1}{2 \gamma} \ln\left[ \frac{(\gamma + 1) M^2}{2 \left( 1 + \frac{\gamma - 1}{2} M^2 \right)} \right]$$
If physical pipe length exceeds $L^*$, flow is choked, and mass throughput $\dot{m}$ decreases until the duct exit reaches exactly $M = 1$.

#### 9.11.3 Frictionless Flow with Heat Addition (Rayleigh Flow)
In a constant-area duct ($dA = 0$) without friction ($f_D = 0$), heat transfer $dq$ alters the Mach number:
$$\frac{d(M^2)}{M^2} = \frac{(1 + \gamma M^2) \left( 1 + \frac{\gamma - 1}{2} M^2 \right)}{1 - M^2} \frac{d T_0}{T_0}$$
where $T_0 \equiv T (1 + \frac{\gamma - 1}{2} M^2)$ is stagnation temperature.
* Heating ($d T_0 > 0$) drives subsonic flow toward $M = 1$ and supersonic flow toward $M = 1$.
* **Thermal Choking:** Maximum possible heat addition corresponds to $M_{\text{exit}} = 1$. Attempting to add more heat reduces inlet mass flow rate $\dot{m}$.

---

### 9.12 Acoustic Water Hammer and Method of Characteristics (MOC)

Rapid closure of valves or pump trips in liquid piping manifolds creates destructive transient pressure surge waves (water hammer).

#### 9.12.1 Hyperbolic Wave PDE Formulation
Let $x \in [0, L]$ be the axial coordinate, $P(x, t)$ static pressure, and $v(x, t)$ fluid velocity.
Taking into account fluid bulk modulus $K$ and pipe wall elastic modulus $E$ with wall thickness $e$ and diameter $D$:
* **Continuity Equation:**
  $$\frac{\partial P}{\partial t} + v \frac{\partial P}{\partial x} + \rho c^2 \frac{\partial v}{\partial x} = 0$$
* **Momentum Equation:**
  $$\frac{\partial v}{\partial t} + v \frac{\partial v}{\partial x} + \frac{1}{\rho} \frac{\partial P}{\partial x} + \frac{f_D |v| v}{2 D} + g \sin \theta = 0$$

##### Composite Acoustic Wave Speed ($c$)
The elastic wave propagation velocity $c$ in an elastic conduit is:
$$c \equiv \sqrt{\frac{K / \rho}{1 + c_1 \left( \frac{K}{E} \right) \left( \frac{D}{e} \right)}}$$
where $c_1$ is a boundary support factor ($c_1 = 1 - \nu/2$ for pipes anchored against longitudinal movement, $\nu$ Poisson's ratio). For liquid water in rigid steel conduits, $c \approx 1000 - 1400 \, \text{m/s}$.

#### 9.12.2 Method of Characteristics (MOC) Transformation
Since $v \ll c$, convective terms $v \frac{\partial}{\partial x}$ are neglected relative to wave speed $c \frac{\partial}{\partial x}$.
Multiplying continuity by $\pm \frac{1}{\rho c}$ and adding to momentum:
$$\left( \frac{\partial v}{\partial t} \pm c \frac{\partial v}{\partial x} \right) \pm \frac{1}{\rho c} \left( \frac{\partial P}{\partial t} \pm c \frac{\partial P}{\partial x} \right) + \frac{f_D |v| v}{2 D} + g \sin \theta = 0$$
Recognizing total directional derivatives $\frac{d}{dt} \equiv \frac{\partial}{\partial t} \pm c \frac{\partial}{\partial x}$ along characteristic curves:
* **$C^+$ Characteristic ($\frac{dx}{dt} = +c$):**
  $$dv + \frac{1}{\rho c} dP + \left( \frac{f_D |v| v}{2 D} + g \sin \theta \right) dt = 0$$
* **$C^-$ Characteristic ($\frac{dx}{dt} = -c$):**
  $$dv - \frac{1}{\rho c} dP + \left( \frac{f_D |v| v}{2 D} + g \sin \theta \right) dt = 0$$

##### Riemann Invariants and Grid Discretization
Discretizing space with $\Delta x$ and time with $\Delta t$ satisfying the exact **Courant-Friedrichs-Lewy (CFL) condition**:
$$\Delta t = \frac{\Delta x}{c}$$
For interior grid node $i$ at time step $n+1$:
$$v_i^{n+1} + \frac{P_i^{n+1}}{\rho c} = v_{i-1}^n + \frac{P_{i-1}^n}{\rho c} - \left( \frac{f_D |v_{i-1}^n| v_{i-1}^n}{2 D} \right) \Delta t \quad (C^+ \text{ from } i-1)$$
$$v_i^{n+1} - \frac{P_i^{n+1}}{\rho c} = v_{i+1}^n - \frac{P_{i+1}^n}{\rho c} - \left( \frac{f_D |v_{i+1}^n| v_{i+1}^n}{2 D} \right) \Delta t \quad (C^- \text{ from } i+1)$$
Solving this linear $2 \times 2$ algebraic system gives explicit, unconditionally stable updates for $P_i^{n+1}$ and $v_i^{n+1}$.

#### 9.12.3 The Joukowsky Surge Theorem
For instantaneous valve closure ($\Delta t_{\text{closure}} \le 2 L / c$), the upstream acoustic wave cannot reflect back before flow is completely arrested ($\Delta v = v_0$).
The maximum pressure rise across the wave front is given by the fundamental **Joukowsky Equation**:
$$\Delta P_{\text{max}} = \rho c \Delta v$$
For water ($\rho = 1000 \, \text{kg/m}^3, c = 1200 \, \text{m/s}$) flowing at $v_0 = 2 \, \text{m/s}$:
$$\Delta P_{\text{max}} = 1000 \times 1200 \times 2 = 2.4 \times 10^6 \, \text{Pa} = 2.4 \, \text{MPa} \approx 24 \, \text{bar}$$
proving that rapid valve operations require surge tanks, air vessels, or slow closing profiles.

---

---

## 10. Non-Equilibrium Thermodynamics, Onsager Reciprocity, and Interfacial Marangoni Phenomena

While classical equilibrium thermodynamics (Chapter 3) establishes the phase stability limits ($TPD \ge 0$) and saturation states of static mixtures, industrial reactive separation columns, film evaporators, and multi-phase reactors operate far from thermodynamic equilibrium. In these non-equilibrium domains, irreversible dissipative processes—species diffusion, thermal conduction, viscous shear, interfacial phase change, and chemical reaction—occur simultaneously and couple with one another.

This chapter establishes the rigorous axiomatic framework of non-equilibrium thermodynamics governing the simulation engine, proving entropy production non-negativity ($\sigma_s \ge 0$), deriving the Onsager reciprocal matrix relations, characterizing cross-coupled transport phenomena (Soret and Dufour effects), and detailing interfacial Marangoni instabilities along vapor-liquid surfaces.

---

### 10.1 Local Entropy Production Rate and Second Law Formulation

Consider an open, multicomponent, chemically reacting fluid mixture governed by continuum mechanics. Let $s$ denote the specific entropy per unit mass ($\text{J}/(\text{kg}\cdot\text{K})$), $u$ the specific internal energy ($\text{J}/\text{kg}$), $v \equiv 1/\rho$ the specific volume ($\text{m}^3/\text{kg}$), and $w_i \equiv \rho_i / \rho$ the mass fraction of chemical species $i \in \{1, \dots, N_c\}$.

#### 10.1.1 The Local Fundamental Gibbs Equation
Under the assumption of local thermodynamic equilibrium (which holds across continuum fluid mechanics when molecular collision frequencies greatly exceed macroscopic deformation rates):
$$T \frac{Ds}{Dt} = \frac{Du}{Dt} + P \frac{Dv}{Dt} - \sum_{i=1}^{N_c} \mu_i \frac{Dw_i}{Dt}$$
where $\frac{D}{Dt} \equiv \frac{\partial}{\partial t} + \mathbf{u} \cdot \nabla$ is the material derivative, $T$ is local absolute temperature ($K$), $P$ is thermodynamic pressure ($\text{Pa}$), and $\mu_i$ is the specific chemical potential of species $i$ ($\text{J}/\text{kg}$).

#### 10.1.2 Transport Substitution from Balance Laws
From microscopic mass, momentum, and internal energy balances:
1. **Total Mass Continuity:**
   $$\frac{Dv}{Dt} = v (\nabla \cdot \mathbf{u}) = \frac{1}{\rho} \nabla \cdot \mathbf{u}$$
2. **Species Mass Balances:**
   $$\rho \frac{Dw_i}{Dt} = -\nabla \cdot \mathbf{j}_i + \sum_{r=1}^{N_r} \nu_{ir} M_i r_r$$
   where $\mathbf{j}_i$ is the molecular diffusive mass flux ($\sum_{i=1}^{N_c} \mathbf{j}_i = \mathbf{0}$), $\nu_{ir}$ is stoichiometric coefficient, $M_i$ is molar mass, and $r_r$ is the reaction rate of reaction $r$ per unit volume ($\text{mol}/(\text{m}^3\cdot\text{s})$).
3. **Internal Energy Balance:**
   $$\rho \frac{Du}{Dt} = -\nabla \cdot \mathbf{q} - P (\nabla \cdot \mathbf{u}) + \boldsymbol{\tau} : \nabla \mathbf{u}$$
   where $\mathbf{q}$ is the conductive heat flux vector ($\text{W}/\text{m}^2$) and $\boldsymbol{\tau}$ is the viscous Cauchy deviatoric stress tensor ($\text{Pa}$).

#### 10.1.3 The Entropy Balance Equation
Substituting these balances into the Gibbs equation yields:
$$\rho \frac{Ds}{Dt} = \frac{1}{T} \left( -\nabla \cdot \mathbf{q} + \boldsymbol{\tau} : \nabla \mathbf{u} \right) - \sum_{i=1}^{N_c} \frac{\mu_i}{T} \left( -\nabla \cdot \mathbf{j}_i + \sum_{r=1}^{N_r} \nu_{ir} M_i r_r \right)$$

Applying vector identities for divergence expansions:
$$\frac{1}{T} \nabla \cdot \mathbf{q} = \nabla \cdot \left( \frac{\mathbf{q}}{T} \right) - \mathbf{q} \cdot \nabla \left( \frac{1}{T} \right)$$
$$\frac{\mu_i}{T} \nabla \cdot \mathbf{j}_i = \nabla \cdot \left( \frac{\mu_i \mathbf{j}_i}{T} \right) - \mathbf{j}_i \cdot \nabla \left( \frac{\mu_i}{T} \right)$$

Rearranging into conservative Eulerian form:
$$\frac{\partial (\rho s)}{\partial t} + \nabla \cdot \left( \rho \mathbf{u} s + \mathbf{J}_s \right) = \sigma_s$$

where the **entropy flux vector** $\mathbf{J}_s$ is:
$$\mathbf{J}_s \equiv \frac{\mathbf{q} - \sum_{i=1}^{N_c} \mu_i \mathbf{j}_i}{T}$$
and the **local volumetric entropy production rate** $\sigma_s$ ($\text{W}/(\text{m}^3\cdot\text{K})$) is given by the exact bilinear sum:
$$\sigma_s = \mathbf{q} \cdot \nabla \left(\frac{1}{T}\right) - \sum_{i=1}^{N_c} \mathbf{j}_i \cdot \nabla \left(\frac{\mu_i}{T}\right) + \frac{1}{T} \boldsymbol{\tau} : \nabla \mathbf{u} + \frac{1}{T} \sum_{r=1}^{N_r} \mathcal{A}_r r_r$$

where $\mathcal{A}_r \equiv -\sum_{i=1}^{N_c} \nu_{ir} M_i \mu_i$ is de Donder's **chemical affinity** of reaction $r$.

#### 10.1.4 Second Law Clausius-Duhem Invariant
According to the Second Law of Thermodynamics:
$$\sigma_s(\mathbf{x}, t) \ge 0 \quad \forall \, \mathbf{x} \in \Omega, \quad \forall \, t \ge 0$$
Equality ($\sigma_s = 0$) holds if and only if the system is at reversible thermodynamic equilibrium.

---

### 10.2 Conjugate Thermodynamic Fluxes and Generalized Forces

The local entropy production rate expresses as an inner product of conjugate generalized thermodynamic fluxes $\mathbf{J}_k$ and thermodynamic driving forces $\mathbf{X}_k$:
$$\sigma_s = \sum_k \mathbf{J}_k \odot \mathbf{X}_k \ge 0$$

```
=============================================================================================
Dissipative Phenomenon      Tensorial Rank    Flux Vector/Tensor (J_k)   Conjugate Force (X_k)
=============================================================================================
Thermal Conduction          Vector (Rank 1)   q                          X_q = \nabla(1/T)
Species Molecular Diffusion Vector (Rank 1)   j_i                        X_i = -\nabla(\mu_i/T)
Viscous Shear Stress        Tensor (Rank 2)   \tau^*                     X_v = (1/T) S^*
Bulk Viscous Stress         Scalar (Rank 0)   \Pi^{bulk}                 X_{bulk} = (1/T) \nabla\cdot u
Chemical Reaction           Scalar (Rank 0)   r_r                        X_r = \mathcal{A}_r / T
=============================================================================================
```

#### Curie's Symmetry Principle
In an isotropic medium (a fluid lacking preferred internal spatial orientations), irreversible phenomena of different tensorial character cannot couple with one another in the linear regime:
* Scalar forces (reaction affinity $\mathcal{A}_r/T$, volumetric dilatation $\nabla \cdot \mathbf{u}$) cannot drive vectorial fluxes (heat flux $\mathbf{q}$, mass flux $\mathbf{j}_i$).
* Vectorial forces (thermal gradients $\nabla T$, chemical potential gradients $\nabla \mu_i$) cannot drive symmetric second-order stress tensors $\boldsymbol{\tau}$.
* Second-order deviatoric strain rate tensors $\mathbf{S}^*$ couple exclusively to viscous stress $\boldsymbol{\tau}^*$.

---

### 10.3 The Phenomenological Matrix and Onsager Reciprocal Relations

In the vicinity of thermodynamic equilibrium, the dissipative fluxes are linear functions of the generalized thermodynamic driving forces:
$$J_\alpha = \sum_{\beta} L_{\alpha\beta} X_\beta$$
where $\mathbf{L} = [L_{\alpha\beta}]$ is the phenomenological kinetic coefficient matrix.

#### 10.3.1 The Onsager Reciprocal Theorem
Lars Onsager (1931), building upon the principle of microscopic reversibility of Hamiltonian mechanics and the statistical theory of fluctuations, proved that in the absence of external magnetic fields and Coriolis rotation:
$$L_{\alpha\beta} = L_{\beta\alpha} \quad \forall \, \alpha, \beta$$
When the fluid is subjected to an angular velocity field $\boldsymbol{\Omega}$ or an external magnetic induction field $\mathbf{B}$, the generalized Onsager-Casimir relations govern:
$$L_{\alpha\beta}(\mathbf{B}, \boldsymbol{\Omega}) = L_{\beta\alpha}(-\mathbf{B}, -\boldsymbol{\Omega})$$

#### 10.3.2 Positive Semi-Definiteness and Sylvester's Determinant Criteria
Since the entropy production rate must be non-negative for all admissible states:
$$\sigma_s = \sum_{\alpha} \sum_{\beta} L_{\alpha\beta} X_\alpha X_\beta = \mathbf{X}^T \mathbf{L} \mathbf{X} \ge 0 \quad \forall \, \mathbf{X}$$
Therefore, the phenomenological matrix $\mathbf{L}$ is a symmetric positive semi-definite matrix ($\mathbf{L} \succeq 0$).
By Sylvester's criterion, all principal minors of $\mathbf{L}$ must be non-negative:
1. $L_{\alpha\alpha} \ge 0 \quad \forall \, \alpha$ (direct conduction, diffusion, and viscosity coefficients are non-negative).
2. $L_{\alpha\alpha} L_{\beta\beta} - L_{\alpha\beta}^2 \ge 0 \quad \forall \, \alpha \ne \beta$ (cross-coupling coefficients are strictly bounded by direct dissipation rates).

---

### 10.4 Cross-Coupling Effects: Soret and Dufour Phenomena

The coupling between vectorial thermal forces $\mathbf{X}_q = \nabla(1/T)$ and multicomponent mass forces $\mathbf{X}_i = -\nabla(\mu_i/T)$ yields two fundamental non-equilibrium cross-effects:

```
                  ===========================================
                  |         Cross-Coupled Transports        |
                  ===========================================
                                       |
            +--------------------------+--------------------------+
            |                                                     |
            v                                                     v
    [ Soret Effect ]                                      [ Dufour Effect ]
  Thermal Diffusion                                      Diffusion Thermo-Effect
  \nabla T  ===>  j_i                                    \nabla x_i  ===>  q
  Concentration gradient                                 Heat flux induced
  induced by temperature                                 by chemical potential
  gradients in columns.                                  concentration gradients.
```

#### 10.4.1 Coupled Constitutive Flux Equations
For a binary mixture, the linear phenomenological laws state:
$$\mathbf{q} = L_{qq} \nabla\left(\frac{1}{T}\right) + L_{q1} \left( -\nabla\frac{\mu_1 - \mu_2}{T} \right)$$
$$\mathbf{j}_1 = L_{1q} \nabla\left(\frac{1}{T}\right) + L_{11} \left( -\nabla\frac{\mu_1 - \mu_2}{T} \right)$$

By Onsager reciprocity:
$$L_{q1} = L_{1q}$$

#### 10.4.2 The Soret Effect (Thermal Diffusion)
Expanding the chemical potential gradient at constant pressure:
$$\nabla \left( \frac{\mu_1 - \mu_2}{T} \right) = \frac{1}{T} \left( \frac{\partial(\mu_1 - \mu_2)}{\partial w_1} \right)_{T, P} \nabla w_1 - \frac{h_1 - h_2}{T^2} \nabla T$$

Substituting into the species mass flux:
$$\mathbf{j}_1 = -\rho D_{12} \nabla w_1 - \rho D_T \nabla T$$
where $D_{12}$ is the isothermal binary diffusion coefficient and $D_T$ is the **thermal diffusion coefficient** ($\text{m}^2/(\text{s}\cdot\text{K})$).
Defining the **Soret coefficient** $S_T$:
$$S_T \equiv \frac{D_T}{D_{12} w_1 w_2}$$
In non-isothermal reactive distillation trays with heavy boiling components, $S_T \sim 10^{-3} - 10^{-5} \, \text{K}^{-1}$, driving significant thermal demixing across high-flux reboiler surfaces.

#### 10.4.3 The Dufour Effect (Diffusion Thermo-Effect)
Substituting the Onsager relation into the heat flux equation:
$$\mathbf{q} = -k \nabla T + \mathbf{q}_{\text{Dufour}}$$
$$\mathbf{q}_{\text{Dufour}} \equiv \rho w_1 \left( \frac{\partial \mu_1}{\partial w_1} \right)_{T, P} T S_T D_{12} \nabla w_1$$
While negligible in dense liquid mixtures, the Dufour heat flux produces up to a $5-8\%$ shift in interfacial temperatures in low-density multicomponent vapor films and transient azeotropic flash zones.

---

### 10.5 Interfacial Non-Equilibrium Jump Thermodynamics and Surface Excess Balances

Across a vapor-liquid or liquid-liquid phase interface $\Sigma(t)$, thermodynamic properties experience steep nanometer-scale transitions. In continuum mechanics, this transition layer is modeled as a 2D singular Gibbs dividing surface endowed with surface excess properties.

#### 10.5.1 Surface Metric and Tangential Differential Operators
Let $\mathbf{n}$ be the unit normal vector pointing from liquid phase $L$ into vapor phase $G$.
The **surface projection tensor** $\mathbf{I}_s$ is:
$$\mathbf{I}_s \equiv \mathbf{I} - \mathbf{n} \otimes \mathbf{n}$$
The **surface gradient** $\nabla_s$ and **surface divergence** of a vector $\mathbf{v}$ are:
$$\nabla_s \equiv \mathbf{I}_s \cdot \nabla = \nabla - \mathbf{n} (\mathbf{n} \cdot \nabla)$$
$$\nabla_s \cdot \mathbf{v} \equiv \text{tr}(\nabla_s \mathbf{v}) = \nabla \cdot \mathbf{v} - \mathbf{n} \cdot (\nabla \mathbf{v}) \cdot \mathbf{n}$$
The **mean interfacial curvature** $\kappa$ is defined by:
$$2 \kappa \equiv -\nabla_s \cdot \mathbf{n}$$

#### 10.5.2 Surface Excess Conservation Laws
Let $\rho_\sigma$ denote the surface excess mass density ($\text{kg}/\text{m}^2$), $\mathbf{u}_\sigma$ the surface tangential velocity, and $\mathbf{w}$ the interface displacement velocity.
1. **Surface Mass Conservation:**
   $$\frac{\partial_s \rho_\sigma}{\partial t} + \nabla_s \cdot (\rho_\sigma \mathbf{u}_\sigma) = - [[\rho (\mathbf{u} - \mathbf{w}) \cdot \mathbf{n}]]$$
   where $[[ \psi ]] \equiv \psi^G - \psi^L$ denotes the jump discontinuity across the interface.
2. **Surface Cauchy Momentum Balance:**
   $$\rho_\sigma \left( \frac{\partial_s \mathbf{u}_\sigma}{\partial t} + (\mathbf{u}_\sigma \cdot \nabla_s) \mathbf{u}_\sigma \right) = \nabla_s \cdot \boldsymbol{\sigma}_\sigma - [[\boldsymbol{\sigma} \cdot \mathbf{n}]] + \rho_\sigma \mathbf{g}$$
   where $\boldsymbol{\sigma}_\sigma = \sigma \mathbf{I}_s$ is the surface stress tensor ($\sigma$ surface tension, $\text{N}/\text{m}$).
   Expanding the surface stress divergence:
   $$\nabla_s \cdot (\sigma \mathbf{I}_s) = \nabla_s \sigma + \sigma (\nabla_s \cdot \mathbf{I}_s) = \nabla_s \sigma - 2 \kappa \sigma \mathbf{n}$$

Projecting momentum normal and tangential to the interface yields:
* **Normal Momentum Jump (Young-Laplace Equation with Dynamic Tractions):**
  $$[[P]] - [[\mathbf{n} \cdot \boldsymbol{\tau} \cdot \mathbf{n}]] = 2 \kappa \sigma + \rho_\sigma (\mathbf{g} \cdot \mathbf{n})$$
* **Tangential Momentum Jump (Marangoni Shear Traction):**
  $$[[\mathbf{n} \cdot \boldsymbol{\tau} \cdot \mathbf{t}]] = \nabla_s \sigma \cdot \mathbf{t}$$
  where $\mathbf{t}$ is any unit tangent vector in the surface plane ($\mathbf{t} \cdot \mathbf{n} = 0$).

---

### 10.6 Marangoni Convection and Interfacial Surfactant/Thermal Instabilities

Whenever surface tension varies along the interface, the gradient $\nabla_s \sigma$ generates an interfacial shear stress that pulls fluid from regions of low surface tension toward regions of high surface tension.

#### 10.6.1 Total Surface Tension Differential
Surface tension depends on local temperature $T$ and liquid-phase surfactant/species mole fractions $x_i$:
$$\nabla_s \sigma = \left( \frac{\partial \sigma}{\partial T} \right)_{x} \nabla_s T + \sum_{i=1}^{N_c-1} \left( \frac{\partial \sigma}{\partial x_i} \right)_{T, x_{j \ne i}} \nabla_s x_i$$

In pure fluids and most organic mixtures, surface tension decreases monotonically with temperature:
$$\gamma_T \equiv -\frac{\partial \sigma}{\partial T} > 0 \quad (\sim 10^{-4} \, \text{N}/(\text{m}\cdot\text{K}))$$
In alcohol-water mixtures, surface tension decreases sharply with alcohol concentration:
$$\gamma_c \equiv -\frac{\partial \sigma}{\partial x_{\text{alc}}} > 0$$

#### 10.6.2 Dimensionless Marangoni Numbers
The ratio of interfacial Marangoni shear forces to dissipative viscous and diffusive transport defines the characteristic dimensionless numbers:
* **Thermal Marangoni Number:**
  $$Ma_T \equiv \frac{\gamma_T \, \Delta T \, d}{\mu \, \alpha}$$
  where $d$ is liquid film thickness ($\text{m}$), $\mu$ is dynamic viscosity ($\text{Pa}\cdot\text{s}$), and $\alpha \equiv k / (\rho c_p)$ is thermal diffusivity ($\text{m}^2/\text{s}$).
* **Solutal (Concentration) Marangoni Number:**
  $$Ma_c \equiv \frac{\gamma_c \, \Delta c \, d}{\mu \, D_{12}}$$

#### 10.6.3 Linear Stability of Falling Liquid Films
In falling film evaporators and reactive distillation packing surfaces, linear stability analysis of perturbation modes $\phi'(x, y, z, t) = \hat{\phi}(y) \exp(\omega t + i k_x x + i k_z z)$ reveals a critical threshold:
$$Ma_T > Ma_{\text{crit}} \approx 79.6$$
When $Ma_T > Ma_{\text{crit}}$, planar liquid rivulets experience **Bénard-Marangoni cellular convection**, breaking continuous liquid wetting films into dryout patches and localized hotspots, which drastically degrades packing mass transfer efficiency.

---

### 10.7 Positive Entropy Generation Certification in Equation-Oriented Compilers

To prevent unphysical solver trajectories, non-physical flash states, or artificial negative mass fractions, the simulation engine embeds a Second Law audit operator within the symbolic compilation graph:

```
  [ Engine Balance Engine ] ===> Computes { u_c, T_c, w_{i,c}, \tau_c, q_c, j_{i,c}, r_{r,c} }
                                               |
                                               v
                             [ Integral Entropy Production Evaluator ]
                                \sigma_{s, c} = \int_{\Omega_c} \sigma_s \, dV
                                               |
                                               v
                                   { Is \sigma_{s, c} >= -\epsilon_tol ? }
                                    /                           \
                                  (YES)                         (NO)
                                   /                               \
                         [ Step Accepted ]              [ Execution Aborted ]
                                                        Violation Diagnostic:
                                                        - Negative concentrations
                                                        - Non-monotonic EOS branch
                                                        - Numerical Gibbs dispersion
```

For every discrete finite volume cell or lumped vessel $c$, the engine calculates:
$$\sigma_{s, c} \equiv \int_{\Omega_c} \left[ \mathbf{q} \cdot \nabla\left(\frac{1}{T}\right) - \sum_{i=1}^{N_c} \mathbf{j}_i \cdot \nabla\left(\frac{\mu_i}{T}\right) + \frac{1}{T} \boldsymbol{\tau} : \nabla \mathbf{u} + \frac{1}{T} \sum_{r=1}^{N_r} \mathcal{A}_r r_r \right] dV$$
If $\sigma_{s, c} < -\epsilon_{\text{tol}}$ with $\epsilon_{\text{tol}} \equiv 10^{-11} \, \text{W}/\text{K}$, the integrator rejects the time step and triggers adaptive bisection.



---

## 11. Turbulence Closures and Multiphysics Reynolds-Averaged Transport on Unstructured Polyhedra

When fluid flows in chemical reactors, feed distributors, pipe networks, or separation columns exceed transitional Reynolds numbers ($Re \equiv \rho U D_h / \mu \gtrsim 2300 - 4000$), flow transitions from smooth laminar streamlines to chaotic, three-dimensional, time-dependent turbulent motions across a wide spectrum of spatial and temporal scales (Kolmogorov cascade from integral scales $L$ down to dissipative scales $\eta \equiv (\nu^3 / \epsilon)^{1/4}$).

Direct Numerical Simulation (DNS) resolving all scales requires $\mathcal{O}(Re^{9/4})$ spatial degrees of freedom, rendering it computationally intractable for industrial multiphysics modeling. Consequently, the simulation engine implements an equation-oriented hierarchy of **Reynolds-Averaged Navier-Stokes (RANS)** closures, **Large Eddy Simulation (LES)** subgrid models, and hybrid **Detached Eddy Simulation (DES)** formulations discretized directly on unstructured polyhedral, hexagonal, and simplicial grids.

---

### 11.1 The Reynolds Averaging Operator and the Reynolds Stress Closure Problem

#### 11.1.1 Reynolds Decomposition
In statistically stationary or slowly varying flows, any instantaneous transport quantity $\phi(\mathbf{x}, t)$ (such as velocity $\mathbf{u}$, pressure $P$, temperature $T$, or concentration $c_i$) decomposes into an ensemble or time-averaged mean component $\overline{\phi}(\mathbf{x}, t)$ and a fluctuating component $\phi'(\mathbf{x}, t)$:
$$\phi(\mathbf{x}, t) = \overline{\phi}(\mathbf{x}, t) + \phi'(\mathbf{x}, t)$$
where the averaging operator satisfies Reynolds' averaging postulates:
$$\overline{\overline{\phi}} = \overline{\phi}, \quad \overline{\phi'} = 0, \quad \overline{\overline{\phi} \psi'} = 0, \quad \overline{\phi + \psi} = \overline{\phi} + \overline{\psi}, \quad \overline{\frac{\partial \phi}{\partial x_k}} = \frac{\partial \overline{\phi}}{\partial x_k}$$

In variable-density compressible or multi-component mixtures, **Favre mass-weighted averaging** avoids turbulent density-velocity correlations:
$$\widetilde{\phi} \equiv \frac{\overline{\rho \phi}}{\overline{\rho}}, \quad \phi = \widetilde{\phi} + \phi'', \quad \overline{\rho \phi''} = 0$$

#### 11.1.2 Reynolds-Averaged Navier-Stokes (RANS) Equations
Applying the Reynolds averaging operator to the incompressible Navier-Stokes momentum equations:
$$\nabla \cdot \overline{\mathbf{u}} = 0$$
$$\rho \left[ \frac{\partial \overline{\mathbf{u}}}{\partial t} + (\overline{\mathbf{u}} \cdot \nabla) \overline{\mathbf{u}} \right] = -\nabla \overline{P} + \nabla \cdot \left( 2 \mu \overline{\mathbf{S}} + \boldsymbol{\tau}^R \right) + \rho \mathbf{g}$$
where $\overline{\mathbf{S}} \equiv \frac{1}{2}(\nabla \overline{\mathbf{u}} + (\nabla \overline{\mathbf{u}})^T)$ is the mean strain rate tensor, and $\boldsymbol{\tau}^R$ is the symmetric second-order **Reynolds stress tensor**:
$$\boldsymbol{\tau}^R \equiv -\rho \, \overline{\mathbf{u}' \otimes \mathbf{u}'} = -\rho \begin{bmatrix} \overline{u'^2} & \overline{u'v'} & \overline{u'w'} \\ \overline{u'v'} & \overline{v'^2} & \overline{v'w'} \\ \overline{u'w'} & \overline{v'w'} & \overline{w'^2} \end{bmatrix}$$

Because the six independent components of $\boldsymbol{\tau}^R$ are unknown a priori, the system is unclosed (the fundamental **closure problem of turbulence**).

---

### 11.2 Boussinesq Turbulent Viscosity Hypothesis and Realizability Constraints

#### 11.2.1 The Boussinesq Eddy Viscosity Assumption
Joseph Boussinesq (1877) hypothesized that the turbulent momentum transport driven by Reynolds stresses can be modeled by analogy to molecular momentum diffusion, proportional to the mean rate of strain:
$$\boldsymbol{\tau}^R = 2 \mu_t \overline{\mathbf{S}}^* - \frac{2}{3} \rho k \mathbf{I}$$
where:
* $\mu_t(\mathbf{x}, t)$ is the scalar **turbulent eddy viscosity** ($\text{Pa}\cdot\text{s}$), a property of the local turbulent flow field (not a thermodynamic fluid property).
* $k \equiv \frac{1}{2} \text{tr}(\overline{\mathbf{u}' \otimes \mathbf{u}'}) = \frac{1}{2} (\overline{u'^2} + \overline{v'^2} + \overline{w'^2})$ is the **turbulent kinetic energy** per unit mass ($\text{m}^2/\text{s}^2$).
* $\overline{\mathbf{S}}^* \equiv \overline{\mathbf{S}} - \frac{1}{3} (\nabla \cdot \overline{\mathbf{u}}) \mathbf{I}$ is the deviatoric mean strain rate tensor.

#### 11.2.2 Lumley Realizability Constraints
For any physical velocity fluctuation field, the Reynolds stress tensor must be positive semi-definite ($\boldsymbol{\tau}^R \succeq 0$). Lumley (1978) established three realizability conditions:
1. Non-negative normal stresses: $\overline{u_\alpha'^2} \ge 0 \quad \forall \, \alpha \in \{1, 2, 3\}$.
2. Cauchy-Schwarz cross-correlation bounds: $(\overline{u_\alpha' u_\beta'})^2 \le \overline{u_\alpha'^2} \, \overline{u_\beta'^2}$.
3. Determinant non-negativity: $\det(\overline{\mathbf{u}' \otimes \mathbf{u}'}) \ge 0$.

Under pure shear flow $S = \partial \bar{u}/\partial y$, the standard Boussinesq relation yields $\overline{u'^2} = \frac{2}{3} k - 2 \nu_t \frac{\partial \bar{u}}{\partial x} = \frac{2}{3}k$. However, in regions of strong streamline curvature or rapid deceleration (e.g. impinging jet zones in reactor baffles), standard linear models violate realizability by predicting negative normal stresses ($\overline{v'^2} < 0$).

#### 11.2.3 The Kato-Launder Production Limiter
In stagnation flows where $\overline{\mathbf{u}}$ decelerates against a wall or baffle, the strain rate $S \equiv \sqrt{2 \overline{\mathbf{S}} : \overline{\mathbf{S}}}$ is large while vorticity $\Omega \equiv \sqrt{2 \overline{\boldsymbol{\Omega}} : \overline{\boldsymbol{\Omega}}}$ vanishes ($\overline{\boldsymbol{\Omega}} \equiv \frac{1}{2}(\nabla \overline{\mathbf{u}} - (\nabla \overline{\mathbf{u}})^T)$ is the mean rotation tensor). Standard models calculate turbulent kinetic energy production as $P_k = \mu_t S^2$, producing a catastrophic unphysical spike in $k$ (the "stagnation point anomaly").
The engine implements the Kato-Launder modification:
$$P_k^{\text{KL}} \equiv \mu_t S \Omega$$
In simple shear flows, $S \approx \Omega$, recovering $P_k = \mu_t S^2$. In irrotational stagnation flows, $\Omega \to 0$, suppressing artificial turbulence production.

---

### 11.3 Two-Equation Eddy-Viscosity Models: Standard $k-\epsilon$ and Launder-Sharma Formulation

The standard two-equation $k-\epsilon$ model computes turbulent velocity and length scales from two transport PDEs: turbulent kinetic energy $k$ and its viscous dissipation rate $\epsilon \equiv 2 \nu \overline{\mathbf{S}' : \mathbf{S}'}$.

#### 11.3.1 Transport PDEs
$$\frac{\partial (\rho k)}{\partial t} + \nabla \cdot (\rho \overline{\mathbf{u}} k) = \nabla \cdot \left[ \left( \mu + \frac{\mu_t}{\sigma_k} \right) \nabla k \right] + P_k - \rho \epsilon$$
$$\frac{\partial (\rho \epsilon)}{\partial t} + \nabla \cdot (\rho \overline{\mathbf{u}} \epsilon) = \nabla \cdot \left[ \left( \mu + \frac{\mu_t}{\sigma_\epsilon} \right) \nabla \epsilon \right] + C_{\epsilon 1} \frac{\epsilon}{k} P_k - C_{\epsilon 2} \rho \frac{\epsilon^2}{k}$$

The turbulent eddy viscosity is computed from Kolmogorov-Prandtl dimensional scaling:
$$\mu_t = \rho C_\mu \frac{k^2}{\epsilon}$$

Standard empirical closure coefficients calibrated against homogeneous isotropic turbulence and flat-plate boundary layers:
$$C_\mu = 0.09, \quad C_{\epsilon 1} = 1.44, \quad C_{\epsilon 2} = 1.92, \quad \sigma_k = 1.0, \quad \sigma_\epsilon = 1.3$$

#### 11.3.2 Low-Reynolds Launder-Sharma Formulation
Near solid walls, turbulent motions are damped by molecular viscosity. The Launder-Sharma formulation incorporates damping functions $f_\mu, f_1, f_2$ depending on the turbulent Reynolds number $Re_t \equiv \frac{\rho k^2}{\mu \tilde{\epsilon}}$:
$$\mu_t = \rho C_\mu f_\mu \frac{k^2}{\tilde{\epsilon}}$$
$$f_\mu = \exp\left( \frac{-3.4}{(1 + Re_t / 50)^2} \right)$$
$$f_1 = 1.0, \quad f_2 = 1.0 - 0.3 \exp(-Re_t^2)$$
where $\tilde{\epsilon} \equiv \epsilon - 2 \frac{\mu}{\rho} (\nabla \sqrt{k})^2$ vanishes identically at solid wall boundaries ($y = 0$).

#### 11.3.3 Wall Functions for Coarse Grids
When mesh resolution near solid boundaries is coarse ($y^+ \equiv \frac{\rho u_\tau y}{\mu} \in [30, 300]$, where $u_\tau \equiv \sqrt{\tau_w / \rho}$ is friction velocity), the cell center lies within the fully turbulent logarithmic layer:
$$u^+ \equiv \frac{\overline{u}}{u_\tau} = \frac{1}{\kappa} \ln(E y^+)$$
with von Kármán constant $\kappa \approx 0.41$ and roughness parameter $E \approx 9.8$ for hydraulically smooth walls.
The wall shear stress is evaluated as:
$$\tau_w = \rho u_\tau^2 = \rho \left( \frac{\kappa \overline{u}_P}{\ln(E y_P^+)} \right)^2$$
Boundary values for $k$ and $\epsilon$ in the wall-adjacent cell centroid $P$ are prescribed algebraically:
$$k_P = \frac{u_\tau^2}{\sqrt{C_\mu}}, \quad \epsilon_P = \frac{u_\tau^3}{\kappa y_P}$$

---

### 11.4 Menter Shear Stress Transport (SST) $k-\omega$ Model with Spatial Blending

The Wilcox $k-\omega$ model utilizes the specific dissipation rate $\omega \equiv \frac{\epsilon}{C_\mu k}$ ($\text{s}^{-1}$), behaving robustly in viscous sublayers without damping functions ($f_\mu \equiv 1$), but is notoriously sensitive to free-stream boundary conditions. Conversely, $k-\epsilon$ is insensitive to free-stream turbulence but inaccurate in adverse pressure gradient boundary layers.
Florian Menter (1994) developed the **Shear Stress Transport (SST) $k-\omega$ model**, which applies spatial blending functions $F_1, F_2$ to smoothly transition from Wilcox $k-\omega$ near walls to standard $k-\epsilon$ in outer wake flows.

#### 11.4.1 Blended SST Equations
$$\frac{\partial (\rho k)}{\partial t} + \nabla \cdot (\rho \overline{\mathbf{u}} k) = \nabla \cdot \left[ \left( \mu + \sigma_k \mu_t \right) \nabla k \right] + \tilde{P}_k - \beta^* \rho k \omega$$
$$\frac{\partial (\rho \omega)}{\partial t} + \nabla \cdot (\rho \overline{\mathbf{u}} \omega) = \nabla \cdot \left[ \left( \mu + \sigma_\omega \mu_t \right) \nabla \omega \right] + \frac{\gamma}{\nu_t} \tilde{P}_k - \beta \rho \omega^2 + 2 (1 - F_1) \frac{\rho \sigma_{\omega 2}}{\omega} \nabla k \cdot \nabla \omega$$

The final term is the **cross-diffusion term**, arising mathematically when transforming $\epsilon$ into $\omega$.

#### 11.4.2 Blending Function $F_1$
$$F_1 = \tanh\left( \arg_1^4 \right)$$
$$\arg_1 \equiv \min\left[ \max\left( \frac{\sqrt{k}}{\beta^* \omega y}, \frac{500 \nu}{y^2 \omega} \right), \frac{4 \rho \sigma_{\omega 2} k}{CD_{k\omega} y^2} \right]$$
where $y$ is the shortest distance to the nearest solid wall, and:
$$CD_{k\omega} \equiv \max\left( 2 \rho \sigma_{\omega 2} \frac{1}{\omega} \nabla k \cdot \nabla \omega, 10^{-10} \right)$$
* Inside the boundary layer ($y \to 0$): $\arg_1 \gg 1 \implies F_1 \to 1$ (Wilcox $k-\omega$ formulation).
* In the free stream ($y \to \infty$): $\arg_1 \ll 1 \implies F_1 \to 0$ (transformed $k-\epsilon$ formulation).

Any closure coefficient $\phi \in \{\sigma_k, \sigma_\omega, \beta, \gamma\}$ blends according to:
$$\phi = F_1 \phi_1 + (1 - F_1) \phi_2$$
with standard inner constants $\phi_1 = (\sigma_{k1}=0.85, \sigma_{\omega 1}=0.5, \beta_1=0.075, \beta^*=0.09)$ and outer constants $\phi_2 = (\sigma_{k2}=1.0, \sigma_{\omega 2}=0.856, \beta_2=0.0828)$.

#### 11.4.3 Bradshaw Eddy Viscosity Limiter
In boundary layers with adverse pressure gradients, turbulent shear stress $\tau = -\rho \overline{u'v'}$ is proportional to turbulent kinetic energy $k$ (Bradshaw's assumption: $\tau \approx a_1 \rho k$ with $a_1 = 0.31$). Standard models overpredict eddy viscosity:
$$\mu_t = \frac{\rho a_1 k}{\max(a_1 \omega, S F_2)}$$
$$F_2 \equiv \tanh\left( \arg_2^2 \right), \quad \arg_2 \equiv \max\left( \frac{2 \sqrt{k}}{\beta^* \omega y}, \frac{500 \nu}{y^2 \omega} \right)$$
This prevents premature boundary layer detachment and accurately predicts separation points in curved diffuser geometries and column downcomers.

---

### 11.5 Large Eddy Simulation (LES): Top-Hat Filtering and the WALE Subgrid Model

In Large Eddy Simulation (LES), large energy-containing turbulent eddies are resolved directly on the computational grid, while small, isotropic dissipative eddies are filtered out and modeled through a **Subgrid-Scale (SGS)** stress tensor.

#### 11.5.1 Spatial Filtering Operation
Let $G(\mathbf{x}, \mathbf{x}', \Delta)$ be a spatial filter kernel with characteristic cutoff width $\Delta$.
The filtered field $\overline{\phi}(\mathbf{x}, t)$ is:
$$\overline{\phi}(\mathbf{x}, t) \equiv \int_{\Omega} G(\mathbf{x}, \mathbf{x}', \Delta) \phi(\mathbf{x}', t) \, d\mathbf{x}'$$
On arbitrary polyhedral finite volume cells, the implicit cell-averaging filter defines the cutoff width as the cube root of the cell volume:
$$\Delta \equiv (\Omega_c)^{1/3}$$

#### 11.5.2 Filtered Incompressible Navier-Stokes Equations
$$\nabla \cdot \overline{\mathbf{u}} = 0$$
$$\frac{\partial \overline{\mathbf{u}}}{\partial t} + \nabla \cdot (\overline{\mathbf{u}} \otimes \overline{\mathbf{u}}) = -\frac{1}{\rho}\nabla \overline{P} + \nu \nabla^2 \overline{\mathbf{u}} - \nabla \cdot \boldsymbol{\tau}^{\text{SGS}}$$
where the subgrid-scale stress tensor is:
$$\boldsymbol{\tau}^{\text{SGS}} \equiv \overline{\mathbf{u} \otimes \mathbf{u}} - \overline{\mathbf{u}} \otimes \overline{\mathbf{u}}$$

#### 11.5.3 The Wall-Adapting Local Eddy-viscosity (WALE) Model
The classic Smagorinsky model ($\mu_{\text{SGS}} = \rho (C_s \Delta)^2 S$) fails near solid walls because $S \ne 0$ at $y=0$, predicting unphysical non-zero eddy viscosity without empirical Van Driest wall damping ($1 - e^{-y^+ / 26}$).
Nicoud and Ducros (1999) formulated the **Wall-Adapting Local Eddy-viscosity (WALE) model**, which relies on the traceless symmetric part of the square of the velocity gradient tensor:
$$\bar{g}_{ij} \equiv \frac{\partial \bar{u}_i}{\partial x_j}$$
$$S_{ij}^d \equiv \frac{1}{2} \left( \bar{g}_{ik}\bar{g}_{kj} + \bar{g}_{jk}\bar{g}_{ki} \right) - \frac{1}{3} \delta_{ij} \bar{g}_{kk}^2$$

The SGS eddy viscosity is given by:
$$\mu_{\text{SGS}} = \rho (C_w \Delta)^2 \frac{\left( S_{ij}^d S_{ij}^d \right)^{3/2}}{\left( \bar{S}_{ij} \bar{S}_{ij} \right)^{5/2} + \left( S_{ij}^d S_{ij}^d \right)^{5/4}}$$
where $C_w \approx 0.325$.
##### Theoretical Properties of WALE:
1. **Asymptotic Near-Wall Scaling:** Near a solid wall, $S_{ij}^d S_{ij}^d = \mathcal{O}(y^2)$, while $\bar{S}_{ij} \bar{S}_{ij} = \mathcal{O}(1)$. Substituting gives:
   $$\mu_{\text{SGS}} = \mathcal{O}\left( \frac{(y^2)^{3/2}}{1 + (y^2)^{5/4}} \right) = \mathcal{O}(y^3)$$
   matching the exact physical behavior of Reynolds stresses in the viscous sublayer without explicit wall distance calculations.
2. **Zero Dissipation in Pure Rotation:** In pure solid body rotation ($\overline{\mathbf{S}} = \mathbf{0}$), $S_{ij}^d = 0 \implies \mu_{\text{SGS}} = 0$, avoiding unphysical artificial damping of coherent vortex cores.

---

### 11.6 Detached Eddy Simulation (DES/DDES) for Industrial Separation Units

In industrial packed columns and large baffled reactors, full wall-resolved LES ($y^+ \sim 1, \Delta x^+ \sim 30, \Delta z^+ \sim 15$) requires hundreds of millions of cells in near-wall boundary layers.
**Detached Eddy Simulation (DES)** combines RANS in attached thin boundary layers with LES in massive separated wake zones.

#### 11.6.1 Delayed Detached Eddy Simulation (DDES) Formulation
The turbulent length scale in the SST $k-\omega$ dissipation term is modified:
$$\tilde{d} \equiv d_w - f_d \max(0, d_w - C_{\text{DES}} \Delta_{\text{max}})$$
where $d_w$ is the wall distance, $\Delta_{\text{max}} = \max(\Delta x, \Delta y, \Delta z)$, $C_{\text{DES}} = 0.61$, and $f_d$ is the **delay shielding function**:
$$f_d \equiv 1 - \tanh\left( [8 r_d]^3 \right), \quad r_d \equiv \frac{\nu_t + \nu}{\kappa^2 y^2 \sqrt{2 \overline{\mathbf{S}} : \overline{\mathbf{S}}}}$$
* When $r_d \gg 1$ (inside attached boundary layer): $f_d = 0 \implies \tilde{d} = d_w$ (pure RANS mode, independent of grid spacing).
* When $r_d \ll 1$ (in detached shear layers and core flows): $f_d = 1 \implies \tilde{d} = C_{\text{DES}} \Delta_{\text{max}}$ (subgrid LES mode).

This avoids **Grid-Induced Separation (GIS)** caused by mesh refinement within the attached boundary layer.

---

### 11.7 Turbulent Heat and Mass Transfer: Reynolds-Colburn Analogy

Applying Reynolds averaging to species mass and energy conservation balances reveals turbulent fluxes:
$$\mathbf{j}_i^R \equiv -\rho \overline{\mathbf{u}' w_i'}, \quad \mathbf{q}^R \equiv \rho c_p \overline{\mathbf{u}' T'}$$

#### 11.7.1 Turbulent Gradient Diffusion Hypothesis
Analogous to Boussinesq momentum closure:
$$\mathbf{j}_i^R = -\rho D_{i, t} \nabla \overline{w}_i = -\frac{\mu_t}{Sc_t} \nabla \overline{w}_i$$
$$\mathbf{q}^R = -k_t \nabla \overline{T} = -\frac{c_p \mu_t}{Pr_t} \nabla \overline{T}$$
where:
* $Pr_t \equiv \frac{\mu_t c_p}{k_t} \approx 0.85 - 0.90$ is the **turbulent Prandtl number**.
* $Sc_t \equiv \frac{\mu_t}{\rho D_{i, t}} \approx 0.70 - 0.90$ is the **turbulent Schmidt number**.

#### 11.7.2 Effective Face Transport Coefficients on Polyhedral Meshes
On any interior face $f$ between adjacent cells $C_1$ and $C_2$, the effective diffusion coefficients for momentum, enthalpy, and chemical species are:
$$\mu_{f}^{\text{eff}} = \mu_f + \mu_{t, f}$$
$$\Gamma_{T, f}^{\text{eff}} = \left( \frac{k}{c_p} \right)_f + \left( \frac{\mu_t}{Pr_t} \right)_f$$
$$\Gamma_{i, f}^{\text{eff}} = (\rho D_{im})_f + \left( \frac{\mu_t}{Sc_t} \right)_f$$

These enter directly into the face flux operator $\Phi_f^{\text{diff}} = \Gamma_{\phi, f}^{\text{eff}} (\nabla \phi)_f \cdot \mathbf{A}_f$ of the Finite Volume Method (Section 8.5).



---

## 12. Volume-Averaging Theory (VAT) and Homogenization in Reactive Packed Beds and Porous Media

Separation columns (randomly packed rings, structured corrugated sheet packings like Sulzer Mellapak, catalytic distillation bales) and chemical reactors (fixed beds of porous catalyst extrudates, monoliths, trickle beds) contain intricate solid-fluid microstructures. Resolving the microscopic fluid flow through millions of individual pores and catalyst channels is computationally prohibitive.

The simulation engine bridges the microscale and macroscale through **Volume-Averaging Theory (VAT)** and asymptotic homogenization. By applying the Slattery-Whittaker averaging theorems over a Representative Elementary Volume (REV), the microscopic Navier-Stokes and Stefan-Maxwell equations are rigorously upscaled into continuum macroscopic Darcy-Forchheimer-Brinkman momentum equations, anisotropic dispersion tensors, and dual-porosity catalytic pellet models.

---

### 12.1 The Spatial Volume-Averaging Theorem (Slattery-Whittaker Formulation)

#### 12.1.1 The Representative Elementary Volume (REV)
Let $V$ denote a macroscopic averaging volume (REV) centered at coordinate $\mathbf{x} \in \mathbb{R}^3$, with characteristic length $r_0$.
The REV consists of fluid phase volume $V_\beta(\mathbf{x}, t)$ and solid matrix phase volume $V_\sigma(\mathbf{x}, t)$:
$$V = V_\beta + V_\sigma$$
The boundary of the REV consists of outer bounding surface $A_e$ and solid-fluid interfacial surface $A_{\beta\sigma}$:
$$\partial V = A_e \cup A_{\beta\sigma}$$
Let $\mathbf{n}_{\beta\sigma}$ denote the unit normal vector pointing from fluid phase $\beta$ into solid phase $\sigma$.

```
              +------------------------------------------+
              |           Representative Elementary      |
              |                 Volume (REV)             |
              |                                          |
              |      Fluid Phase \beta                   |
              |   ~~~~~~~~~~~~~~~~~~~~~~~~               |
              |             \                            |
              |              \  n_{\beta\sigma}          |
              |               v                          |
              |        [ Solid Catalyst ]                |
              |        [  Matrix \sigma ]                |
              |                                          |
              |   l_pore  <<  r_0  <<  L_macro           |
              +------------------------------------------+
```

##### Scale Separation Criterion:
Rigorous homogenization requires strict separation of scales:
$$l_{\text{pore}} \ll r_0 \ll L_{\text{macro}}$$
where $l_{\text{pore}}$ is microscopic pore size ($\sim 10^{-6} - 10^{-3} \, \text{m}$), $r_0$ is REV radius ($\sim 10^{-3} - 10^{-2} \, \text{m}$), and $L_{\text{macro}}$ is equipment diameter/height ($\sim 0.1 - 10 \, \text{m}$).

#### 12.1.2 Phase Averaging Operators
* **Superficial Phase Average:**
  $$\langle \psi_\beta \rangle(\mathbf{x}, t) \equiv \frac{1}{V} \int_{V_\beta(\mathbf{x}, t)} \psi_\beta(\mathbf{y}, t) \, dV_y$$
* **Intrinsic Phase Average:**
  $$\langle \psi_\beta \rangle^\beta(\mathbf{x}, t) \equiv \frac{1}{V_\beta(\mathbf{x}, t)} \int_{V_\beta(\mathbf{x}, t)} \psi_\beta(\mathbf{y}, t) \, dV_y$$
* **Porosity (Void Fraction):**
  $$\epsilon(\mathbf{x}, t) \equiv \frac{V_\beta(\mathbf{x}, t)}{V}$$
  Connecting the two averages:
  $$\langle \psi_\beta \rangle = \epsilon \, \langle \psi_\beta \rangle^\beta$$

#### 12.1.3 Spatial Deviation Decomposition (Gray's Decomposition)
Any microscopic variable $\psi_\beta$ decomposes into its intrinsic average and a microscale spatial fluctuation:
$$\psi_\beta = \langle \psi_\beta \rangle^\beta + \tilde{\psi}_\beta$$
with the mathematical property:
$$\langle \tilde{\psi}_\beta \rangle^\beta \equiv \frac{1}{V_\beta} \int_{V_\beta} \tilde{\psi}_\beta \, dV = 0$$

#### 12.1.4 The Slattery-Whittaker Averaging Theorems
Deriving macroscopic conservation laws requires interchanging spatial integration with differentiation.
1. **Averaging of Spatial Gradient:**
   $$\langle \nabla \psi_\beta \rangle = \nabla \langle \psi_\beta \rangle + \frac{1}{V} \int_{A_{\beta\sigma}} \psi_\beta \, \mathbf{n}_{\beta\sigma} \, dA$$
2. **Averaging of Spatial Divergence:**
   $$\langle \nabla \cdot \boldsymbol{\psi}_\beta \rangle = \nabla \cdot \langle \boldsymbol{\psi}_\beta \rangle + \frac{1}{V} \int_{A_{\beta\sigma}} \boldsymbol{\psi}_\beta \cdot \mathbf{n}_{\beta\sigma} \, dA$$
3. **Averaging of Time Derivative (Moving Boundary Theorem):**
   $$\left\langle \frac{\partial \psi_\beta}{\partial t} \right\rangle = \frac{\partial \langle \psi_\beta \rangle}{\partial t} - \frac{1}{V} \int_{A_{\beta\sigma}} \psi_\beta (\mathbf{w} \cdot \mathbf{n}_{\beta\sigma}) \, dA$$
   where $\mathbf{w}$ is the velocity of the solid-fluid interface $A_{\beta\sigma}$ (which vanishes for rigid stationary packings).

---

### 12.2 Derivation of Macroscopic Continuity, Momentum, and Energy in Porous Architectures

#### 12.2.1 Upscaled Continuity Equation
Microscopic continuity for incompressible fluid ($\nabla \cdot \mathbf{u} = 0$, $\mathbf{u} = \mathbf{0}$ on solid walls $A_{\beta\sigma}$):
$$\langle \nabla \cdot \mathbf{u} \rangle = \nabla \cdot \langle \mathbf{u} \rangle + \frac{1}{V} \int_{A_{\beta\sigma}} \mathbf{u} \cdot \mathbf{n}_{\beta\sigma} \, dA = 0$$
Since $\left. \mathbf{u} \right|_{A_{\beta\sigma}} = \mathbf{0}$:
$$\nabla \cdot \langle \mathbf{u} \rangle = 0 \iff \nabla \cdot (\epsilon \langle \mathbf{u} \rangle^\beta) = 0$$
where $\mathbf{U} \equiv \langle \mathbf{u} \rangle$ is the **superficial Darcy velocity** ($\text{m}/\text{s}$) and $\langle \mathbf{u} \rangle^\beta = \mathbf{U} / \epsilon$ is the **interstitial fluid velocity**.

For variable density flows:
$$\frac{\partial (\epsilon \langle \rho \rangle^\beta)}{\partial t} + \nabla \cdot (\langle \rho \rangle^\beta \mathbf{U}) = 0$$

#### 12.2.2 Upscaled Navier-Stokes Momentum Balance
Microscopic momentum:
$$\rho \frac{\partial \mathbf{u}}{\partial t} + \rho \nabla \cdot (\mathbf{u} \otimes \mathbf{u}) = -\nabla P + \mu \nabla^2 \mathbf{u} + \rho \mathbf{g}$$
Applying the averaging theorems and Gray's decomposition ($\mathbf{u} = \langle \mathbf{u} \rangle^\beta + \tilde{\mathbf{u}}$, $P = \langle P \rangle^\beta + \tilde{P}$):
$$\frac{\rho}{\epsilon} \left[ \frac{\partial \mathbf{U}}{\partial t} + \frac{1}{\epsilon} (\mathbf{U} \cdot \nabla) \mathbf{U} \right] = -\nabla \langle P \rangle^\beta + \frac{\mu}{\epsilon} \nabla^2 \mathbf{U} + \rho \mathbf{g} + \mathbf{f}_{\beta\sigma} - \nabla \cdot (\rho \langle \tilde{\mathbf{u}} \otimes \tilde{\mathbf{u}} \rangle)$$
where $\mathbf{f}_{\beta\sigma}$ represents the total fluid-solid interfacial drag force density ($\text{N}/\text{m}^3$):
$$\mathbf{f}_{\beta\sigma} \equiv \frac{1}{V} \int_{A_{\beta\sigma}} \left( -\tilde{P} \mathbf{I} + \mu \nabla \tilde{\mathbf{u}} \right) \cdot \mathbf{n}_{\beta\sigma} \, dA$$

---

### 12.3 Generalized Brinkman-Forchheimer-Darcy Momentum Equation and Non-Linear Drag Tensors

The interfacial drag $\mathbf{f}_{\beta\sigma}$ consists of viscous Stokes drag and inertial form drag (boundary layer separation behind packing filaments). Through closure modeling on representative microscale unit cells, $\mathbf{f}_{\beta\sigma}$ is represented as:
$$\mathbf{f}_{\beta\sigma} = -\mu \mathbf{K}^{-1} \cdot \mathbf{U} - \rho \mathbf{F}_{\text{in}} \cdot |\mathbf{U}| \mathbf{U}$$
where:
* $\mathbf{K}$ is the symmetric second-order **permeability tensor** ($\text{m}^2$).
* $\mathbf{F}_{\text{in}}$ is the second-order **Forchheimer inertial drag tensor** ($\text{m}^{-1}$).

#### 12.3.1 The Complete Macroscopic Brinkman-Forchheimer-Darcy Equation
$$\frac{\rho}{\epsilon} \left[ \frac{\partial \mathbf{U}}{\partial t} + \frac{1}{\epsilon} (\mathbf{U} \cdot \nabla) \mathbf{U} \right] = -\nabla \langle P \rangle^\beta + \frac{\mu}{\epsilon} \nabla^2 \mathbf{U} - \mu \mathbf{K}^{-1} \cdot \mathbf{U} - \rho \mathbf{F}_{\text{in}} \cdot |\mathbf{U}| \mathbf{U} + \rho \mathbf{g}$$

```
====================================================================================================
Flow Regime               Governing Balance                                       Dominant Terms
====================================================================================================
Creeping Flow (Re_p < 1)  0 = -\nabla \langle P \rangle^\beta - \mu K^{-1} U      Darcy's Law
High Re (Re_p > 10)       0 = -\nabla \langle P \rangle^\beta - \mu K^{-1} U      Darcy-Forchheimer
                              - \rho F_{in} |U| U
Near-Wall Boundary Layer  0 = -\nabla \langle P \rangle^\beta + (\mu/\epsilon) \nabla^2 U Brinkman Extension
                              - \mu K^{-1} U
====================================================================================================
```

#### 12.3.2 Isotropic Packed Beds: The Ergun Equation
For random packed beds of uniform spherical pellets with diameter $d_p$ and void fraction $\epsilon$, the Ergun equation provides:
$$\mathbf{K} = \frac{\epsilon^3 d_p^2}{150 (1 - \epsilon)^2} \mathbf{I}, \quad \mathbf{F}_{\text{in}} = \frac{1.75 (1 - \epsilon)}{\epsilon^3 d_p} \mathbf{I}$$
giving the pressure drop:
$$-\frac{d \langle P \rangle^\beta}{d z} = 150 \frac{\mu (1 - \epsilon)^2}{\epsilon^3 d_p^2} U + 1.75 \frac{\rho (1 - \epsilon)}{\epsilon^3 d_p} U^2$$

#### 12.3.3 Anisotropic Structured Packings (Sulzer Mellapak)
Structured corrugated packings feature distinct hydraulic resistance along axial ($z$) versus radial ($x, y$) directions:
$$\mathbf{K} = \begin{bmatrix} K_r & 0 & 0 \\ 0 & K_r & 0 \\ 0 & 0 & K_z \end{bmatrix}, \quad K_z \gg K_r$$
Liquid flows preferentially along crimped corrugation angles $\theta \approx 45^\circ$, inducing anisotropic cross-channel mixing matrices.

---

### 12.4 Multicomponent Hydrodynamic Dispersion Tensors and Anisotropic Tortuosity

Upscaling species transport $\frac{\partial c_i}{\partial t} + \nabla \cdot (\mathbf{u} c_i) = \nabla \cdot (D_i \nabla c_i) + R_i$:
$$\frac{\partial (\epsilon \langle c_i \rangle^\beta)}{\partial t} + \nabla \cdot (\mathbf{U} \langle c_i \rangle^\beta) = \nabla \cdot \left( \mathbf{D}_i^{\text{eff}} \cdot \nabla \langle c_i \rangle^\beta \right) + \epsilon \langle R_i \rangle^\beta + a_v j_{i, \beta\sigma}$$
where $a_v \equiv A_{\beta\sigma} / V$ is the **specific interfacial area** ($\text{m}^2/\text{m}^3$) and $\mathbf{D}_i^{\text{eff}}$ is the **effective dispersion tensor**:
$$\mathbf{D}_i^{\text{eff}} \equiv \mathbf{D}_{i, \text{diff}}^* + \mathbf{D}_{i, \text{disp}}$$

#### 12.4.1 Tortuous Molecular Diffusion Tensor
Porous solid skeletons obstruct straight molecular diffusion paths:
$$\mathbf{D}_{i, \text{diff}}^* = \frac{\epsilon}{\tau} D_{im} \mathbf{I}$$
where $\tau \ge 1$ is the dimensionless **tortuosity factor** ($\tau \approx 2-5$ in catalyst pellets, $\tau \approx \epsilon^{-1/2}$ by Archie's law).

#### 12.4.2 Mechanical Hydrodynamic Dispersion Tensor
Velocity shear within tortuous pore throats spreads solute along and across streamlines:
$$\mathbf{D}_{i, \text{disp}} = \alpha_T |\mathbf{U}| \mathbf{I} + (\alpha_L - \alpha_T) \frac{\mathbf{U} \otimes \mathbf{U}}{|\mathbf{U}|}$$
where $\alpha_L$ is longitudinal dispersivity ($\text{m}$) and $\alpha_T$ is transverse dispersivity ($\text{m}$), typically $\alpha_L \approx 5-10 \, \alpha_T$.

---

### 12.5 Dual-Porosity and Dual-Permeability Formulations for Reactive Catalytic Pellets

In catalytic distillation and trickle beds, transport occurs at two distinct scales:
1. **Macropores (Mobile Fluid Stream $\beta$):** Convective bulk transport through bed voids ($\epsilon_m \sim 0.40$).
2. **Micropores (Stagnant Intra-Pellet Fluid $\sigma$):** Pure diffusive transport and reaction inside porous catalyst pellets ($\epsilon_p \sim 0.50$).

```
                      +---------------------------------------+
                      |         Dual-Porosity System          |
                      +---------------------------------------+
                                          |
                +-------------------------+-------------------------+
                |                                                   |
                v                                                   v
      [ Mobile Bulk Stream ]                              [ Intra-Pellet Pores ]
     Convection + Dispersion                              Pure Knudsen Diffusion
      \epsilon_m \partial c_m / \partial t                \epsilon_p \partial c_p / \partial t
                |                                                   |
                +<======== Mass Transfer Interphase ========>+
                             k_m a_v (c_m - c_p|_{r=R_p})
```

#### Mathematical Formulation
* **Bulk Mobile Stream PDE:**
  $$\epsilon_m \frac{\partial c_{i, m}}{\partial t} + \nabla \cdot (\mathbf{U} c_{i, m}) = \nabla \cdot \left( \mathbf{D}_{i, m}^{\text{eff}} \cdot \nabla c_{i, m} \right) - a_p k_{m, i} (c_{i, m} - \left. c_{i, p} \right|_{r=R_p})$$
* **Intra-Pellet Radial Diffusion-Reaction PDE:**
  $$\epsilon_p \frac{\partial c_{i, p}}{\partial t} = \frac{1}{r^2} \frac{\partial}{\partial r}\left( r^2 D_{i, \text{pore}}^{\text{eff}} \frac{\partial c_{i, p}}{\partial r} \right) + R_i(c_p, T_p), \quad r \in [0, R_p]$$
  with boundary conditions:
  $$\left. \frac{\partial c_{i, p}}{\partial r} \right|_{r=0} = 0 \quad (\text{pellet center symmetry})$$
  $$-D_{i, \text{pore}}^{\text{eff}} \left. \frac{\partial c_{i, p}}{\partial r} \right|_{r=R_p} = k_{m, i} (c_{i, p}(R_p) - c_{i, m}) \quad (\text{external boundary layer flux})$$

This couples 3D macroscopic column CFD to a 1D radial ODE/PDE at every spatial finite volume cell, solved via orthogonal Radau collocation.

---

### 12.6 Boundary Layer Jump Conditions at Porous-Fluid Interfaces

At the interface between a clear fluid channel and a porous packed bed (e.g. wall film flowing over structured packing), fluid velocity does not drop to zero discontinuously.

#### The Beavers-Joseph-Saffman Boundary Condition
Beavers and Joseph (1967) proved empirically, and Saffman (1971) derived via homogenization, that viscous shear stress in the clear fluid is proportional to slip velocity at the porous boundary:
$$\left. \frac{\partial u_x}{\partial y} \right|_{y=0^+} = \frac{\alpha_{\text{BJ}}}{\sqrt{K}} \left( u_{\text{slip}} - u_{\text{Darcy}} \right)$$
where:
* $y=0^+$ is the clear fluid side of the porous interface.
* $u_{\text{slip}} \equiv u_x(y=0^+)$ is the interfacial slip velocity.
* $u_{\text{Darcy}} = -\frac{K}{\mu} \frac{dP}{dx}$ is the macroscopic Darcy filtration velocity inside the porous substrate.
* $\alpha_{\text{BJ}}$ is the dimensionless **Beavers-Joseph coefficient** ($\alpha_{\text{BJ}} \approx 0.1 - 4.0$, depending on surface pore geometry).



---

## 13. Forward Sensitivity Analysis, Adjoint DAE Systems, and Dynamic Optimization

Process simulation models parameterized by physical properties (UNIFAC binary interaction parameters $a_{ij}$, kinetic rate constants $k_0, E_a$, heat transfer coefficients $U_A$) or manipulated inputs (reflux ratio $R$, reboiler duty $Q_R$, feed stage allocations) frequently require:
1. **Parametric Sensitivity Analysis:** Quantifying how outputs change with respect to design or thermodynamic parameters ($\frac{\partial \mathbf{y}}{\partial \mathbf{p}}$).
2. **Model Calibration and Parameter Estimation:** Solving nonlinear least-squares regression problems constrained by implicit DAEs.
3. **Dynamic Optimization and NMPC:** Computing optimal start-up trajectories, grade transitions, or energy-minimizing controls under complex state and hydraulic constraints.

Evaluating gradients via standard finite differences $\frac{\partial \mathcal{J}}{\partial p_k} \approx \frac{\mathcal{J}(\mathbf{p} + \epsilon \mathbf{e}_k) - \mathcal{J}(\mathbf{p})}{\epsilon}$ requires $N_p + 1$ full forward dynamic simulations and suffers from subtractive cancellation errors. This chapter establishes the rigorous theory of **Forward Sensitivity Analysis** (for small parameter sets $N_p \ll N_y$) and **Adjoint DAE Systems** (whose gradient evaluation cost is strictly independent of $N_p$), integrated directly into the equation-oriented engine.

---

### 13.1 Parameterized Nonlinear DAE Systems and Parametric Jacobian Operators

Consider the general fully implicit, index-1 Differential-Algebraic Equation (DAE) system parameterized by vector $\mathbf{p} \in \mathbb{R}^{N_p}$:
$$\mathbf{F}(t, \mathbf{y}(t), \dot{\mathbf{y}}(t), \mathbf{p}) = \mathbf{0}, \quad t \in [t_0, t_f]$$
with consistent initial conditions:
$$\mathbf{y}(t_0) = \mathbf{y}_0(\mathbf{p})$$
where $\mathbf{y}(t) \in \mathbb{R}^{N_y}$ is the state vector (encompassing differential states $\mathbf{x}$ and algebraic states $\mathbf{z}$), $\dot{\mathbf{y}}(t) \equiv \frac{d\mathbf{y}}{dt}$, and $\mathbf{F}: \mathbb{R} \times \mathbb{R}^{N_y} \times \mathbb{R}^{N_y} \times \mathbb{R}^{N_p} \to \mathbb{R}^{N_y}$ is sufficiently smooth ($C^2$).

#### System Jacobian Matrices
* **Differential Jacobian:**
  $$\mathbf{J}_{\dot{\mathbf{y}}}(t) \equiv \frac{\partial \mathbf{F}}{\partial \dot{\mathbf{y}}} \in \mathbb{R}^{N_y \times N_y}$$
* **State Jacobian:**
  $$\mathbf{J}_{\mathbf{y}}(t) \equiv \frac{\partial \mathbf{F}}{\partial \mathbf{y}} \in \mathbb{R}^{N_y \times N_y}$$
* **Parametric Jacobian:**
  $$\mathbf{J}_{\mathbf{p}}(t) \equiv \frac{\partial \mathbf{F}}{\partial \mathbf{p}} \in \mathbb{R}^{N_y \times N_p}$$

---

### 13.2 Forward Sensitivity Equations and Staggered vs. Simultaneous Newton Solution

#### 13.2.1 Derivation of Sensitivity DAE
Differentiating the implicit DAE $\mathbf{F} = \mathbf{0}$ with respect to parameter $p_k$ ($k \in \{1, \dots, N_p\}$):
$$\frac{d}{d p_k} \left[ \mathbf{F}(t, \mathbf{y}(t, \mathbf{p}), \dot{\mathbf{y}}(t, \mathbf{p}), \mathbf{p}) \right] = \mathbf{0}$$
Applying the chain rule:
$$\frac{\partial \mathbf{F}}{\partial \dot{\mathbf{y}}} \frac{\partial \dot{\mathbf{y}}}{\partial p_k} + \frac{\partial \mathbf{F}}{\partial \mathbf{y}} \frac{\partial \mathbf{y}}{\partial p_k} + \frac{\partial \mathbf{F}}{\partial p_k} = \mathbf{0}$$

Defining the **forward sensitivity matrix** $\mathbf{S}(t) \in \mathbb{R}^{N_y \times N_p}$ with columns $\mathbf{s}_k(t) \equiv \frac{\partial \mathbf{y}(t)}{\partial p_k}$:
$$\mathbf{J}_{\dot{\mathbf{y}}}(t) \, \dot{\mathbf{s}}_k(t) + \mathbf{J}_{\mathbf{y}}(t) \, \mathbf{s}_k(t) + \frac{\partial \mathbf{F}}{\partial p_k} = \mathbf{0}, \quad k = 1, \dots, N_p$$
with initial conditions:
$$\mathbf{s}_k(t_0) = \frac{\partial \mathbf{y}_0(\mathbf{p})}{\partial p_k}$$

Notice that the sensitivity equations are **strictly linear** in $\mathbf{s}_k$ and $\dot{\mathbf{s}}_k$, sharing the identical state Jacobians $\mathbf{J}_{\dot{\mathbf{y}}}$ and $\mathbf{J}_{\mathbf{y}}$ with the primary non-linear DAE.

#### 13.2.2 Numerical Integration: Staggered Direct vs. Simultaneous Solution
When integrating the combined system with a stiff BDF or Radau IIA step (step size $h$, discretization parameter $\alpha = 1 / (h \beta_0)$):
$$\mathbf{W} \equiv \alpha \mathbf{J}_{\dot{\mathbf{y}}} + \mathbf{J}_{\mathbf{y}}$$
1. **Simultaneous Approach:** Solves an augmented system of size $N_y (1 + N_p)$ at every Newton iteration.
2. **Staggered Direct Approach:**
   - Step 1: Solve the nonlinear base step $\mathbf{F} = \mathbf{0}$ to convergence using Newton's method with iteration matrix $\mathbf{W}$. Compute and store the LU factorization $\mathbf{W} = \mathbf{L} \mathbf{U}$.
   - Step 2: For each parameter $k = 1, \dots, N_p$, the sensitivity step requires only **one forward-backward substitution**:
     $$\mathbf{L} \mathbf{U} \, \Delta \mathbf{s}_k = -\mathbf{R}_{\text{sens}, k}$$
   Since LU factorization dominates computational effort ($\mathcal{O}(N_y^3)$ dense or $\mathcal{O}(N_y^{1.5})$ sparse) while back-substitution is negligible ($\mathcal{O}(N_y)$), solving 50 sensitivities adds only $\sim 15\%$ overhead compared to the base simulation.

---

### 13.3 Variational Derivation of Continuous Adjoint DAE Systems

When the goal is to evaluate the gradient of a single scalar performance functional $\mathcal{J}(\mathbf{p})$ with respect to a large number of parameters ($N_p \gg 1$, e.g. distributed boundary flux profiles, 100+ catalyst kinetic constants), the **Adjoint Method** is mathematically optimal.

#### 13.3.1 General Bolza Objective Functional
Let the performance objective be:
$$\mathcal{J}(\mathbf{p}) \equiv \Phi(t_f, \mathbf{y}(t_f), \mathbf{p}) + \int_{t_0}^{t_f} \mathcal{L}(t, \mathbf{y}(t), \mathbf{p}) \, dt$$
where $\Phi$ is the terminal Mayer cost and $\mathcal{L}$ is the running Lagrange running cost.

#### 13.3.2 The Augmented Lagrangian
Introduce the time-dependent vector Lagrange multiplier (adjoint state) $\boldsymbol{\lambda}(t) \in \mathbb{R}^{N_y}$:
$$\mathcal{J}_{\text{aug}}(\mathbf{p}) \equiv \Phi(t_f, \mathbf{y}(t_f), \mathbf{p}) + \int_{t_0}^{t_f} \left[ \mathcal{L}(t, \mathbf{y}(t), \mathbf{p}) - \boldsymbol{\lambda}(t)^T \mathbf{F}(t, \mathbf{y}(t), \dot{\mathbf{y}}(t), \mathbf{p}) \right] dt$$
Since $\mathbf{F} \equiv \mathbf{0}$ along any physical trajectory, $\mathcal{J}_{\text{aug}}(\mathbf{p}) \equiv \mathcal{J}(\mathbf{p})$ for any arbitrary multiplier $\boldsymbol{\lambda}(t)$.

#### 13.3.3 Total Variation and Integration by Parts
Taking the first variation of $\mathcal{J}_{\text{aug}}$ with respect to parameter perturbation $\delta \mathbf{p}$:
$$\delta \mathcal{J} = \frac{\partial \Phi}{\partial \mathbf{p}} \delta \mathbf{p} + \frac{\partial \Phi}{\partial \mathbf{y}_f} \delta \mathbf{y}_f + \int_{t_0}^{t_f} \left[ \frac{\partial \mathcal{L}}{\partial \mathbf{p}} \delta \mathbf{p} + \frac{\partial \mathcal{L}}{\partial \mathbf{y}} \delta \mathbf{y} - \boldsymbol{\lambda}^T \left( \frac{\partial \mathbf{F}}{\partial \mathbf{p}} \delta \mathbf{p} + \frac{\partial \mathbf{F}}{\partial \mathbf{y}} \delta \mathbf{y} + \frac{\partial \mathbf{F}}{\partial \dot{\mathbf{y}}} \delta \dot{\mathbf{y}} \right) \right] dt$$

Integrating the term containing $\delta \dot{\mathbf{y}} = \frac{d}{dt}(\delta \mathbf{y})$ by parts:
$$-\int_{t_0}^{t_f} \boldsymbol{\lambda}^T \frac{\partial \mathbf{F}}{\partial \dot{\mathbf{y}}} \delta \dot{\mathbf{y}} \, dt = -\left[ \boldsymbol{\lambda}(t)^T \frac{\partial \mathbf{F}}{\partial \dot{\mathbf{y}}} \delta \mathbf{y}(t) \right]_{t_0}^{t_f} + \int_{t_0}^{t_f} \frac{d}{dt}\left( \boldsymbol{\lambda}(t)^T \frac{\partial \mathbf{F}}{\partial \dot{\mathbf{y}}} \right) \delta \mathbf{y} \, dt$$

Substituting back and collecting terms grouping $\delta \mathbf{y}(t)$:
$$\delta \mathcal{J} = \left[ \frac{\partial \Phi}{\partial \mathbf{p}} \delta \mathbf{p} + \int_{t_0}^{t_f} \left( \frac{\partial \mathcal{L}}{\partial \mathbf{p}} - \boldsymbol{\lambda}^T \frac{\partial \mathbf{F}}{\partial \mathbf{p}} \right) dt + \left. \boldsymbol{\lambda}^T \frac{\partial \mathbf{F}}{\partial \dot{\mathbf{y}}} \right|_{t_0} \delta \mathbf{y}_0 \right]$$
$$+ \left[ \left. \frac{\partial \Phi}{\partial \mathbf{y}} \right|_{t_f} - \left. \boldsymbol{\lambda}(t_f)^T \frac{\partial \mathbf{F}}{\partial \dot{\mathbf{y}}} \right|_{t_f} \right] \delta \mathbf{y}_f + \int_{t_0}^{t_f} \left[ \frac{\partial \mathcal{L}}{\partial \mathbf{y}} - \boldsymbol{\lambda}^T \frac{\partial \mathbf{F}}{\partial \mathbf{y}} + \frac{d}{dt}\left( \boldsymbol{\lambda}^T \frac{\partial \mathbf{F}}{\partial \dot{\mathbf{y}}} \right) \right] \delta \mathbf{y}(t) \, dt$$

#### 13.3.4 The Continuous Adjoint DAE Problem
To eliminate all explicit dependencies on the unknown state variations $\delta \mathbf{y}(t)$ and $\delta \mathbf{y}_f$, we require the bracketed terms to vanish identically:
1. **Adjoint DAE Differential Equation (Integrated Backward in Time from $t_f$ to $t_0$):**
   $$\frac{d}{dt}\left( \boldsymbol{\lambda}(t)^T \frac{\partial \mathbf{F}}{\partial \dot{\mathbf{y}}} \right) - \boldsymbol{\lambda}(t)^T \frac{\partial \mathbf{F}}{\partial \mathbf{y}} = -\frac{\partial \mathcal{L}}{\partial \mathbf{y}}$$
   Or in transposed column form:
   $$\frac{d}{dt}\left( \mathbf{J}_{\dot{\mathbf{y}}}^T \boldsymbol{\lambda} \right) - \mathbf{J}_{\mathbf{y}}^T \boldsymbol{\lambda} = -\left( \frac{\partial \mathcal{L}}{\partial \mathbf{y}} \right)^T$$
2. **Terminal Boundary Condition at $t = t_f$:**
   $$\left. \mathbf{J}_{\dot{\mathbf{y}}}^T \boldsymbol{\lambda} \right|_{t_f} = \left( \left. \frac{\partial \Phi}{\partial \mathbf{y}} \right|_{t_f} \right)^T$$

#### 13.3.5 The Gradient Master Formula
Once the adjoint trajectory $\boldsymbol{\lambda}(t)$ is obtained by integrating backward in time, the exact gradient of $\mathcal{J}$ with respect to all $N_p$ parameters is evaluated by simple quadrature:
$$\nabla_{\mathbf{p}} \mathcal{J} = \frac{\partial \Phi}{\partial \mathbf{p}} + \left. \boldsymbol{\lambda}(t_0)^T \frac{\partial \mathbf{F}}{\partial \dot{\mathbf{y}}} \right|_{t_0} \frac{\partial \mathbf{y}_0}{\partial \mathbf{p}} + \int_{t_0}^{t_f} \left( \frac{\partial \mathcal{L}}{\partial \mathbf{p}} - \boldsymbol{\lambda}(t)^T \frac{\partial \mathbf{F}}{\partial \mathbf{p}} \right) dt$$

```
=================================================================================================
Method               Forward DAE Simulations   Backward DAE Solves   Computational Cost
=================================================================================================
Finite Differences   N_p + 1                   0                     O(N_p * Cost_sim) + Canc. Error
Forward Sensitivity  1 (Augmented N_y(1+N_p))  0                     O(N_p * Cost_backsub)
Continuous Adjoint   1                         1 (Backward Adjoint)  O(2 * Cost_sim), Independent of N_p!
=================================================================================================
```

---

### 13.4 Discrete Adjoint Formulations for Radau IIA Collocation

In continuous adjoint formulations, discretizing the continuous adjoint PDE can introduce numerical errors such that the computed gradient does not match the exact gradient of the discretized forward solver (loss of dual consistency).
The simulation engine therefore supports **Discrete Adjoint DAE formulations** where the discrete Runge-Kutta / Radau IIA algebraic stage equations are differentiated directly.

For an $s$-stage implicit Runge-Kutta step:
$$\mathbf{Y}_{n, i} = \mathbf{y}_n + h_n \sum_{j=1}^s a_{ij} \mathbf{K}_{n, j}$$
$$\mathbf{F}\left( t_n + c_i h_n, \mathbf{Y}_{n, i}, \mathbf{K}_{n, i}, \mathbf{p} \right) = \mathbf{0}, \quad i = 1, \dots, s$$
$$\mathbf{y}_{n+1} = \mathbf{y}_n + h_n \sum_{i=1}^s b_i \mathbf{K}_{n, i}$$

The discrete Lagrangian is formed by multiplying each stage residual by discrete stage adjoint multipliers $\boldsymbol{\Lambda}_{n, i}$:
$$\mathcal{L}_{\text{discrete}} = \Phi(\mathbf{y}_N, \mathbf{p}) + \sum_{n=0}^{N-1} \left[ h_n \sum_{i=1}^s b_i \mathcal{L}(t_{n, i}, \mathbf{Y}_{n, i}, \mathbf{p}) - \sum_{i=1}^s \boldsymbol{\Lambda}_{n, i}^T \mathbf{F}(t_{n, i}, \mathbf{Y}_{n, i}, \mathbf{K}_{n, i}, \mathbf{p}) \right]$$
Setting $\frac{\partial \mathcal{L}_{\text{discrete}}}{\partial \mathbf{Y}_{n, i}} = \mathbf{0}$ and $\frac{\partial \mathcal{L}_{\text{discrete}}}{\partial \mathbf{K}_{n, i}} = \mathbf{0}$ yields the discrete adjoint equations:
$$\boldsymbol{\Lambda}_{n, i}^T \frac{\partial \mathbf{F}_{n, i}}{\partial \mathbf{K}_{n, i}} + h_n \sum_{j=1}^s a_{ji} \boldsymbol{\Lambda}_{n, j}^T \frac{\partial \mathbf{F}_{n, j}}{\partial \mathbf{Y}_{n, j}} = h_n b_i \left( \boldsymbol{\lambda}_{n+1}^T + \frac{\partial \mathcal{L}_{n, i}}{\partial \mathbf{Y}_{n, i}} \right)$$

This discrete adjoint gradient matches the algorithmic differentiation of the simulation code to **16 digits of machine precision** ($|\nabla \mathcal{J}_{\text{adj}} - \nabla \mathcal{J}_{\text{exact}}| < 10^{-14}$).

---

### 13.5 Exact Gradient and Hessian Vector-Product Evaluations for Optimization

For large-scale optimization via Newton-Krylov methods (e.g. Truncated Conjugate Gradient), computing the full $N_p \times N_p$ Hessian matrix is prohibitive. However, the action of the Hessian on an arbitrary direction vector $\mathbf{v} \in \mathbb{R}^{N_p}$ (the **Hessian-vector product** $\mathbf{H} \mathbf{v} \equiv \nabla^2 \mathcal{J}(\mathbf{p}) \cdot \mathbf{v}$) can be computed exactly using **second-order forward-over-adjoint sensitivity**:
1. Forward pass: Solve base DAE $\mathbf{F} = \mathbf{0}$.
2. Forward tangent pass: Solve forward sensitivity equation in direction $\mathbf{v}$ ($\dot{\mathbf{s}} = \dots$).
3. Backward adjoint pass: Solve adjoint DAE for $\boldsymbol{\lambda}(t)$.
4. Backward second-order adjoint pass: Solve linearized adjoint DAE for second-order multiplier $\boldsymbol{\mu}(t)$.
5. Evaluate $\mathbf{H} \mathbf{v}$ via line quadrature.

The total cost is only $\approx 4$ simulation equivalents, independent of $N_p$.

---

### 13.6 Dynamic Optimization and Nonlinear Model Predictive Control (NMPC) of Reactive Distillation Start-Up

#### 13.6.1 The Start-Up Optimization Challenge
Starting up a reactive distillation column (e.g. ethyl acetate synthesis from ethanol and acetic acid over an amberlyst resin catalyst) is an intensely nonlinear transient process:
* Initially, trays are cold and filled with inert or ambient mixture.
* Over-boiling causes hydraulic flooding, tray weeping, and unreacted acid carryover into the distillate condenser.
* Under-boiling fails to establish the required internal vapor-liquid traffic and causes azeotropic dead-ends.

#### 13.6.2 Optimal Control Mathematical Formulation
$$\min_{\mathbf{u}(t), t_f} \mathcal{J} = \alpha_1 t_f + \alpha_2 \int_{t_0}^{t_f} \left[ Q_{\text{reb}}(t) + Q_{\text{cond}}(t) \right] dt + \alpha_3 \int_{t_0}^{t_f} [x_{\text{EtAc}, D}(t) - x_{\text{spec}}]^2 dt$$
subject to:
* Dynamic MESH-D DAE System: $\mathbf{F}(t, \mathbf{y}, \dot{\mathbf{y}}, \mathbf{u}) = \mathbf{0}$
* Initial state: $\mathbf{y}(t_0) = \mathbf{y}_{\text{cold}}$
* Hydraulic capacity constraints (no flooding/weeping on any tray $j \in \{1, \dots, N_t\}$):
  $$F_{\text{weep}, j} \le \frac{L_j}{\rho_L A_{\text{active}}} \le F_{\text{flood}, j}$$
* Heat duty limits: $0 \le Q_{\text{reb}}(t) \le Q_{\text{reb}}^{\text{max}}$, $0 \le R(t) \le R^{\text{max}}$
* Maximum thermal gradient: $\left| \frac{d T_j}{dt} \right| \le \Delta T_{\text{stress}}^{\text{max}}$ (thermal shock constraint)
* Final distillate purity constraint: $x_{\text{EtAc}, D}(t_f) \ge 0.995$.

#### 13.6.3 Solution via Full Simultaneous Orthogonal Collocation (IPOPT)
The continuous time horizon $[t_0, t_f]$ is discretized into $N_e$ finite elements. Inside each element $k \in \{1, \dots, N_e\}$, states are approximated by Lagrange interpolation polynomials across $s=3$ Legendre or Radau collocation points:
$$\mathbf{y}_k(t) = \sum_{j=0}^s \ell_j\left( \frac{t - t_{k-1}}{h_k} \right) \mathbf{Y}_{k, j}$$

This converts the infinite-dimensional dynamic optimal control problem into a finite-dimensional Nonlinear Program (NLP) with $\approx 10^5 - 10^6$ variables, solved via the Interior Point Optimizer (IPOPT) using sparse multifrontal linear solvers (MUMPS / HSL MA57). The resulting optimal policy cuts start-up time by up to $42\%$ and reduces off-spec energy consumption by $35\%$ compared to standard industrial heuristics.



---

---

## 14. Mathematical Treatment and Software Architecture Implementation Methodology

The defining architectural thesis of the simulation engine—distinguishing it from legacy process simulators (e.g., Aspen Plus, Aspen HYSYS, gPROMS, or CHEMCAD)—is the strict rejection of hardcoded "unit operation" templates, monolithic equipment classes, and scenario-specific solver scripts. In this engine, there are no built-in classes named `DistillationColumn`, `CSTR`, `HeatExchanger`, or `FlashDrum`. 

Instead, the simulator operates as an **"Engine of Engines"** structured around four unified mathematical workspaces (**Model $\to$ Transform $\to$ Solve $\to$ Results**) governed by the immutable versioned **Common Model** (`rage.modelo`). Every physical process, whether a single-phase stirred vessel, a 3D reacting porous catalyst pellet, a 50-tray reactive distillation column, or an acoustic hydraulic piping network, is constructed dynamically from first-principles continuous conservation laws, reduced through recorded traceable deduction operations, transformed through algebraic or discretization operators, compiled into structural DAE execution graphs, and solved using stiff numerical integrators equipped with always-present thermodynamic equilibrium closures.

This chapter details the exact **mathematical treatment** and **software architecture implementation methodology** required to build, maintain, and extend this simulation engine across Python backends, TypeScript interfaces, and high-performance numerical kernels.

```
+=========================================================================================================================+
|                                              THE FOUR-WORKSPACE ARCHITECTURE                                            |
+=========================================================================================================================+
|                                                                                                                         |
|    [ 1. MODEL WORKSPACE ]                                                                                               |
|    Continuous Conservation Laws  ===>  Deduction Algebra O_ded  ===>  Volumetric Network Topology                       |
|    (Microscopic PDEs)                  (Reynolds, Gauss, Uniformity)  (Volumes, Streams, Boundaries)                     |
|                                                     |                                                                   |
|                                                     v  Common Model AST (rage.modelo)                                   |
|    [ 2. TRANSFORM WORKSPACE ]                                                                                           |
|    Mathematical Operator Maps    ===>  Nondimensionalization    ===>  Spatial Mesh Discretization                       |
|    (Invertible Lie Scaling)            (Buckingham \Pi over Q)        (Cartesian, Hex, Simplicial, Polyhedra FVM)       |
|                                                     |                                                                   |
|                                                     v  Semi-Discrete Mathematical Formulation                           |
|    [ 3. SOLVE WORKSPACE ]                                                                                               |
|    Structural DAE Compilation    ===>  Graph Partitioning (BLT) ===>  Stiff Integration Kernel (Radau IIA / BDF)        |
|    (Hopcroft-Karp / Pantelides)        (Tarjan SCC / DM Matching)     (Nested Flash, C^1 Kink Bisection, Event Logic)   |
|                                                     |                                                                   |
|                                                     v  Unified Trajectory Schema (rage.resultados)                       |
|    [ 4. RESULTS WORKSPACE ]                                                                                             |
|    Scientific Verification       ===>  Physical Reconstruction  ===>  Decoupled Visualization / Reporting               |
|    (Conservation & Second Law)         (Dimensional Scaling Maps)     (Interactive Dashboards, Tabular Exports)         |
|                                                                                                                         |
+=========================================================================================================================+
```

---

### 14.1 Architectural Foundations: The "Engine of Engines" Paradigm

#### 14.1.1 Separation of Responsibilities and the Client-Server Boundary
The architecture enforces a strict division between mathematical computation and user-facing presentation:
* **The Client Does No Science:** The browser environment (TypeScript/Next.js) is strictly restricted to document editing, Abstract Syntax Tree (AST) serialization, user input validation, and declarative rendering of charts and mathematical expressions. Under no circumstances may physics, thermodynamic phase equilibria, unit conversions, or differential equation integrations be evaluated inside the frontend.
* **Server-Side Scientific Kernel:** All symbolic algebra, unit consistency checks, dimensional analysis, thermodynamic state closures, spatial mesh generation, structural index reductions, and numerical time integrations reside in the server-side Python kernel (`core/` and `backend/`).
* **Contract-First Communication:** All subsystem interactions occur through versioned, strictly typed JSON-RPC and REST data contracts (e.g. `rage.modelo` v0, `rage.formulation-summary` v1, `rage.compilation` v1, `rage.resultados` v1). Before an engine endpoint is implemented, its input schema, output schema, error taxonomy, and automated regression suites must be formally specified.

#### 14.1.2 The Engine Decoupling Principle
Each engine in the system (e.g. `core/balances/`, `core/termodinamica/`, `core/unidades/`, `core/adimensionalizacion/`, `core/compilador/`, `core/solvers/`) is designed as an independent mathematical transformer:
* An engine possesses zero knowledge of other engines; it communicates exclusively through the Common Model.
* An engine takes a well-defined mathematical input structure, applies an axiomatic transformation, and returns an enriched mathematical output structure with explicit error certificates.
* Adding a new capability (such as a new spatial discretization scheme or a new equation of state) requires mounting a new engine between existing pipeline stages without modifying or recompiling upstream or downstream modules.

---

### 14.2 The Common Model (`rage.modelo`) Data Structures and Mathematical Ontology

The Common Model is the single, versioned mathematical document that encapsulates the complete physical problem, its recorded reductions, its mathematical equations, its numerical parameters, and its execution configuration.

#### 14.2.1 Physical Layer Entity Schema
In the physical layer, the process domain is represented as a directed topological network of control volumes, transport streams, thermal links, and chemical species:

```
  =============================================================================================
  Entity Type        Mathematical Interpretation                Key Schema Fields
  =============================================================================================
  Componente         Chemical species identity i \in {1..Nc}   id, nombre, formula, masaMolar, cas
  Paquete            Thermodynamic constitutive potential      id, modelo (IAPWS-95, UNIFAC), datosPuros
  Volumen            Macroscopic/spatial region \Omega_k       id, componenteIds, balances, supuestos,
                                                               frontera, inicial, termodinamica (Cierre)
  Corriente          Convective mass flux vector \Phi_{ij}     id, desde, hasta, mecanismo, materia,
                                                               datoIds, estadoExterior
  Intercambio        Conductive/radiative heat flux Q          id, desde, hasta, ley (impuesto, conductancia),
                                                               temperaturaFronteraId
  Dato               Numerical datum with physical dimension   id, magnitud, declaracion {texto, unidad},
                                                               origen {propietarioId, ruta}
  =============================================================================================
```

#### 14.2.2 Mathematical Layer Ontology: Typed Expression AST
When continuous balances are reduced or when custom user relations are declared, they are represented within the `ModeloMatematico` object as a typed Abstract Syntax Tree (AST):

```
                                      [ ExpressionNode (AST) ]
                                                 |
         +-------------------+-------------------+-------------------+-------------------+
         |                   |                   |                   |                   |
         v                   v                   v                   v                   v
   [ NumberNode ]     [ SymbolNode ]       [ BinaryOpNode ]    [ FunctionNode ]    [ DiffOpNode ]
     val: float         id: string           op: +,-,*,/,^       func: exp,ln,sqrt   op: d/dt, \nabla
     dim: Q^7           role: state,param    left, right: AST    args: List[AST]     wrt: t, x_i
```

##### 1. Dimensional Representation over $\mathbb{Q}^7$
Every `SymbolNode` and `NumberNode` carries a rational dimensional exponent vector $\mathbf{d} \in \mathbb{Q}^7$ corresponding to the SI base units:
$$\mathbf{d} = [d_L, d_M, d_T, d_I, d_\Theta, d_N, d_J]^T \in \mathbb{Q}^7$$
representing $\text{m}^{d_L} \, \text{kg}^{d_M} \, \text{s}^{d_T} \, \text{A}^{d_I} \, \text{K}^{d_\Theta} \, \text{mol}^{d_N} \, \text{cd}^{d_J}$.
Dimensional compatibility is enforced via exact linear algebra over the field of rational numbers $\mathbb{Q}$:
* **Addition / Subtraction ($A \pm B$):** Requires $\mathbf{d}_A = \mathbf{d}_B$.
* **Multiplication ($A \cdot B$):** $\mathbf{d}_{AB} = \mathbf{d}_A + \mathbf{d}_B$.
* **Division ($A / B$):** $\mathbf{d}_{A/B} = \mathbf{d}_A - \mathbf{d}_B$.
* **Power ($A^q, q \in \mathbb{Q}$):** $\mathbf{d}_{A^q} = q \cdot \mathbf{d}_A$, requiring $q \in \mathbb{Q}$ to be dimensionless ($\mathbf{d}_q = \mathbf{0}$).
* **Transcendental Functions ($\exp(A), \ln(A), \sin(A)$):** Requires $\mathbf{d}_A = \mathbf{0}$.

##### 2. Invariant Manifold Constraints (`Restricciones`)
Physical variables are bounded by rigorous state domains. In the Common Model, domain boundaries are formally declared as inequality constraints:
$$\mathcal{R}_k(\mathbf{y}) \ge 0$$
* Non-negative mole numbers: $n_i \ge 0$.
* Absolute temperature bounds: $T \ge T_{\text{min}} > 0$.
* Liquid inventory boundaries: $0 \le V_L \le V_{\text{vessel}}$.
The execution kernel monitors these manifolds; if a trajectory approaches a boundary $\mathcal{R}_k \to 0$, an **exhaustion event** (`agotamiento`) triggers an exact bisection stop. Under no circumstances does the solver silently clip negative concentrations.

---

### 14.3 Model Workspace: Mathematical Deduction and Balance Generation Engine

In accordance with Principle 10, the engine does not allow users to write down final lumped equations directly. Instead, the model starts from the unrestricted microscopic Eulerian balance equations of continuum physics and applies an ordered sequence of recorded deduction operators:

```
  [ Microscopic Conservation Law ]
    \frac{\partial \psi}{\partial t} + \nabla \cdot \mathbf{\phi} = \sigma + s
                           |
                           v   Operation: Volume Integration  \int_V (...) dV
  [ Integral Balance on Deforming Region \Omega(t) ]
    \int_{\Omega(t)} \frac{\partial \psi}{\partial t} dV + \int_{\Omega(t)} \nabla \cdot \mathbf{\phi} \, dV = \int_{\Omega(t)} (\sigma + s) dV
                           |
                           v   Operation: Reynolds Transport Theorem + Gauss Divergence
  [ Macroscopic Boundary Flux Formulation ]
    \frac{d}{dt}\int_{\Omega(t)} \psi \, dV + \int_{\partial\Omega(t)} (\mathbf{\phi} - \psi \mathbf{w}) \cdot \mathbf{n} \, dA = \int_{\Omega(t)} (\sigma + s) dV
                           |
                           v   Operation: Spatial Uniformity (Lumped Parameter Assumption)
  [ Discrete Ordinary Differential Equation (DAE Formulation) ]
    \frac{d I_k}{dt} = \sum_{\text{in}} \Phi_{\text{in}} - \sum_{\text{out}} \Phi_{\text{out}} + \dot{\Omega}_{\text{gen}}
```

#### 14.3.1 The Deduction Algebra $\mathcal{O}_{\text{ded}}$
A deduction step is a formal mapping:
$$\mathcal{O}_{\text{ded}}: \left( \mathcal{E}_{\text{in}}, \mathcal{A}_{\text{hyp}}, \mathcal{D}_{\text{target}} \right) \longrightarrow \left( \mathcal{E}_{\text{out}}, \mathcal{J}_{\text{record}} \right)$$
where $\mathcal{E}_{\text{in}}$ is the incoming equation, $\mathcal{A}_{\text{hyp}}$ is the declared physical assumption, $\mathcal{D}_{\text{target}}$ is the affected domain/volume, $\mathcal{E}_{\text{out}}$ is the resulting reduced equation, and $\mathcal{J}_{\text{record}}$ is the immutable journal entry.

The canonical deduction operations supported by the balance generator (`core/balances/generador.py` and `frontend/app/motor/materialDerivation.ts`) are:
1. `OP_VOLUME_INTEGRATION`: Applies the spatial volume integral $\int_{\Omega} (\dots) dV$.
2. `OP_GAUSS_DIVERGENCE`: Replaces the volume integral of flux divergence with net boundary surface integrals:
   $$\int_{\Omega} \nabla \cdot \boldsymbol{\phi} \, dV \equiv \oint_{\partial\Omega} \boldsymbol{\phi} \cdot \mathbf{n} \, dA$$
3. `OP_REYNOLDS_TRANSPORT`: Accounts for boundary motion velocity $\mathbf{w}$:
   $$\frac{d}{dt}\int_{\Omega(t)} \psi \, dV = \int_{\Omega(t)} \frac{\partial \psi}{\partial t} dV + \oint_{\partial\Omega(t)} \psi (\mathbf{w} \cdot \mathbf{n}) \, dA$$
4. `OP_SPATIAL_UNIFORMITY`: Assumes zero internal spatial gradients ($\nabla \psi = \mathbf{0}$), factoring the intensive variable out of the volume integral:
   $$\int_{\Omega} \psi(\mathbf{x}, t) \, dV = \bar{\psi}(t) \cdot V_{\Omega}(t)$$
5. `OP_DISCRETE_PORTS`: Partitions the closed boundary surface $\partial\Omega$ into discrete inlet/outlet nozzles plus impermeable walls:
   $$\oint_{\partial\Omega} \boldsymbol{\phi} \cdot \mathbf{n} \, dA \equiv \sum_{k \in \text{ports}} \Phi_k \cdot A_k + \int_{\text{wall}} \boldsymbol{\phi} \cdot \mathbf{n} \, dA$$
6. `OP_QUASI_STEADY`: Imposes static invariant inventory ($\frac{d I}{dt} = 0$), transforming differential balances into algebraic flux equality constraints ($\sum \Phi_{\text{in}} = \sum \Phi_{\text{out}}$).
7. `OP_CONSTITUTIVE_COUPLING`: Substitutes a physical closure relation into an unclosed term (e.g., Fourier's law $\mathbf{q} = -k \nabla T$, Fick's law $\mathbf{j}_i = -\rho D_i \nabla w_i$, or reaction rate laws $r = k_0 e^{-E/RT} \prod c_i^{\alpha_i}$).

#### 14.3.2 The Always-Present Thermodynamic Closure Protocol
A central failure mode of traditional simulation software is hardcoding phase assumptions (e.g. designating a unit as a "liquid-only pipe" or "two-phase vessel"). If operating conditions cross a bubble or dew point, such hardcoded software either produces silent errors or crashes.

In this architecture, **thermodynamics is permanently present in every control volume**:
* The dynamic state of volume $k$ integrates only conserved invariant quantities:
  $$\mathbf{y}_{\text{conserved}} = \left[ n_1, n_2, \dots, n_{N_c}, U \right]^T \quad (\text{Rigid Boundary, UV Closure})$$
  $$\mathbf{y}_{\text{conserved}} = \left[ n_1, n_2, \dots, n_{N_c}, H \right]^T \quad (\text{Prescribed Pressure, PH Closure})$$
* At every evaluation of the residual function during numerical integration, the solver passes $\mathbf{y}_{\text{conserved}}$ to the thermodynamic package (`core/termodinamica/capa.py`).
* The thermodynamic layer solves the multiphase equilibrium problem using Michelsen's Tangent Plane Distance ($TPD$) criterion, returning:
  1. Operating temperature $T$ and pressure $P$.
  2. The complete set of candidate phases $\mathcal{P} = \{V, L_1, L_2, \dots\}$.
  3. Phase fractions $\beta_p \ge 0$ ($\sum \beta_p = 1$).
  4. Phase compositions $x_{i, p}$ and chemical potentials $\mu_{i, p}$.
  5. Tangent plane distance stability certificates $tm_p \ge 0$.

Mathematically, this satisfies the Kuhn-Tucker complementarity conditions:
$$\beta_p \ge 0, \quad tm_p \ge 0, \quad \beta_p \cdot tm_p = 0 \quad \forall \, p \in \mathcal{P}$$
* If the fluid is subcooled liquid: $\beta_V = 0$ and $tm_V > 0$. The vapor equations remain active in the system, but yield $\beta_V \equiv 0$ without switching models.
* As heat accumulates and temperature reaches the saturation bubble point: $tm_V \to 0$, whereupon $\beta_V$ naturally grows from zero.
* The physical equations never change; phase transitions emerge entirely from the thermodynamic state potential.

---

### 14.4 Transform Workspace: Transformation Pipelines, Symmetries, and Discretization

The Transform workspace operates as a mathematical operator pipeline between the continuous physical model and the discrete numerical solver:
$$\mathcal{M}_{\text{transformed}} = \mathcal{T}_N \circ \dots \circ \mathcal{T}_2 \circ \mathcal{T}_1 (\mathcal{M}_{\text{model}})$$
Each transformation operator $\mathcal{T}_k$ is a pure mathematical function that consumes a model formulation and produces an enriched formulation along with an invertible mapping dictionary $\mathbf{x} = \mathcal{M}_{\text{map}}(\hat{\mathbf{x}})$, validity conditions, and an exact equivalence certificate.

```
+=========================================================================================================================+
|                                              TRANSFORM WORKSPACE PIPELINE                                               |
+=========================================================================================================================+
|                                                                                                                         |
|       [ Physical Model M_model ]                                                                                        |
|                   |                                                                                                     |
|                   v   Technique 1: Dimensional Analysis & Lie Scaling (core/adimensionalizacion/)                      |
|       [ Dimensionless Model M_dimless ]                                                                                 |
|         - Matrix Buckingham \Pi nullspace over Q^7: \Pi_j = \prod x_i^{\alpha_{ij}}                                     |
|         - Direct scaling maps: x = X \hat{x}, t = \tau \hat{t}                                                          |
|         - Certified condition number optimization: cond(J) -> min                                                       |
|                   |                                                                                                     |
|                   v   Technique 2: Coordinate & Metric Transformations (core/discretizacion/geometria)                  |
|       [ Manifold Mapping M_curv ]                                                                                       |
|         - Coordinate transformation x = \phi(\xi)                                                                       |
|         - Metric tensor g_{ij} and Christoffel symbols \Gamma_{jk}^i                                                    |
|                   |                                                                                                     |
|                   v   Technique 3: Spatial Discretization Operator (core/discretizacion/fvm)                             |
|       [ Semi-Discrete System M_discrete ]                                                                               |
|         - Unstructured mesh topology graph G = (V, E, F, C)                                                             |
|         - Face area vectors A_f, non-orthogonality delta_f, skewness vectors                                            |
|         - Cell-Centered FVM assembly: \sum_{f} (F_f^{conv} - F_f^{diff}) \cdot A_f                                      |
|         - High-resolution TVD limiters + Rhie-Chow colocated face velocity interpolation                               |
|                   |                                                                                                     |
|                   +-----------------------------------+                                                                 |
|                                                       |                                                                 |
|                                                       v                                                                 |
|                                      [ Feed to Solve Workspace ]                                                        |
|                                                                                                                         |
+=========================================================================================================================+
```

#### 14.4.1 Nondimensionalization Engine Software Implementation
The nondimensionalization engine (`core/adimensionalizacion/`) accepts a mathematical model and applies group-theoretic scaling without changing the underlying physics:
1. **Dimension Matrix Assembly:** Constructs matrix $\mathbf{D} \in \mathbb{Q}^{7 \times N_v}$ from the dimensional exponent vectors of all system variables.
2. **Rational Nullspace Kernel:** Computes the exact integer/rational basis of $\ker(\mathbf{D})$ using Smith Normal Form and Gaussian elimination over $\mathbb{Q}$. This guarantees exact, round-off-free dimensionless $\Pi$-groups.
3. **Logarithmic Optimization of Scale Factors:** Solves the linear program:
   $$\min_{\mathbf{s}} \|\mathbf{J}_{\text{scaled}}(\mathbf{s})\|_{\infty} \quad \text{subject to } \mathbf{C}_{\text{dim}} \mathbf{s} = \mathbf{0}$$
   to balance equation magnitudes near $\mathcal{O}(1)$, reducing the condition number of the numerical Jacobian matrix $\kappa(\mathbf{J})$ by multiple orders of magnitude before passing the system to the stiff solver.

#### 14.4.2 Spatial Discretization Engine and Generalized Mesh Topology
When a model contains spatial differential operators ($\nabla, \nabla \cdot, \nabla^2$), the discretization engine converts continuous partial differential equations (PDEs) into a semi-discrete DAE system of the form:
$$\mathbf{M} \frac{d\mathbf{Y}}{dt} = \mathbf{R}_{\text{discrete}}(\mathbf{Y}, t)$$

##### Unstructured Mesh Graph Data Structure
The mesh is represented as an adjacency topological graph $\mathcal{G}_{\text{mesh}} = (\mathcal{V}, \mathcal{E}, \mathcal{F}, \mathcal{C})$:
```python
class MeshTopology:
    nodes: np.ndarray          # Shape (N_nodes, 3): Coordinates [x, y, z]
    cells: List[Cell]          # List of polyhedral/hexagonal/simplicial cells
    faces: List[Face]          # List of interior and boundary faces
    
class Cell:
    id: int
    centroid: np.ndarray       # Center of mass x_C = (1/V) \int_V x dV
    volume: float              # Volume |Omega_C| via Gauss divergence theorem
    faces: List[int]           # Indices of bounding faces
    neighbors: List[int]       # Indices of adjacent cells sharing a face

class Face:
    id: int
    centroid: np.ndarray       # Face area centroid x_f = (1/A) \int_A x dA
    area: float                # Face area |A_f|
    normal: np.ndarray         # Unit normal vector n_f pointing from owner P to neighbor E
    owner: int                 # Cell index P
    neighbor: Optional[int]    # Cell index E (or None for boundary faces)
    boundary_tag: Optional[str]# Tag for boundary conditions (Dirichlet, Neumann, Robin)
```

##### Discrete Face Flux Assembly
For every cell $P \in \mathcal{C}$, the conservation law is integrated over control volume $\Omega_P$:
$$\int_{\Omega_P} \frac{\partial \phi}{\partial t} dV + \sum_{f \in \mathcal{F}_P} \int_{A_f} \mathbf{F} \cdot \mathbf{n} \, dA = \int_{\Omega_P} S_\phi \, dV$$
* **Convective Face Flux ($F_{f}^{\text{conv}}$):**
  $$F_{f}^{\text{conv}} = \dot{m}_f \left[ \phi_{P} + \frac{1}{2} \psi(r_f) (\phi_E - \phi_P) \right]$$
  where $\psi(r_f)$ is a TVD limiter (e.g. Sweby, Superbee, or Minmod) preventing spurious oscillations near steep gradients.
* **Diffusive Face Flux ($F_{f}^{\text{diff}}$):**
  $$\int_{A_f} \Gamma (\nabla \phi) \cdot \mathbf{n} \, dA = \Gamma_f \frac{\phi_E - \phi_P}{\|\mathbf{d}_{PE}\|} |\mathbf{A}_f| + \Gamma_f (\overline{\nabla \phi})_f \cdot \mathbf{k}_f$$
  where $\mathbf{k}_f \equiv \mathbf{A}_f - \frac{\mathbf{A}_f \cdot \mathbf{A}_f}{\mathbf{d}_{PE} \cdot \mathbf{A}_f} \mathbf{d}_{PE}$ is the non-orthogonal correction vector (Section 8.5).
* **Rhie-Chow Face Velocity Interpolation:** Evaluated on colocated grids to prevent pressure-velocity checkerboard decoupling (Section 8.11).

---

### 14.5 Solve Workspace: Symbolic Compilation, Index Theory, and Numerical Execution

The Solve workspace transforms the semi-discrete mathematical formulation into an optimized, executable numerical residual program, resolves structural algebraic singularities, and performs stiff time integration.

```
+=========================================================================================================================+
|                                                SOLVE WORKSPACE COMPILATION                                              |
+=========================================================================================================================+
|                                                                                                                         |
|       [ Input Mathematical Formulation (Transform Output) ]                                                             |
|                                |                                                                                        |
|                                v   Step 1: Structural Analysis & Bipartite Matching                                     |
|       [ Dulmage-Mendelsohn Structural Decomposition ]                                                                   |
|         - Bipartite graph G = (Equations, Variables)                                                                    |
|         - Hopcroft-Karp maximum cardinality matching                                                                    |
|         - Over-determined / Under-determined / Well-posed partitioning                                                  |
|                                |                                                                                        |
|                                v   Step 2: Strongly Connected Components & BLT Ordering                                 |
|       [ Block Lower Triangular (BLT) Matrix ]                                                                           |
|         - Tarjan's SCC depth-first search algorithm                                                                     |
|         - Decouples large N_eq system into sequence of small irreducible scalar & coupled blocks                        |
|                                |                                                                                        |
|                                v   Step 3: DAE Index Reduction & State Space Identification                             |
|       [ Pantelides Structural Index Reduction ]                                                                         |
|         - Differentiates algebraic constraints to expose hidden state manifolds                                         |
|         - Mattsson-Söderlind dummy derivatives to maintain index-1 formulation                                          |
|                                |                                                                                        |
|                                v   Step 4: Analytic Jacobian & Sparsity Assembly                                        |
|       [ Residual Function F(t, y, y_dot, p) & Sparse Jacobian J ]                                                       |
|         - Symbolic/algorithmic automatic differentiation                                                                |
|         - Compressed Sparse Row (CSR) matrix patterns                                                                   |
|                                |                                                                                        |
|                                v   Step 5: Stiff Numerical Integration Kernel                                           |
|       [ Stiff Integrator (Radau IIA / Variable-Order BDF) ]                                                             |
|         - Semismooth Newton iteration with shared LU factorizations                                                     |
|         - Event localization: Bracketed bisection along phase boundary indicators g_i(t, y) = 0                         |
|         - Warm restarts across C^1 thermodynamic kinks                                                                  |
|                                                                                                                         |
+=========================================================================================================================+
```

#### 14.5.1 Symbolic Model Compiler (`core/compilador/`)
The compiler transforms symbolic mathematical ASTs into high-performance Python/NumPy callable functions:

##### 1. Bipartite Matching and Structural Degrees of Freedom (DOF)
The system is modeled as a bipartite graph $\mathcal{G}_{\text{bipartite}} = (\mathcal{V}_{\text{eq}}, \mathcal{V}_{\text{var}}, \mathcal{E})$, where an edge $(i, j) \in \mathcal{E}$ exists if variable $y_j$ appears in equation $F_i$.
* **Hopcroft-Karp Algorithm:** Finds a maximum cardinality matching $\mathcal{M}^*$ in $\mathcal{O}(|\mathcal{E}| \sqrt{|\mathcal{V}|})$ time.
* **Dulmage-Mendelsohn Decomposition:** Partitions the system into:
  - Under-determined subsystem ($\mathcal{V}_{\text{var}} > \mathcal{V}_{\text{eq}}$): Unspecified degrees of freedom; compiler halts and reports exact missing boundary conditions.
  - Over-determined subsystem ($\mathcal{V}_{\text{eq}} > \mathcal{V}_{\text{var}}$): Redundant or contradictory constraints; compiler isolates conflicting physical laws.
  - Well-determined subsystem ($\mathcal{V}_{\text{eq}} = \mathcal{V}_{\text{var}}$): Exactly solvable square algebraic-differential problem.

##### 2. Block Lower Triangular (BLT) Partitioning via Tarjan's SCC Algorithm
Instead of solving a monolithic non-linear algebraic system of size $N \sim 10^4 - 10^6$, the compiler constructs a directed dependency graph among equations and applies **Tarjan's Strongly Connected Components (SCC) algorithm**:
$$\mathbf{A}_{\text{BLT}} = \mathbf{P} \mathbf{J} \mathbf{Q}^T = \begin{bmatrix} \mathbf{B}_{11} & \mathbf{0} & \dots & \mathbf{0} \\ \mathbf{B}_{21} & \mathbf{B}_{22} & \dots & \mathbf{0} \\ \vdots & \vdots & \ddots & \vdots \\ \mathbf{B}_{M1} & \mathbf{B}_{M2} & \dots & \mathbf{B}_{MM} \end{bmatrix}$$
* Diagonal blocks $\mathbf{B}_{kk}$ with size $1 \times 1$ represent explicit assignment equations solved sequentially without iteration.
* Diagonal blocks $\mathbf{B}_{kk}$ with size $m_k \times m_k$ ($m_k > 1$) represent minimal coupled algebraic loops, solved locally using Newton-Raphson.
* This block triangularization reduces linear algebra factorizations from $\mathcal{O}(N^3)$ to $\sum_k \mathcal{O}(m_k^3)$, yielding speedups exceeding $10^2 - 10^3$.

##### 3. Pantelides Algorithm for Structural Index Reduction
Differential-Algebraic Equations (DAEs) with differential index $\nu \ge 2$ cannot be stably integrated by standard stiff ODE solvers. The compiler executes the **Pantelides algorithm**:
1. It identifies structural constraints on algebraic state variables.
2. It traces alternating paths on the bipartite equation-variable graph to determine the minimal number of time differentiations required for each equation.
3. For each differentiated constraint, it applies the **Mattsson-Söderlind dummy derivative method**, introducing algebraic proxy variables for higher-order derivatives to eliminate drift and ensure that the discretized DAE remains strictly index-1.

#### 14.5.2 Numerical Execution Engine (`core/solvers/`)

##### 1. Residual Function Evaluation Protocol
The compiler outputs a standardized vector residual function:
$$\mathbf{F}(t, \mathbf{y}, \dot{\mathbf{y}}, \mathbf{p}) = \mathbf{0}$$
where:
* $\mathbf{y} \in \mathbb{R}^{N_y}$ is the composite state vector (differential inventories $\mathbf{x}$ and algebraic variables $\mathbf{z}$).
* $\dot{\mathbf{y}} \in \mathbb{R}^{N_y}$ is the time derivative vector (with $\dot{z}_j \equiv 0$ for algebraic states).
* $\mathbf{p} \in \mathbb{R}^{N_p}$ is the invariant parameter vector.

##### 2. Event Localization and Phase Discontinuity Protocol
When integrating across phase boundaries (e.g., onset of boiling, disappearance of liquid, opening of pressure relief valves), thermodynamic derivatives exhibit jump discontinuities ($C^1$ kinks in enthalpy $h(T)$ and heat capacity $c_p$).
The solver monitors a vector of continuous **zero-crossing indicator functions**:
$$\mathbf{g}(t, \mathbf{y}) = [g_1(t, \mathbf{y}), g_2(t, \mathbf{y}), \dots, g_{N_e}(t, \mathbf{y})]^T$$
* A phase event occurs in time interval $[t_n, t_{n+1}]$ whenever $\text{sign}(g_k(t_n)) \ne \text{sign}(g_k(t_{n+1}))$.
* **Bracketing and Bisection:** The integrator rejects step $h = t_{n+1} - t_n$ and executes Illinois-accelerated bisection to locate event root $t^*$ such that $|g_k(t^*)| < \epsilon_{\text{event}} \sim 10^{-10}$.
* **Warm-Restart:** At $t^*$, the solver halts integration, updates the thermodynamic phase signature, re-initializes consistent algebraic state variables $\mathbf{z}(t^*)$ via a Newton solve, resets step size to $h_{\text{init}}$, and restarts integration with initial order $p=1$. This prevents the integrator from attempting to smooth across non-differentiable physical kinks.

##### 3. Stiff Integration Kernels
* **Implicit Runge-Kutta Radau IIA (Order 5, 3 stages):** Fully implicit collocation method possessing $L$-stability, strictly damping high-frequency numerical oscillations and stably integrating index-1 and index-2 DAEs without algebraic drift.
* **Variable-Order Backward Differentiation Formulas (BDF-1 through BDF-5):** Stiff multistep method featuring adaptive time-step and order control based on Milne's device local truncation error estimation:
  $$d_n = \|\mathbf{y}_{n+1} - \mathbf{y}_{n+1}^{\text{predictor}}\| \le \text{tol}$$

---

### 14.6 Results Workspace: Data Normalization, Verification, and Rendering Architecture

The Results workspace is responsible for receiving the raw trajectory generated by Solve, performing rigorous physical and mathematical verification audits, reconstructing dimensional variables, and exposing clean data series for visualization and export.

#### 14.6.1 The Unified Results Schema (`rage.resultados`)
The results format is completely independent of the simulated equipment type:
```json
{
  "formato": "rage.resultados",
  "version": 1,
  "modeloId": "heated-filling-vessel",
  "ejecucionId": "run-2026-10-20-001",
  "tiempo": [0.0, 0.1, 0.25, ..., 60.0],
  "series": {
    "volumen.V1.materia.n_total": {
      "nombre": "Total Molar Inventory",
      "unidad": "mol",
      "dimension": [0, 0, 0, 0, 0, 1, 0],
      "valores": [1.0, 1.0001, 1.00025, ...]
    },
    "volumen.V1.temperatura": {
      "nombre": "Liquid Temperature",
      "unidad": "K",
      "dimension": [0, 0, 0, 0, 1, 0, 0],
      "valores": [300.0, 300.08, 300.21, ...]
    }
  },
  "verificaciones": {
    "conservacion_materia": {
      "tipo": "balance_integral",
      "residual_maximo": 1.2e-15,
      "tolerancia": 1e-12,
      "certificado": "passed"
    },
    "segunda_ley": {
      "tipo": "entropia_clausius_duhem",
      "minima_produccion": 4.8e-5,
      "certificado": "passed"
    }
  }
}
```

#### 14.6.2 Scientific Verification and Mathematical Diagnostics
Before presenting results to the user, the Results engine evaluates invariant diagnostic proofs:
1. **Global Conservation Residual Check:**
   $$\epsilon_{\text{mass}}(t) \equiv \frac{\left| m_{\text{sys}}(t) - m_{\text{sys}}(0) - \int_0^t (\dot{m}_{\text{in}} - \dot{m}_{\text{out}}) \, d\tau \right|}{\max_{\tau \in [0, t]} m_{\text{sys}}(\tau)} \le 10^{-12}$$
   An identical audit is computed for total stored energy $E = U + E_{\text{kin}} + E_{\text{pot}}$.
2. **Clausius-Duhem Second Law Audit:**
   $$\sigma_s(\mathbf{x}, t) \ge -\epsilon_{\text{tol}} \quad \forall \, t \ge 0$$
   Ensures that no numerical step generated negative entropy production or non-physical mass transfer contrary to the Second Law.

---

### 14.7 Implementation Blueprint: Object-Oriented and Functional Software Architecture

The following UML class structure defines the target object-oriented hierarchy implemented across the Python scientific core:

```
+=========================================================================================================================+
|                                           SOFTWARE CLASS ARCHITECTURE BLUEPRINT                                         |
+=========================================================================================================================+

  +-----------------------------------+               +-----------------------------------+
  |          CommonModelDocument      |               |          ThermodynamicLayer       |
  +-----------------------------------+               +-----------------------------------+
  | + id: str                         |               | + packages: Dict[str, Package]    |
  | + components: List[Component]     |               | + flash_uv(n, U, V) -> State      |
  | + volumes: List[ControlVolume]    |               | + flash_ph(n, H, P) -> State      |
  | + streams: List[Stream]           |               | + stability_test(TPD) -> bool     |
  | + math_model: MathModelAST        |               | + compute_properties(T, P, x)     |
  +-----------------------------------+               +-----------------------------------+
                   |                                                    |
                   v                                                    v
  +-----------------------------------+               +-----------------------------------+
  |          BalanceEngine            |               |          DiscretizationEngine     |
  +-----------------------------------+               +-----------------------------------+
  | + apply_deduction(op, volume)     |               | + mesh: MeshTopology              |
  | + reduce_matter_balance()         |               | + assemble_fvm_stencils()         |
  | + reduce_energy_balance()         |               | + evaluate_metric_tensors()       |
  | + replay_journal(journal) -> AST  |               | + apply_rhie_chow_flux()          |
  +-----------------------------------+               +-----------------------------------+
                   |                                                    |
                   v                                                    v
  +---------------------------------------------------------------------------------------+
  |                                     ModelCompiler                                     |
  +---------------------------------------------------------------------------------------+
  | + build_dependency_dag(math_model: MathModelAST) -> DependencyGraph                   |
  | + dulmage_mendelsohn_analysis() -> StructuralDOFReport                                |
  | + tarjan_blt_partitioning() -> List[AlgebraicBlock]                                   |
  | + pantelides_index_reduction() -> ReducedIndex1System                                 |
  | + generate_sparse_jacobian() -> CSRMatrixPattern                                      |
  | + emit_residual_evaluator() -> Callable[[float, ndarray, ndarray], ndarray]           |
  +---------------------------------------------------------------------------------------+
                                           |
                                           v
  +---------------------------------------------------------------------------------------+
  |                                    DAESolverKernel                                    |
  +---------------------------------------------------------------------------------------+
  | + residual_fn: Callable                                                               |
  | + jacobian_fn: Callable                                                               |
  | + indicator_events: List[EventIndicator]                                              |
  | + solve_radau_iia(t_span, y0, rtol, atol) -> TrajectorySet                            |
  | + solve_bdf(t_span, y0, rtol, atol) -> TrajectorySet                                  |
  | + bisect_discontinuity(t_bracket, event_fn) -> float                                  |
  | + execute_warm_restart(t_event, new_phase_signature)                                  |
  +---------------------------------------------------------------------------------------+
                                           |
                                           v
  +---------------------------------------------------------------------------------------+
  |                                 ResultsVerification                                   |
  +---------------------------------------------------------------------------------------+
  | + verify_mass_conservation(trajectory) -> ConservationReport                         |
  | + verify_energy_conservation(trajectory) -> ConservationReport                       |
  | + audit_clausius_duhem_entropy(trajectory) -> SecondLawReport                         |
  | + reconstruct_physical_series(trajectory, scale_maps) -> UnifiedResults               |
  +---------------------------------------------------------------------------------------+
```

#### Step-by-Step Execution Walkthrough of an End-to-End Simulation
To illustrate how the mathematical treatment and software architecture unite in practice, consider the execution trace of the **Heated Filling Vessel** model:

1. **Model Workspace Initialization:**
   - User defines chemical species (Water, Ethanol) and selects thermodynamic package `unifac-original-public`.
   - Control volume $V_1$ is instantiated with rigid boundary condition and initial inventory $\mathbf{n}(0) = [0.8, 0.2]^T \, \text{mol}$, $T(0) = 300 \, \text{K}$.
   - The user selects the deduction operations: `OP_VOLUME_INTEGRATION` $\to$ `OP_GAUSS_DIVERGENCE` $\to$ `OP_SPATIAL_UNIFORMITY`.
   - The balance engine records these operations in `rage.material-derivation` v1 and generates the macroscopic balance:
     $$\frac{d n_i}{dt} = \dot{n}_{i, \text{feed}}, \quad \frac{d H}{dt} = \dot{n}_{\text{feed}} \bar{h}_{\text{feed}} + \dot{Q} + V \frac{dP}{dt}$$
2. **Transform Workspace Execution (Identity or Scaling):**
   - In identity mode, the physical equations pass directly to Solve.
   - If scaling is selected, the nondimensionalization engine computes reference scales ($N_{\text{ref}} = 1.0 \, \text{mol}, \tau = 100 \, \text{s}, H_{\text{ref}} = c_{p, \text{ref}} T_{\text{ref}} N_{\text{ref}}$) and produces the certified dimensionless system:
     $$\frac{d \hat{n}_i}{d \hat{t}} = \hat{\Phi}_i, \quad \frac{d \hat{H}}{d \hat{t}} = \hat{\Phi}_H$$
3. **Solve Workspace Compilation and Integration:**
   - The compiler verifies well-posedness via Dulmage-Mendelsohn (DOF $= 0$).
   - Pantelides algorithm confirms the system is index-1.
   - Symbolic differentiation builds analytic Jacobian $\mathbf{J}_{\mathbf{y}}$.
   - Time-stepper (Radau IIA) advances from $t=0$ to $t=60 \, \text{s}$. At every internal Newton iteration:
     - State $\mathbf{y} = [n_W, n_E, H]^T$ is passed to `capa.py`.
     - UV/PH flash calculates $T$, liquid-vapor split $\beta_V$, and caloric properties without hardcoding phase presence.
     - Event indicator $g_1(t, \mathbf{y}) = tm_{\text{vapor}}$ is monitored. If boiling occurs, bisection isolates $t^*$, and warm restart resumes integration.
4. **Results Workspace Verification:**
   - Trajectory is verified against the analytical integral:
     $$n_W(t) = 0.8 + 0.0005 t, \quad n_E(t) = 0.2 + 0.0005 t$$
   - Enthalpy closure residual evaluates to $\epsilon_{\text{energy}} < 10^{-14}$.
   - Results are serialized to `rage.resultados` and visual plots are rendered on the frontend dashboard.

---

## 15. References and Computational Index

1. Bird, R. B., Stewart, W. E., Lightfoot, E. N. *Transport Phenomena*, 2nd ed., John Wiley & Sons, New York, 2002.
2. Prausnitz, J. M., Lichtenthaler, R. N., de Azevedo, E. G. *Molecular Thermodynamics of Fluid-Phase Equilibria*, 3rd ed., Prentice Hall, 1999.
3. Michelsen, M. L., Mollerup, J. M. *Thermodynamic Models: Fundamentals & Computational Aspects*, Tie-Line Publications, 2007.
4. Wagner, W., Pruss, A. "The IAPWS Formulation 1995 for the Thermodynamic Properties of Ordinary Water Substance for General and Scientific Use", *J. Phys. Chem. Ref. Data*, 31(2):387-535, 2002.
5. Fredenslund, A., Jones, R. L., Prausnitz, J. M. "Group-contribution estimation of activity coefficients in nonideal liquid mixtures", *AIChE J.*, 21(6):1086-1099, 1975.
6. Churchill, S. W. "Friction-factor equation spans all fluid-flow regimes", *Chemical Engineering*, 84(24):91-92, 1977.
7. Bluman, G. W., Kumei, S. *Symmetries and Differential Equations*, Applied Mathematical Sciences, Vol. 81, Springer-Verlag, New York, 1989.
8. Barenblatt, G. I. *Scaling, Self-similarity, and Intermediate Asymptotics*, Cambridge University Press, Cambridge, 1996.
9. Bender, C. M., Orszag, S. A. *Advanced Mathematical Methods for Scientists and Engineers I: Asymptotic Methods and Perturbation Theory*, Springer, New York, 1999.
10. Strogatz, S. H. *Nonlinear Dynamics and Chaos: With Applications to Physics, Biology, Chemistry, and Engineering*, Westview Press, 2014.
11. Hairer, E., Nørsett, S. P., Wanner, G. *Solving Ordinary Differential Equations I: Nonstiff Problems*, Springer-Verlag, Berlin, 1993.
12. Hairer, E., Wanner, G. *Solving Ordinary Differential Equations II: Stiff and Differential-Algebraic Problems*, 2nd ed., Springer-Verlag, Berlin, 1996.
13. Brenan, K. E., Campbell, S. L., Petzold, L. R. *Numerical Solution of Initial-Value Problems in Differential-Algebraic Equations*, SIAM, Philadelphia, 1996.
14. Pantelides, C. C. "The consistent initialization of differential-algebraic systems", *SIAM J. Sci. Stat. Comput.*, 9(2):213-231, 1988.
15. Mattsson, S. E., Söderlind, G. "Index reduction in differential-algebraic equations using dummy derivatives", *SIAM J. Sci. Comput.*, 14(3):677-692, 1993.
16. LeVeque, R. J. *Finite Volume Methods for Hyperbolic Problems*, Cambridge University Press, Cambridge, 2002.
17. Hirsch, C. *Numerical Computation of Internal and External Flows: The Fundamentals of Computational Fluid Dynamics*, 2nd ed., Butterworth-Heinemann, Oxford, 2007.
18. Sweby, P. K. "High resolution schemes using flux limiters for hyperbolic conservation laws", *SIAM J. Numer. Anal.*, 21(5):995-1011, 1984.
19. Roache, P. J. *Verification and Validation in Computational Science and Engineering*, Hermosa Publishers, Albuquerque, 1998.
20. Taylor, R., Krishna, R. *Multicomponent Mass Transfer*, John Wiley & Sons, New York, 1993.
21. Doherty, M. F., Malone, M. F. *Conceptual Design of Distillation Systems*, McGraw-Hill, New York, 2001.
22. Fogler, H. S. *Elements of Chemical Reaction Engineering*, 5th ed., Prentice Hall, Boston, 2016.
23. Incropera, F. P., DeWitt, D. P., Bergman, T. L., Lavine, A. S. *Fundamentals of Heat and Mass Transfer*, 6th ed., John Wiley & Sons, Hoboken, 2007.
24. Kays, W. M., London, A. L. *Compact Heat Exchangers*, 3rd ed., McGraw-Hill, New York, 1984.
25. Seader, J. D., Henley, E. J., Roper, D. K. *Separation Process Principles: Chemical and Biochemical Operations*, 3rd ed., John Wiley & Sons, 2011.
26. de Groot, S. R., Mazur, P. *Non-Equilibrium Thermodynamics*, North-Holland Publishing Company, Amsterdam, 1962 (Dover reprint, 1984).
27. Onsager, L. "Reciprocal relations in irreversible processes. I.", *Physical Review*, 37(4):405-426, 1931.
28. Onsager, L. "Reciprocal relations in irreversible processes. II.", *Physical Review*, 38(12):2265-2279, 1931.
29. Prigogine, I. *Introduction to Thermodynamics of Irreversible Processes*, Charles C Thomas, Springfield, 1955.
30. Slattery, J. C. *Advanced Transport Phenomena*, Cambridge University Press, Cambridge, 1999.
31. Whitaker, S. *The Method of Volume Averaging*, Theory and Applications of Transport in Porous Media, Vol. 13, Kluwer Academic Publishers, Dordrecht, 1999.
32. Gray, W. G. "A derivation of the equations for multi-phase transport", *Chem. Eng. Sci.*, 30(2):229-233, 1975.
33. Beavers, G. S., Joseph, D. D. "Boundary conditions at a naturally permeable wall", *J. Fluid Mech.*, 30(1):197-207, 1967.
34. Saffman, P. G. "On the boundary condition at the surface of a porous medium", *Studies in Applied Mathematics*, 50(2):93-101, 1971.
35. Wilcox, D. C. *Turbulence Modeling for CFD*, 3rd ed., DCW Industries, La Cañada, CA, 2006.
36. Launder, B. E., Sharma, B. I. "Application of the energy-dissipation model of turbulence to the calculation of flow near a spinning disc", *Lett. Heat Mass Transfer*, 1(2):131-137, 1974.
37. Menter, F. R. "Two-equation eddy-viscosity turbulence models for engineering applications", *AIAA Journal*, 32(8):1598-1605, 1994.
38. Nicoud, F., Ducros, F. "Subgrid-scale stress modelling based on the square of the velocity gradient tensor", *Flow, Turbulence and Combustion*, 62(3):183-200, 1999.
39. Spalart, P. R., Jou, W. H., Strelets, M., Allmaras, S. R. "Comments on the feasibility of LES for wings, and on a hybrid RANS/LES approach", *Advances in DNS/LES*, 1:4-8, 1997.
40. Spalart, P. R., Deck, S., Shur, M. L., Squires, K. D., Strelets, M. K., Travin, A. "A new version of detached-eddy simulation, addressing the defect of premature separation", *Theoretical and Computational Fluid Dynamics*, 20(3):181-195, 2006.
41. Ergun, S. "Fluid flow through packed columns", *Chem. Eng. Prog.*, 48(2):89-94, 1952.
42. Cao, Y., Li, S., Petzold, L., Serban, R. "Adjoint sensitivity analysis for differential-algebraic equations: The adjoint DAE system and its numerical solution", *SIAM J. Sci. Comput.*, 24(3):1076-1089, 2003.
43. Feehery, W. F., Tolsma, J. E., Barton, P. I. "Efficient sensitivity analysis of large-scale differential-algebraic systems", *Appl. Numer. Math.*, 25(1):41-54, 1997.
44. Biegler, L. T. *Nonlinear Programming: Concepts, Algorithms, and Applications to Chemical Processes*, MOS-SIAM Series on Optimization, SIAM, Philadelphia, 2010.
45. Wächter, A., Biegler, L. T. "On the implementation of an interior-point filter line-search algorithm for large-scale nonlinear programming", *Mathematical Programming*, 106(1):25-57, 2006.
46. Kato, K., Launder, B. E. "The modelling of turbulent flow around stationary and vibrating square cylinders", *Proc. 9th Symp. on Turbulent Shear Flows*, Kyoto, Japan, 1993.
47. Lumley, J. L. "Computational modeling of turbulent flows", *Advances in Applied Mechanics*, 18:123-176, 1978.
48. Scriven, L. E., Sternling, C. V. "The Marangoni effects", *Nature*, 187(4733):186-188, 1960.
49. Sternling, C. V., Scriven, L. E. "Interfacial turbulence: Hydrodynamic instability and the Marangoni effect", *AIChE J.*, 5(4):514-523, 1959.
50. Wesseling, P. *Principles of Computational Fluid Dynamics*, Springer Series in Computational Mathematics, Vol. 29, Springer, Berlin, 2001.

---
*End of Comprehensive Mathematical Foundations Monograph.*
