---
name: model-equation-deduction
description: Refine the reactive_distillation Engine's Model equation deduction, assumptions, coupling or examples. Use when changing how physical equations are obtained or handed to Transform/Solve; examples must exercise shared authoring operations.
---

# Model equation deduction

The product is a mathematical modeling engine. The user's priority is extending its authoring capabilities, not delivering a finished example by embedding its equations. Apply this skill to this repository's Model work and examples.

Read the repository's AGENTS.md, ARCHITECTURE.md and the maintained contracts/workspace specification before editing. Use Model → Transform → Solve → Results; identify inputs, outputs, consumers and invalidation. Update canonical documentation in place.

## Acceptance rule

Start from fundamental laws. Apply independently recorded assumptions and mathematical operations. If the required operation is missing, implement it in the shared engine and restart/replay the deduction. Missing capability is a finding, never permission to append a terminal formula, precomputed model or decorative history.

Fundamental laws, mathematical identities, definitions and empirical constitutive relations may be declared with their proper provenance. Distinguish these roots from results actually derived by the engine. A constitutive choice does not follow from conservation alone. Geometry or solver configuration must not inject an undeclared equation.

## Authoring and coupling

- Operate on equation/expression identities: select inputs, substitute a relation, isolate a variable, integrate, differentiate, combine equations, impose an explicit condition or change a declared dependency. Preserve before/after expressions, rule, conditions, branches, units and provenance. A boolean journal next to a fixed formula is insufficient.
- Separate conservation equations, definitions, constitutive relations, boundary/initial conditions and assumptions. Coupling shares symbol identities and explicit relations; it is not a new equipment template.
- Support multiple equations of a family. Component balances are indexed by component identity; a total mass balance is derived by summing component mass balances. Explain dependent totals and avoid counting redundant rows as extra independent equations or unknowns. Do not equate a total molar balance with total mass conservation.
- Keep mathematical indices generic and stable. Physical names and later display aliases do not determine equations. Renaming labels must not change physics or translate persisted keys.
- Domains, components and equations must be editable through shared tools. A list of example-specific volumes is not an equation authoring system.
- Keep the canonical Model worksheet: equations on the left, operations/assumptions on the right. Add capabilities to its shared controls and rows, not another editor or example frontend. Python owns algebra, units and numerical evaluation.
- Show unreduced fundamental laws first, their actual mathematical development next, and the derived model distinctly at the end. Never default to final equations while hiding their roots behind a current/all toggle. Keep optional expression tools separate from physical assumptions.
- Viewing history, changing the selected domain, selecting equations or expanding provenance is read-only with respect to physics. Never wire a view selector to a physical journal rewind. Use explicit reversible Undo/Redo actions for physical changes. An invalid downstream operation must leave the source equations visible, retain saved history and block unsupported execution; never erase the worksheet or silently substitute a partial model.

## Handoff and evidence

Transform and Solve consume the exact selected derived system. An unsupported edit must produce a capability diagnostic; it must never fall back to the earlier prescribed equations. Invalidate dependent formulations and runs when equation meaning changes. Keep dynamic conservation laws when adding permanent zero-rate constraints.

Verify more than the requested numerical example: change an assumption, remove a closure, combine a different equation set, undo an operation and rename an index. Confirm that the expression graph changes appropriately, incomplete derivations remain incomplete, and unsupported execution is blocked. Compare mathematics with an independent reference. Do not treat plausible curves, a readable history, passing snapshots or a renamed static formula as proof of a modeling engine.

State the implemented scope precisely. Never claim all families use the operation engine when only one path does. Record remaining engine findings in the existing roadmap and Checklist.
