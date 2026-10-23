# Definition of the volume and the roles of its variables

14 October 2026. Scope: the independent engine `/motor`. Backend and lab not modified. Claude keeps responsibility for the thermodynamic service.

## A definition that affects the model

The State view opens "Volumen de control" (control volume). The alternatives read and modify the existing formulation; they do not store a second, independent mechanical label:

| Choice | Effect |
|---|---|
| Fixed volume | Fixed boundary, declared geometric volume, dV/dt = 0 and zero boundary work. |
| Moving boundary | Keeps the pressure-work term. It does not invent the pending mechanical relation. |
| Given external pressure | Moving boundary and prescribed uniform pressure, with work P_ext dV/dt. The magnitude of P is declared with its unit in Resolver. |

Choosing a fixed volume starts an empty geometric datum if none existed. Its value must be constant, positive and have a compatible unit. `volumen` or the assembly's volume key is reused when it already exists; otherwise `geometria_V` is used. State and Resolver read the same data bank. The declared geometry also appears in the final equations, the traceability and the V series of the energy results.

The change is recorded in the mathematical breakdowns and removes the reference to the earlier result. It does not delete initial masses, flows or declared properties. Data that stop being active are kept so it is possible to go back to another formulation.

A fixed boundary by itself does not forbid accumulating mass. In the current homogeneous model, also imposing constant density and occupied V = geometric V imposes constant mass: the compiler rejects incompatible inlets/outlets and also an m/ρ different from the geometric V. A partly filled tank needs to tell geometric volume from occupied volume and declare the remaining space; this change does not introduce that physics silently.

## Data, variables and relations

State shows the initial conditions by default; streams and parameters are shown on request. Values are edited in Resolver, through links to the exact field. Forms are not duplicated for the same datum.

- m_i and U: states determined by their balances.
- T: an algebraic variable obtained from U = m u(T), only when the manual uniform relation is declared.
- V: a fixed geometric datum, or the result of m/ρ if the constant-density hypothesis and the corresponding energy balance are active. If the relation is missing, it is shown as pending.
- P: a boundary datum when it is prescribed and used in the equations. Without an equation of state or a mechanical relation it is shown as "Sin modelo" (no model), never "Calculada" (calculated).
- T(0) or U(0): an initial condition, different from the external stream's temperature and from T(t).
- c_u, u_ref, T_ref and ρ*: parameters of the manual model. They are not calculated thermodynamic unknowns.

Variables link to the balance, relation or datum that really exists. A missing relation is shown as pending text, without a link to an equation that does not exist. The state-map view is limited to the total mass formulation; it does not label spatial fields as if they were tank states.

## Separation from thermodynamics

"Consultar propiedades" (query properties) is a separate tab. The point evaluation is kept with its own declaration and signature; it does not replace initial conditions or solver parameters. A point phase evaluation does not certify the regime during a trajectory either.

The interface could already read a water model published by the service during the visual review. Claude's physical implementation was not run or validated here. The dynamic thermodynamic closure still needs the delivery and checks of the contract [docs/history/frontend/contract-claude-thermodynamics-engine.md](../history/frontend/contract-claude-thermodynamics-engine.md).

For the future integration, the coordinator must read the boundary and its constraints from the effective formulation, and V/P from their single declarations. An independent UV/UP query must not automatically fix the V/U of the dynamic system. This delivery does not change the routes or the schema of the point evaluation.

## Verification

- `npm run test:motor-fundamental`: every suite passes; it keeps matter, couplings, multicomponent and manual energy.
- `npm run test:volumen-control`: 229 checks; units, shared geometry, matter/energy compatibility, boundary work, roles and relations, and time references.
- TypeScript and ESLint: no errors in the modified files.
- Browser: compact definition, opening/closing data, separation of the property query, and the link to the energy relation checked. The existing sheets were not edited during that visual review.

No phases, EOS, real properties, new integrators or multi-volume energy solver are added. The limits of the manual model stay explicit.
