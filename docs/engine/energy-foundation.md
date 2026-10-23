# Energy: foundation and first assembly

Scope: the independent reference `/motor`. The lab and the backend are not modified.

## Conventions

The local equation conserves internal plus kinetic energy: e = u + |v|²/2. The work of body forces is kept explicit; potential energy is not added at the same time, to avoid counting gravity twice. The flux q is the non-convective energy flux; the first single-component solver does not implement energy diffusion of mixtures.

Each transformation is recorded as a mathematical operation by the user: integrate the local equation and apply Gauss; apply Reynolds for a moving boundary; split sigma = -p I + tau; group u + p/rho into h; partition the boundary into ports and the remaining surface. One never goes directly from a PDE to a tank.

For the moving boundary:

dE/dt = -integral_surface rho e (v-v_b).n - integral_surface q.n + integral_surface (sigma.v).n + integral_volume rho b.v + integral_volume r_v.

Grouping the flow work:

dE/dt = sum_inlets mdot (h+ec) - sum_outlets mdot (h+ec) - Phi_rest + Q - W_b + W_tau + W_bvol + R.

W_b = integral_surface p v_b.n. With uniform pressure W_b = p dV/dt. Q is positive toward the volume; pressure work is positive outward and carries a minus sign. W_tau and W_bvol are powers toward the system. An adiabatic boundary cancels the total Q; it does not impose q=0 everywhere inside.

## First executable contract

One volume, one species, transient macroscopic conservation, no material sources, no undeclared material transport through the rest of the boundary. Active accumulation, negligible kinetic energy, uniform temperature and specific energy, single phase without phase change, all declared by the user. Viscous work, body-force work and the volumetric contribution can be removed by hypothesis or declared as integrated powers. No stress fields or forces are deduced from these powers. These choices do not certify the phase thermodynamically.

An explicit energy relation u(T) = u_ref + c_u (T-T_ref), with positive c_u, units, a reference and a declared thermal domain. U=m u(T). T is obtained from this relation; dU/dt is not replaced by a fixed capacity when m changes.

In an open volume, constant mixture density and spatially uniform pressure must be declared. h=u+p/rho; V=m/rho; W_b=p dm/dt/rho for a moving boundary. A fixed boundary with this model requires dm/dt=0 at every evaluation; an outlet flow is never forced to achieve it. The complete transport and boundary-work terms are kept. u+p/rho can be grouped into h, or internal transport and flow work kept separate: both representations use their own structured terms, without counting the flow work twice.

Each material stream is evaluated with the same SI flow as the mass balance. The matter compiler keeps one common evaluation of rates for the same time and state; energy consumes those values. The outgoing fluid uses the volume's T by the uniform hypothesis. The inlet uses a declared external T. A flow that can reverse direction also needs an external T at the nominal outlet boundary; a return T is never invented. An outlet of constant sign needs no external temperature. Matter specification per component, or total plus composition, is accepted; in this milestone there is a single species.

Energy alone is accepted in a closed volume with constant mass as a datum. Active matter and energy share a vector [m,U]. U accepts negative values because of its reference and has a tolerance in J independent of the mass tolerance. There is no flash or provider, phase equilibrium, multicomponent energy, several volumes with energy, 1D energy conduction or steady-state solver in this milestone.

## Evidence and responsibilities

The structured terms of the total balance are used to render and to evaluate the residual. The u(T) relation evaluates state; it does not change masses or flows. The coordinator obtains the same fluxes from the matter compiler; the integrator keeps mass and energy budgets separately. Series are published with their units and the traceability of terms, data used, inactive data and the phase assumed without verification. U is an energy variable with unit J, never a fictitious chemical component.

The structural count includes the differential states and the algebraic relations of T, V (when constant density is declared) and the streams' h. The latter are eliminated explicitly when evaluating the system; they need no other integrator and are not counted as missing data. Initial conditions are checked separately. The count does not certify a general numerical rank. The user chooses T(0) or U(0); the alternative kept in the data bank stays inactive. A positive initial mass and an initial temperature within the domain are checked before solving.

Units: absolute temperatures K/°C/°F with offset; J/kJ, J/kg or kJ/kg, J/(kg K) or kJ/(kg K), W/kW and Pa/kPa/bar. Energy expressions receive t [s], m [kg], U [J], T [K] and, when available, V [m³] and rho [kg/m³]. The chosen unit converts the result. Heat or power as a function of the state is accepted; there is no dimensional certification of the internal coefficients of free expressions. Flow expressions keep the current matter dependencies: they do not accept T feedback yet.

The thermal limits are watched through events with both RK45 and implicit Euler. A crossing stops the trajectory at the last valid state and publishes a partial result; an initial state outside the domain is rejected. The u(T) law can be evaluated at trial stages outside the domain in order to locate the event, without publishing those stages as valid states. An initially empty volume has no T defined from U/m. Complete draining is singular for this representation; it does not continue as if there were fluid, and no regime after depletion is certified.

The library offers six editable documents through "Añadir pruebas · materia + energía" (add tests · matter + energy): closed heating, cooling with Q(T), hot inlet at constant amount, filling with heat, draining with a cold inlet, and filling with a hot inlet without external heat. They are test data and hypotheses, not special branches of the compiler. Every sheet starts from the local equation; choosing the total form keeps the intermediate Gauss and Reynolds steps. Undo physically removes the steps and Redo restores them. A topology change needs the energy derivation's context to be updated explicitly before running.

The sixth document (`motor-prueba-energia-v1-6`) starts with 100 kg at 293.15 K, receives 2 kg/s at 333.15 K and discharges 1 kg/s. At 100 s it has 200 kg, 323.15 K and 0.2 m³. Its reference is m(t)=100+t and T(t)=333.15−40[100/(100+t)]²; it uses the same manual relation c_u=4000 J/(kg K), rho=1000 kg/m³ and p=100000 Pa as the other test fluids. This document's initial charts show mass and temperature side by side. Adding it keeps the existing documents, even if the user modified them.

The Resolver screen now presents the final equations in a section of their own, with matter/energy labels, each family's accent and a state relation of lower visual hierarchy. Symbols stay neutral and equations stay horizontal until their length requires wrapping terms. It is a presentation change: the LaTeX generated from the same structured formulations is kept.

(Since 19 October 2026 the thermodynamic assumptions of these sheets — one phase, no phase change, constant density, u(T) — are declared in the Thermodynamics panel's own derivation, not in the energy derivation: [docs/contracts/thermodynamic-layer.md](../contracts/thermodynamic-layer.md) §4 bis.)

## Verification of this delivery

- `npm run test:motor-fundamental`: every matter suite and the energy suite pass. The earlier matter cases keep their results.
- `verificar_energia_motor.mjs`: includes symbolic rendering, persistence and validation; the number of checks does not represent independent physical experiments.
- Six analytical references of m(t)/T(t), RK45 and implicit Euler. With rtol=1e-9, maximum temperature error of RK45 ≤3.4e-11 K and of implicit Euler ≤2.1e-4 K; the second method keeps its order one.
- An independent nonlinear reference written in T and integrated with RK4; product rule, conservation, changes of energy reference, negative U, pressure and equivalent units.
- Equivalence between transport through h and through u plus flow work; reversal of orientation with the correct donor state; stream adapters without temperature duplication; rejection of incompatible pressure.
- Thermal events, including leaving the regime at t=0, independent Gauss/Reynolds references, balance selection and preservation of the chemical catalog.
- TypeScript and ESLint pass.

The initial delivery checked navigation, the local equation and template addition in the browser; its complete visual traversal was left pending at that time. The current shared-deduction milestone below adds live browser/API verification and analytical solved-result checks, recorded in the workspace specification.

Physical references: [MIT, Control volume form of the conservation laws](https://web.mit.edu/16.unified/www/FALL/thermodynamics/notes/node19.html), for the first law, flow work and enthalpy; [COMSOL, Conservation of Energy](https://www.comsol.com/multiphysics/heat-transfer-conservation-of-energy), for the local equation and the stress and energy-flux terms.

## Shared deduction milestone (19 October 2026)

The local-to-total first-law journal now connects the supported Model authoring path, Python mathematical development, common and revision-2 validation, compilation inspection and Results provenance. Energy history stores actual operation inputs; legacy snapshots are not reconstructed as real operations. Network volumes support explicit rebuild, undo and restoration. New templates use checked derivation recipes. Thermodynamic assumptions and package selection remain in the separate state journal.

The equilibrium compiler explicitly rejects unsupported energy terms, algebraic accumulation and inconsistent heat assumptions. Uniform prescribed-pressure execution retains `V dP/dt` after `H=U+PV`; independent tests check the actual RHS. Adiabatic boundaries do not imply zero internal heat flux. The deduction milestone is complete within the supported transient uniform-volume scope; spatial energy, reaction energy, momentum-coupled work, general DAEs and dynamic solid transitions remain separate physical extensions. Contracts and endpoint details are maintained in [common model §9](../contracts/common-model.md#9-first-law-and-thermodynamic-operation-journals), with the live scope in [Engine capabilities](engine-checklist.md).
