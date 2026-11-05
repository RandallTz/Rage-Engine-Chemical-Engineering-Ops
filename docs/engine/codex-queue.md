# Codex work queue

The user asked for this queue on 30 October 2026, while Codex was unavailable. It lists the work for Codex.

- **Ownership:** the coordinating Claude session keeps the queue up to date.
- **Use:** Claude hands over the prompts in queue order when the user says Codex is available. Each prompt carries its model level: *light model* or *strong model (Astra)*.
- **Scope:** this file only lists pending work. Status, evidence and priorities remain in the [board](project-board.json), the [roadmap](multiphysics-roadmap.md) and the Checklist.
- **Removing items:** an item leaves the queue when Codex delivers it and its review is accepted.

**History.** Under `dec-claude-demo01-takeover` (30 October 2026), Claude did the Demo 0.1 items. They were reviewed and committed: the derived-execution bridge, the F5-C4 liquid-only admission and the declared-relation functions in 3214490; the interface remnants in 577f3a6; the contract copy in 190fe15. Demo 0.1 is tagged `demo-0.1`.

**Split for Demo 0.2 (updated 2 November 2026; `dec-demo02-codex-numerics` supersedes the numerical ownership in `dec-demo02-ownership`).** The two agents never edit the same file.
- **Codex:** the common-model contract, interface and numerical networks: `core/modelo/`, `frontend/motores/`, `frontend/app/models/`, `frontend/app/motor/` presentation files, `backend/api_modelo.py`, `docs/contracts/*.md`, `core/compilador/` (network lowering, steady/dynamic assembly and assessment) and `core/solvers/` (block-sparse solving).
- **Physical authoring exception (3 November 2026, `dec-demo02-codex-physics`):** Codex may author Demo 0.2 deductions in `core/balances/` and `tests/`, through shared recorded operations from fundamental laws, with physics-based assumptions. Claude reviews later.
- **Claude:** `core/termodinamica/`, `core/reactions/`, and independent review; other physical work outside the explicit Demo 0.2 authorization remains coordinated.
- Codex uses package closures only through `core/termodinamica/derived_bridge.py` and the existing `core/compilador/derived_closure.py`. A needed thermodynamic API is recorded in the roadmap for Claude; no thermodynamic code is changed.
- Claims requiring an ownership exception name `authorizedBy: "dec-demo02-codex-numerics"`. Neither agent edits files claimed by the other.

Rules that apply to every prompt:

- Run `graphify update .` first, and `graphify affected "<path>"` before changing each file.
- Claim a board milestone before editing and release the claim when you stop.
- Never use `git add -A`; commit only file by file with `git commit --only`, and only when the prompt says so.
- Never touch port 8005.
- End each run with `node tools/roadmap_board/build_board.mjs --check` passing and the report "board refresh pending".

Commit preparation (2 November 2026): the cleanup README closure plan classifies all 70 current status entries into disjoint proposed groups, with five local/unresolved entries held. No staging or commit; Claude groups and mixed hunks require confirmation.

## Queue

| # | Item | Model | Unblocks | State |
|---|---|---|---|---|
| 1 | `demo-02-contract`: equipment template marker and typed ports in the common model | Strong (Astra) | Every Demo 0.2 equipment; F4 boundaries | Delivered by Codex 1 November 2026; reviewed (approve with repairs), repaired in item 7; re-check pending |
| 2 | Results: list phase events of derived models; describe `package_closure` in the compilation summary | Light | Demo 0.1/0.2 presentation | Delivered by Codex 1 November 2026; reviewed (approve with repairs), repaired in item 7; re-check pending |
| 3 | F3 slice 5 inverse specifications over HTTP, contracts, strict readers and Solve/Results | Light | F3; sizing (Demo after 0.3) | Delivered by Codex 1 November 2026: common steady HTTP, strict TS contracts/readers and existing Solve/Results; 4 HTTP tests and 83 TS/lifecycle/rendering checks; reverified 2 November 2026 after RT repairs; review pending |
| 4 | F5-C1 equilibrium-reaction constraint in Model/compiler | Strong (Astra) | F5; the reactive stage of `demo-02-column` | Delivered 5 November 2026 for certified ideal-gas index-one extent blocks; 29 focused tests and 26 client checks pass; independent review repairs F1-F6 delivered for re-review; liquid/thermal/steady integration remains pending |
| 5 | Steady state as a one-step Transform technique over the current dynamic selection | Light | `demo-02-steady` (UI half) | RT-1..RT-4 repaired by Codex 2 November 2026; 7 Python tests and 38 TS checks pass; headless production-client HTTP acceptance passed 2 November: 25 checks across both drums, including phase events and dynamic/steady agreement; review pending |
| 6 | Template instances: replay a template's recorded recipe into a new connectable model | Strong (Astra) | `demo-02-drum` onward (F4) | Delivered by Codex 1 November 2026; independent review pending |
| 7 | Repairs RC-1 to RC-7 from the independent review of items 1-2 | Light | Commit of items 1-2; `demo-02-drum` (RC-3) | Repaired by Codex (1 November 2026); review pending |
| 8 | `demo-02-stages`: one generic template, Solve count, expansion and network execution | Strong (Astra) | F4 + F3; Codex under dec-demo02-codex-numerics and dec-demo02-codex-physics | Contract/Solve expansion delivered (6 Python tests, 46 TS checks, prior 35 HTTP checks). Recorded discharge recipe version 2 delivered; six indexed lowering tests pass (135.49 s), including chemical-identity alignment. Four dynamic cases n=1,2,3,5 pass (7598.11 s), with RK45/BDF conservation/certificates and direct DOP853 references for n=1,2,3. The n=2 default steady probe converges; steady/long-time acceptance passes n=1,2,3 (129.798/220.594/521.738 s, including n=3 dense/sparse); n=5 now passes with bounded Jacobian stencils and increasing-count continuation using identity-verified prior-stage seeds (1 passed, 9 deselected, 2291.03 s; 2 focused continuation/stencil tests pass). Its root matches the 6000 s BDF limit and passes conservation and every closure certificate. Indexed publication v2 supports interior side ports (5 Python tests, 50 Node checks, TypeScript). Actual connected dynamic/steady publication now passes 2 Python cases and 60 Node checks with T-versus-j chart acceptance. Versioned aggregate compilation and explicit-selection HTTP transport now pass 3 ASGI tests (152.57 s, n=2 dynamic 1 s/steady plus rejections). Workspace persistence/controls delivered: 31 headless checks and 41 full live HTTP app-flow checks n=2/3 (6000 s BDF/steady, events, certificates and T_j charts; 381.241/617.249 s). Generic replay/compiled-plan reuse has 30 affected regression passes, a repaired exact cold-replay receipt check and n=5..40 timings; all 10 long-time drum regressions after reuse pass (9326.64 s); CSTR/train n=1,2,3,5 acceptance is delivered (6 long tests plus jacket regression, 57 live HTTP checks, 30 affected regressions; 5 November 2026), with independent review pending; unselected requests retain the guard. Review pending CR-2 repaired 5 November: unequal or unresolved discharge/receiving pressures reject before solving; re-review pending. |

| 9 | Demo 0.3 Results chart groundwork | Strong | Results; demo-03 | Delivered 2 November 2026; 137 chart checks and 30 fresh-result HTTP checks; optional versioned layout, shared Python units, events and overlays; review pending; spatial work deferred RV-4 repaired 5 November: float.hex() instance keys and signed-zero/adjacent-float regression; re-review pending. |

Items 1 and 2 were delivered on 1 November 2026 and are under independent review (session "Review Codex template contract, ports and events"). Item 3: Claude's canonical readers and Codex's HTTP/TS/Solve/Results integration are delivered; independent review is pending (F3 fifth-slice section). Item 4 remains blocked by the 2 November user instruction until Claude supplies the Jacobian-bounds API below; do not implement it merely because compiler claims are free.

Physical continuation (3 November 2026, dec-demo02-codex-physics): Codex has recorded discharge component and enthalpy transport through SharedAuthor and regenerated the drum recipe as template version 2. Five indexed-runtime tests pass (72.31 s), with both expected failures removed; the initial four-state RHS is unchanged. Dynamic network acceptance passes four n=1,2,3,5 cases (7598.11 s), including RK45/BDF conservation/certificates and direct DOP853 references for n=1,2,3. Momentum/drum regressions cover eight passing cases: seven original passes plus the repaired nonzero-flow-condition assertion (1 targeted pass, 688.14 s). Steady Transform, HTTP publication and generic symbolic reuse remain Codex work. Claude reviews the physical deduction later; thermodynamics and reactions remain Claude-owned. Historical counts below describe earlier deliveries.

Numerical delivery (3 November 2026; review pending): F3 sparse Newton/BDF covers admitted explicit derived and forward steady systems, independently of the drum recipe. Shared-authored thermal chains n=5,10,20,40 solve with dense/sparse agreement and default seeds; 95 affected regression tests and 12 steady tests pass. The internal indexed runtime is prepared against recorded discharge component fluxes and enthalpy: two tests pass, two narrowly scoped expected failures remain until Claude supplies the physical deduction. No indexed HTTP route or physical relations are authored here. Final counts, timings and limitations remain in roadmap F3/F9-R8.

Symbolic-preparation continuation (3 November 2026; in progress): baseline cProfile for n=5,10,20,40 is recorded in roadmap F3/F9-R8. Candidate exact replay, exact-assumption proofs and alpha-normalized numerical AST caches have 73 passing mathematical/cache/publication tests; repaired numerical subset passes 44 with 2 expected failures. Profile tables and fitted exponents are recorded. Policy v2 keeps automatic dense because no reproducible sparse crossover is established; explicit sparse remains. The final combined numerical run passes 134 tests with 2 expected failures (669.93 s); the final cache suite passes 10 tests. Generic-stage symbolic reuse remains pending, with exact next work recorded in roadmap F3. Indexed publication contract/readers are delivered separately; indexed execution is not. That historical regression run predates the recorded discharge delivery: both physical-transport expected-failure marks have since been removed and the indexed lowering tests pass.

## Prompts

### Long stretch: items 1 → 2 → 3 (strong model, Astra)

```
You are Codex working on the reactive-distillation simulator at C:\Users\randa\Desktop\reactive_distillation, branch fase-a-adopcion (pushed; Demo 0.1 is tagged demo-0.1).

Before anything:
- Read AGENTS.md, ARCHITECTURE.md §12, docs/engine/model-workspaces.md and the "Demo 0.2" section of docs/engine/multiphysics-roadmap.md, including the user decisions of 1 November 2026: everything is deduced dynamic with matter, energy and momentum; steady state is a Transform of the dynamic model; equipment templates are marked; ports are typed and connectable but never wired in the Model view; assumptions describe physics, not equipment.
- Read docs/engine/codex-queue.md ("Split for Demo 0.2"). You own the contract and the interface. Claude is working at the same time on core/compilador/{derived,derived_closure,steady,hydraulics}.py, core/balances/ and core/termodinamica/. Never edit those files; if you need a change there, record the need in the roadmap and continue with the next step.
- Run `$HOME/.local/bin/graphify update .` (or `graphify update .`), then `node tools/roadmap_board/build_board.mjs --check`.

Work through the three steps below in order. For each step:
- claim its board milestone with the exact files, set it active, and release the claim when the step ends;
- update the existing canonical documents in place (roadmap, contracts, Checklist registry frontend/app/checklist/datos.ts, and the snapshot via `node frontend/verificar_physical_journals.mjs --update-checklist`);
- write all new code, identifiers and UI text in English;
- persisted keys need explicit optional versioning; never rename existing keys.
Do not commit; report each step's files and checks so the user can approve the commits.

STEP 1 — demo-02-contract (board milestone demo-02-contract; advances F4)
Add to the common model an optional, versioned template record. It must hold:
(a) template identity and version;
(b) an equipment marker (true only for templates that represent a real piece of equipment);
(c) the replayable recipe reference: the recorded journals that produce the deduction, never a final formula;
(d) typed ports.
A port names an open boundary stream of a volume (desde or hasta null) or a heat/work boundary term. It has:
- a direction (inlet/outlet);
- a kind (material, heat, work);
- for a material outlet, the donor phase it draws, if any;
- for a material inlet, the exterior state it requires;
- the stream variables a future flowsheet connects (flow, composition, T, P, specific enthalpy) with SI units.
Ports describe connectability only; nothing connects them in this view.

Implement in four layers:
1. Python reader: core/modelo/lector.py strict, unknown keys rejected, consistency checks: every port references an existing open stream or term; an equipment marker requires at least one port.
2. TypeScript contract and reader: frontend/motores/modelo/contrato.ts and lector.ts, with the same rules.
3. Contract text: docs/contracts/common-model.md.
4. Display: the library shows an "Equipment" badge, and the existing right-hand panel of ModelWorksheet lists the ports read-only. Reuse ModelAssumptions.tsx; no new page or editor.

Check that existing models without the record are unchanged (all readers, verificar_physical_journals.mjs, verificar_model_derivations.mjs, npm run test:motor-fundamental). Test acceptance and every rejection in Python and TS. Leave the Demo 0.1 fixtures unmarked: they are regression fixtures, and the first equipment template arrives with demo-02-drum.

STEP 2 — queue item 2 (light): derived-model events and package-closure summary
Use the prompt text of item 2 below. Check with node frontend/verificar_demo01_models.mjs, verificar_physical_journals.mjs and the repository TypeScript check.

STEP 3 — queue item 3 (light): F3 slice 5 over HTTP and UI
Use the prompt text of item 3 below. The backend kernels are core/solvers/inverse_spec.py and inverse_steady.py (51c2b9b). Use backend/api_modelo.py for the route. Do not edit core/compilador/steady.py; if it needs a change, record it for Claude.

End: one report per step (files, checks with counts, open findings). The board check must pass. Then say "board refresh pending".
```

### 2. Derived-model phase events and package-closure summary (light model)

```
Two presentation gaps found while running the Demo 0.1 models in the app (docs/engine/multiphysics-roadmap.md, "Demo 0.1 release"). (1) The Results workspace for derived models does not list result events: show the published aparicion_fase / desaparicion_fase events (time, description, propietarioId "volumen:<id>") in the existing Results view, for example as a list in Numerical diagnostics and as markers on the time charts; reuse the existing event presentation of the assembly views, no new page. (2) frontend/app/models/CompilationSummary.tsx describes closureStrategy "package_closure" with the generic "declared thermodynamic assumptions" sentence; describe it as the selected package closing each volume's UV/PH state at every RHS evaluation through the derived-execution bridge, using report.derivedExecution.thermodynamicClosures (contract: docs/contracts/common-model.md "Package closures in derived execution"). Display only; no protocol change. Check with node frontend/verificar_demo01_models.mjs, verificar_physical_journals.mjs and the repository TypeScript check. Follow the common rules in docs/engine/codex-queue.md.
```

### 3. F3 slice 5 over HTTP and UI (light model)

```
Expose the committed F3 slice-5 inverse specifications (core/solvers/inverse_spec.py, inverse_steady.py; 51c2b9b) over the common steady HTTP route, the versioned contracts, the strict result readers and the existing Solve/Results controls, as listed in the "F3 fifth slice" section of docs/engine/multiphysics-roadmap.md. The Python steady readers already accept it: follow the exact shape in the "Steady readers done (Claude, 1 November 2026)" paragraph and round-trip through core.compilador.steady.read_result. No new UI: extend the existing Solve controls. Tests and verifiers for each layer. Follow the common rules in docs/engine/codex-queue.md.
```

### 4. F5-C1 equilibrium constraint (strong model, Astra)

**Review repairs delivered, 5 November 2026.** F1 is explicitly documented as an IdealGasPhase provider closure; F2 caloric inconsistency blocks thermal coupling. F2b adaptive extent bisection certifies every leaf with full-box coverage. F3 moves virtual nonzero displacement to a Model domain premise. F4/F5/F6 repair canonical rational parsing, error paths and the R diagnostic. 29 focused tests and 26 client checks pass; see roadmap F5 for scope and regression evidence.

**Original delivery for independent review, 5 November 2026.** Optional version-1 common-model declarations, recorded Gibbs virtual-variation deductions, public certified affinity bounds and outward-rounded extent-block proof now admit the IdealGasPhase version-4 DAE path. 20 focused Python tests, 68 combined workbench/DAE regression tests and 22 production-client checks pass; repository TypeScript and journal/derivation audits pass. Liquid packages remain a located `PROVIDER_UNSUPPORTED` in this compiler increment, and coupled thermal/network equilibrium and steady composition remain explicit extensions. Evidence and exact scope are in roadmap F5. The historical API request below is retained for review.

**Blocked API handoff (Codex confirmed, 2 November 2026).** No implementation is authorized in this increment. Claude owns the missing provider API in `core/reactions/`; no change there or in `core/termodinamica/` was made.

Confirmed differences from the proposed compiler interface:
- `evaluate_reactions(provider, nu, *, T, P, n, phase_id, standard_state)` uses **reaction rows and species columns**, in provider species order, products positive. Model stoichiometry columns must be transposed once at the boundary. SI: T K, P Pa, n mol, mu J/mol, dimensionless g = nu @ mu/(R*T). It evaluates the supplied inventory; it neither equilibrates nor clips it.
- `provider` is `PackagePhase(sistema,tipo,anchor=...)` or `IdealGasPhase`. Provider phase/formation anchor determines the standard state: vapor `ideal_gas_P0`, liquid `pure_liquid_TP`; these are checked values, not arbitrary labels. Liquid-only species require a liquid-only system and liquid anchor. The record must pin species order, package/pure-data/formation-reference fingerprints and the phase/anchor/standard-state choice.
- `certify_reactions(state, *, tolerances=None, n0=None, A=None)` requires n0 and element matrix A to certify conservation; it recomputes mu. Affinity residuals, conservation and phase stability are separate from Newton convergence. Liquid-only stability does not certify vapour stability.
- mu and partial molar h/u already include formation references: total-energy assembly must not add reaction heat again. `dmu_dn` and temperature derivatives are finite differences. They are point evaluations, not certified bounds. At the original handoff, `kinetic_rates` and `reaction_jacobian_bounds` were not delivered. The latter is now delivered; the scoped compiler integration below supersedes that blocker.

Required callable (requested contract, not a claim that it exists):

```python
reaction_jacobian_bounds(provider, nu, box, *, phase_id, standard_state) -> dict
```

`nu` retains the evaluator reaction-row order. `box` is exactly `{"T":[Tlo,Thi],"P":[Plo,Phi],"n":[[nlo_i,nhi_i],...]}` in SI and provider species order. Endpoints must be finite, ordered, T/P strictly positive, and every n lower bound strictly positive; singleton intervals are allowed. A box crossing a phase/package/formation-reference validity boundary is not certified. No activity clipping, flash, equilibrium projection or sampled-grid estimate may masquerade as an enclosure.

The requested result is versioned `{"format":"rage.reaction-jacobian-bounds","version":1,"certified":bool,"species":[CAS...],"nu":[rows...],"phase_id":...,"standard_state":...,"anchor":...,"box":...,"fingerprints":{"package":str,"pureData":str,"formationReference":str},"bounds":object|null,"proof":object|null,"diagnostics":[{"code":str,"path":str,"message":str}]}`. Certified `bounds` contains `g` (r pairs), `dg_dn` (r by species pairs, 1/mol), `dg_dT` (r pairs, 1/K) and `dg_dP` (r pairs, 1/Pa). Every pair encloses the exact provider value over the **whole box**, with documented outward rounding and validity assumptions in `proof:{method,rounding,assumptions}`. `dg_dT` includes differentiating 1/(R*T), not just dmu/dT. Unavailable, nonfinite or uncertifiable bounds return certified false, null bounds/proof and located diagnostics; malformed dimensions/order/standard state reject explicitly.

Compiler use after delivery: for the independent stoichiometric columns N and n=n_ref+N*xi, compose dg/dxi=(dg/dn)*N with outward-rounded interval arithmetic and prove the algebraic block nonsingular over the declared domain. Dependent reactions remain certificate checks. A point Jacobian, finite differences, successful solve_extents or agreement with minimise_gibbs cannot establish index-one admission over that domain. First provider scope may be smooth ideal gas with explicit unsupported diagnostics for other providers; it must not silently downgrade a real-package request. Claude should test enclosure containment and conservative rejection, including trace inventories, against independent ideal-gas analytic derivatives. F5-C1 tests against minimise_gibbs and solve_extents now pass (5 November 2026); whole-box interval nonsingularity, not those point comparisons, gates admission.


```
Implement F5-C1 from the F5 section of docs/engine/multiphysics-roadmap.md: an equilibrium-reaction constraint g_j = nu_j^T mu/RT = 0 that calls core.reactions.chemical_equilibrium.evaluate_reactions (accepted, 355ac28), with the anchor/standard-state choice exposed as a recorded assumption and the extents admitted as unknowns. First confirm the API differences recorded there. Tests against minimise_gibbs and solve_extents. Follow the common rules in docs/engine/codex-queue.md.
```

### Second stretch: items 5 → 6 (strong model, Astra)

```
You are Codex on the reactive-distillation simulator (C:\Users\randa\Desktop\reactive_distillation, branch fase-a-adopcion). Continue Demo 0.2 inside your own files only, as set out in docs/engine/codex-queue.md, "Split for Demo 0.2".
- Yours: core/modelo/, frontend/motores/, frontend/app/models/, presentation files of frontend/app/motor/, backend/api_modelo.py and the contracts.
- Never edit core/compilador/, core/balances/, core/termodinamica/ or core/solvers/. Claude sessions are working there now (demo-02-momentum and the F3 steady readers). If a step needs a change there, record it in the roadmap and continue.

Your steps 1–2 (template record, ports and events) are uncommitted and under independent Claude review. Leave those files as they are unless a step below needs them. Fix any review finding only after the user hands it to you.

Before starting:
- Run graphify update . and graphify affected "<path>" per file.
- Run node tools/roadmap_board/build_board.mjs --check.
- Claim the board milestone named in each step with its exact files, and release the claim at the end of the step.
- Update the canonical documents in place: the roadmap Demo 0.2 section, docs/engine/model-workspaces.md, the contracts, and the Checklist registry plus its snapshot (node frontend/verificar_physical_journals.mjs --update-checklist).
- Write everything in English and do not commit.

STEP A — queue item 5 (board: demo-02-steady, UI half; advances F3)
The user's rule: steady state is never a separate deduction. It is the same dynamic deduced model with every accumulation rate set to zero.
- Today a steady derived selection (version 5) exists, but the user has to build it by hand in Transform.
- Add a Transform technique, "Steady state (zero accumulation)", to the existing Transform workspace (DerivedExecution.tsx / derivedSelection.ts). No new page or editor.
- In one step it produces the version-5 selection from the current dynamic selection:
  - the same original derivative rows, specialised at zero rate;
  - the same data, with initial values offered as the Newton seeds;
  - explicit invariants where the dynamic model has dependent totals.
- Show before/after in the existing Transform handoff. Changing the dynamic selection invalidates the steady one.
- Solve and Results already handle version 5 (DerivedSolve.tsx).
- Volumes with a package thermodynamic closure are not yet admitted by the steady backend; Claude does that in demo-02-steady. For those volumes, show the backend's structured rejection as returned. Do not filter it or work around it.
- Test on an existing steady-capable fixture (the F3 steady suites and verificar_steady_state.mjs) and on the Demo 0.1 reactor, where it must report the package-closure rejection.

STEP B — queue item 6 (board: demo-02-contract follow-up; advances F4)
- A template is a recorded, parameterised deduction replayed for each instance; it is never a pasted formula.
- Add "New instance from this template" for any model that carries the template record you added in step 1. It works from the existing model page or library row; it does not bundle templates into the library and does not add a template loader.
- The new instance:
  - replays the recorded journals and workbench operations through the existing replay services (Python is the source of truth; the client does not calculate);
  - gets fresh model, volume and stream identities, with port identities remapped consistently;
  - copies the declared data as editable defaults;
  - keeps the template identity, version and equipment marker in provenance.
- The instance must reproduce the source deduction exactly: same equation signatures modulo the identity map, same results on the Demo 0.1 fixtures once they are marked in a test copy. Leave the committed fixtures unmarked.
- Reject a template whose recipe no longer replays (a stale journal) with a located error. Never fall back silently.
- Ports stay unconnected.

End: per step, report files, checks with counts and open findings; the board check must pass. Then say "board refresh pending".
```

### 7. Review repairs RC-1 to RC-7 (light model)

```
Repair the findings of the independent review of your demo-02-contract and events work. The review is recorded in the Demo 0.2 section of docs/engine/multiphysics-roadmap.md, bullet "Independent review of Codex demo-02-contract and events". Stay inside your own files (codex-queue.md, "Split for Demo 0.2").

- RC-1: make tests/test_template_record.py run under pytest (put the corpus loop in a test_ function); pytest must report the cases.
- RC-2: in both readers, require every journal named in the recipe to be a non-null object; a null journal is a located reader error, never a plain Error.
- RC-3: dec-demo02-dynamic-first requires matter, energy and momentum. Add a gate: equipment:true needs materialDerivation, energyDerivation, momentumDerivation (and thermodynamicDerivation when a volume has a package closure) in the recipe. Apply it identically in both readers, plus the library or audit display. Update the corpus, whose valid equipment case lacks momentum.
- RC-4: make the TS common stream reader check estadoExterior and extraccion the way Python does, so the port rules are identical. Keep existing valid documents unchanged.
- RC-5: in verificar_template_record.mjs, assert the reader error class (ErrorModelo), not any exception.
- RC-6: keep the event marker labels inside the chart area. The label at t = 127 s on a 3000 s axis is clipped today; check it in a 1280 px viewport.
- RC-7: document in the contract, or constrain in both readers, two things: integer versions (Python rejects 1.0) and the direction rules for heat/work ports.

Rerun the checks from your report: test_template_record under pytest, verificar_template_record, verificar_demo01_models, verificar_physical_journals, npm run test:motor-fundamental, and tsc. Then append "Repaired by Codex (date)" to the review bullet. Do not commit. The board check must pass; then say "board refresh pending".
```
