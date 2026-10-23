# One system, three balances

Each sheet is a system with a single ID, a component catalog, topology, data and results. The library shows systems; the three animated panels are inside each sheet. (Since 18 October 2026 there is a fourth, always-present panel, Thermodynamics: [docs/contracts/thermodynamic-layer.md](../contracts/thermodynamic-layer.md) §4 bis.)

- `vistaBalance` controls only which equations are viewed and the green, red or blue accent. It does not create sheets or change the calculation's signature.
- `balances` controls which families take part in the solution. Its switches are independent of the view. Changing the selection invalidates the result's reference, keeping data, components, steps, streams and charts.
- Matter keeps its current derivations, coupling and solver. Energy has its own breakdown, stored in `energia.historial`, with the local equation, Gauss, Reynolds, ports and assumptions. Its first solver accepts one volume and one component, transient, with a manual u(T) relation; the requirements and limits are in [docs/engine/energy-foundation.md](energy-foundation.md). Momentum keeps its fundamental view in `supuestosBalances` and is not run yet. An active family is never silently skipped if its formulation is not supported.
- Old sheets inherit matter active, energy and momentum inactive. Their signature and results do not change. The old category routes redirect to the common library.
- The selection applies to the sheet's whole system (including its coupled volumes). It does not add different selections per volume. Matter and energy share [m,U] in the first energy scope; several volumes with energy are still pending.

The lab and the backend are not modified. The energy assumptions applied and the terms run are recorded in the result's traceability. The phase remains assumed without thermodynamic verification. Momentum continues as a symbolic reference.

Verification: `npm run test:motor-fundamental`, TypeScript, ESLint and visual navigation of one sheet among the three balances. `verificar_seleccion_balances.mjs` checks the eight possible selections in every example, compilation and solution guards, persistence, data preservation and numerical equivalence for matter.
