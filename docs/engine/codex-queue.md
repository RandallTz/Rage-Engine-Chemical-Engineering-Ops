# Codex work queue

The user asked for this queue on 30 October 2026, while Codex is unavailable. It lists the work waiting for Codex.

- **Ownership:** the coordinating Claude session keeps the queue up to date.
- **Use:** when the user says Codex is available again, Claude hands over the prompts in queue order. Each prompt carries its model level: *light model* or *strong model (Astra)*.
- **Scope:** this file only lists pending work. Status, evidence and priorities remain in the [board](project-board.json), the [roadmap](multiphysics-roadmap.md) and the Checklist.
- **Removing items:** an item leaves the queue when Codex delivers it and its review is accepted.

**Takeover (user decision, 30 October 2026, `dec-claude-demo01-takeover`).** While Codex is unavailable, Claude sessions did the Demo 0.1 items. The derived-execution bridge, the F5-C4 liquid-only admission and the declared-relation functions were reviewed and committed by Claude on 31 October 2026 (3214490; detail in the roadmap F4 and F5 sections), so they left the queue. Codex keeps ownership of its paths; a Claude session edits them only for queued items, under a board claim with the exact files, and adds a "Done by Claude" line to the item so Codex can resume. Items 2–3 stay with Codex.

Rules that apply to every prompt:

- Run `graphify update .` first, and `graphify affected "<path>"` before changing each file.
- Claim a board milestone before editing and release the claim when you stop.
- Never use `git add -A`; commit only file by file with `git commit --only`, and only when the prompt says so.
- Never touch port 8005.
- End each run with `node tools/roadmap_board/build_board.mjs --check` passing and the report "board refresh pending".

## Queue

| # | Item | Model | Unblocks | State |
|---|---|---|---|---|
| 1 | Clear the four non-blocking Spanish remnants of the interface | Light | `demo-01-release` (polish) | Done by Claude 31 October 2026 and committed (577f3a6) except two deferred items (see below) |
| 2 | F3 slice 5 inverse specifications over HTTP, contracts, strict readers and Solve/Results | Light | F3 | Waiting for Codex; the backend is committed in 51c2b9b |
| 3 | F5-C1 equilibrium-reaction constraint in Model/compiler | Strong (Astra) | F5 (simultaneous chemical and phase equilibrium) | Waiting for Codex |
| 4 | Results: list phase events of derived models; describe `package_closure` in the compilation summary | Light | `demo-01-release` (polish, not blocking) | Waiting for Codex |

## Prompts

### 1. Interface remnants (light model)

```
The demo-01-ui translation is committed (97629e8). Translate the four non-blocking Spanish remnants recorded in the roadmap "Demo 0.1 visible interface review" paragraph: the aria-label in EcuacionesEnsambladas.tsx, the /motor error boundary (app/motor/error.tsx), \text{sin restricción} in the EnergiaFundamental.tsx LaTeX, and decide with the user whether the unlinked /adimensionalizacion studio is translated or retired. Display text only; no key, value, route or protocol name renamed. Run the fundamental verifier suite. Follow the common rules in docs/engine/codex-queue.md.
```

**Done by Claude (31 October 2026; committed in 577f3a6).** The `EcuacionesEnsambladas.tsx` aria-label and the `/motor` error boundary (`app/motor/error.tsx`) are translated; ESLint and `npm run test:motor-fundamental` pass. Left on purpose: `	ext{sin restricción}` (and `	ext{en }`, `	ext{pendiente}`) in `EnergiaFundamental.tsx` are the content of a recorded energy-journal operation, not display text, so changing them alters new histories; translate them at display or under a versioned migration. The unlinked `/adimensionalizacion` studio stays as it is: the user decided on 31 October 2026 to leave it for later.

The former stale-verifier item was done by Claude and committed in 190fe15: only the docs copy `docs/contratos/contratoEnsamblajeV2.ts` was stale.

### 2. F3 slice 5 over HTTP and UI (light model)

```
Expose the committed F3 slice-5 inverse specifications (core/solvers/inverse_spec.py, inverse_steady.py; 51c2b9b) over the common steady HTTP route, the versioned contracts, the strict result readers and the existing Solve/Results controls, as listed in the "F3 fifth slice" section of docs/engine/multiphysics-roadmap.md (reader gap = finding 1). No new UI: extend the existing Solve controls. Tests and verifiers for each layer. Follow the common rules in docs/engine/codex-queue.md.
```

### 3. F5-C1 equilibrium constraint (strong model, Astra)

```
Implement F5-C1 from the F5 section of docs/engine/multiphysics-roadmap.md: an equilibrium-reaction constraint g_j = nu_j^T mu/RT = 0 that calls core.reactions.chemical_equilibrium.evaluate_reactions (accepted, 355ac28), with the anchor/standard-state choice exposed as a recorded assumption and the extents admitted as unknowns. First confirm the API differences recorded there. Tests against minimise_gibbs and solve_extents. Follow the common rules in docs/engine/codex-queue.md.
```

### 4. Derived-model phase events and package-closure summary (light model)

```
Two presentation gaps found while running the Demo 0.1 models in the app (docs/engine/multiphysics-roadmap.md, "Demo 0.1 release"). (1) The Results workspace for derived models does not list result events: show the published aparicion_fase / desaparicion_fase events (time, description, propietarioId "volumen:<id>") in the existing Results view, for example as a list in Numerical diagnostics and as markers on the time charts; reuse the existing event presentation of the assembly views, no new page. (2) frontend/app/models/CompilationSummary.tsx describes closureStrategy "package_closure" with the generic "declared thermodynamic assumptions" sentence; describe it as the selected package closing each volume's UV/PH state at every RHS evaluation through the derived-execution bridge, using report.derivedExecution.thermodynamicClosures (contract: docs/contracts/common-model.md "Package closures in derived execution"). Display only; no protocol change. Check with node frontend/verificar_demo01_models.mjs, verificar_physical_journals.mjs and the repository TypeScript check. Follow the common rules in docs/engine/codex-queue.md.
```
