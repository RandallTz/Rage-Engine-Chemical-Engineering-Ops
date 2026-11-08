# Codex work queue

The user asked for this queue on 30 October 2026. It lists the work for Codex and is Codex's inbox.

- **Ownership:** the coordinating Claude session keeps the queue up to date; Codex changes only the State cell of the item it works on.
- **Claude takes the queue (user decision, 7 November 2026, `dec-claude-takes-codex-queue`):** Codex has no usage, so Claude does the `repairs requested` and `ready` items too. A repair run commits code to its own `claude/*` branch, pushes that branch and sets the State to `review pending` naming the branch; a separate Claude review run merges it into `fase-a-adopcion` after review. Codex may resume any item later by the same states.
- **Use (7 November 2026, `dec-autonomous-loops`):** nobody pastes per-item prompts. Codex starts every run with the generic prompt in [Autonomous loops](../../tools/roadmap_board/README.md#autonomous-loops) and takes the first item whose state is `ready` or `repairs requested`. Claude takes the first `review pending` item. The Model column gives the tier: *Light* or *Strong (Astra)*.
- **Scope:** this file only lists pending work, at most five lines per item: what, files, acceptance command and done criterion. Status history, counts, timings and evidence go to the [roadmap](multiphysics-roadmap.md) section the item names; never here.
- **State:** each State cell starts with one token, then ` · ` and one short line: `ready`, `in progress`, `review pending`, `repairs requested`, `blocked` (name what it waits for) or `accepted`. The board check rejects any other start.
- **Removing items:** an item leaves the queue when its review is accepted. Renumber the remaining rows 1..n and update any board `waitingOn.queue` numbers in the same edit.

**Split for Demo 0.2 (updated 2 November 2026; `dec-demo02-codex-numerics` supersedes the numerical ownership in `dec-demo02-ownership`; since 5 November `dec-claude-absorbs-codex` lets the two Claude accounts take Codex's lanes, and Codex stays optional for items it claims).** The two agents never edit the same file.
- **Codex:** the common-model contract, interface and numerical networks: `core/modelo/`, `frontend/motores/`, `frontend/app/models/`, `frontend/app/motor/` presentation files, `backend/api_modelo.py`, `docs/contracts/*.md`, `core/compilador/` (network lowering, steady/dynamic assembly and assessment) and `core/solvers/` (block-sparse solving).
- **Physical authoring exception (3 November 2026, `dec-demo02-codex-physics`):** Codex may author Demo 0.2 deductions in `core/balances/` and `tests/`, through shared recorded operations from fundamental laws, with physics-based assumptions. Claude reviews later.
- **Claude:** `core/termodinamica/`, `core/reactions/`, and independent review; other physical work outside the explicit Demo 0.2 authorization remains coordinated.
- Codex uses package closures only through `core/termodinamica/derived_bridge.py` and the existing `core/compilador/derived_closure.py`. A needed thermodynamic API is recorded in the roadmap for Claude; no thermodynamic code is changed.
- Claims requiring an ownership exception name `authorizedBy: "dec-demo02-codex-numerics"`. Neither agent edits files claimed by the other.

Rules that apply to every run:

- When the item touches code: run `graphify update .` first (in a new worktree, copy the main checkout's `graphify-out/` before), and `graphify affected "<path>"` before changing each code file. Documentation-only items skip Graphify.
- Claim a board milestone before editing and release the claim when you stop.
- Never use `git add -A`; commit file by file with `git commit --only`, under `dec-standing-commit-permission` (reviewed and tested work only).
- Never touch port 8005.
- End each run with `node tools/roadmap_board/build_board.mjs --check` passing and the report "board refresh pending".

## Queue

| # | Item | Model | Unblocks | State |
|---|---|---|---|---|
| 1 | `demo-02-contract`: equipment template marker and typed ports in the common model | Strong (Astra) | Every Demo 0.2 equipment; F4 boundaries | `accepted` · RC-8 to RC-11 re-reviewed and merged into fase-a-adopcion (7 November 2026) |
| 2 | Results: list phase events of derived models; describe `package_closure` in the compilation summary | Light | Demo 0.1/0.2 presentation | `review pending` · RE-1 to RE-7 repaired on branch claude/keen-nobel-0f362b at 9851975 (RE-5 to RE-7 after the Opus review; not merged) |
| 3 | F3 slice 5 inverse specifications over HTTP, contracts, strict readers and Solve/Results | Light | F3; sizing (Demo after 0.3) | `accepted` · F3H-1 to F3H-4 and the Solve closure request merged into fase-a-adopcion (cherry-picks of 742ed66 and e6503a8, 7 November) |
| 4 | F5-C1 equilibrium-reaction constraint in Model/compiler | Strong (Astra) | F5; the reactive stage of `demo-02-column` | `repairs requested` · RA-1 (Python reader accepts Unicode digits; roadmap F5 claude-a re-review), RA-2 doc update with it |
| 5 | Steady state as a one-step Transform technique over the current dynamic selection | Light | `demo-02-steady` (UI half) | `repairs requested` · RT-9, RT-10 (roadmap Demo 0.2, re-review of the RT-6/RT-7 repairs, 7 November); RT-6 confirmed, RT-7 only repaired for masses; branch claude/steady-rt6-rt7 not merged |
| 6 | Template instances: replay a template's recorded recipe into a new connectable model | Strong (Astra) | `demo-02-drum` onward (F4) | `repairs requested` · RI-1, RI-2 (roadmap Codex queue item 6, re-review of 7 November); RI-1 first; RC-8 repaired with item 1 |
| 7 | `demo-02-stages`: one generic template, Solve count, expansion and network execution | Strong (Astra) | F4 + F3; Codex under dec-demo02-codex-numerics and dec-demo02-codex-physics | `review pending` · S8-1 repaired by claude-a on `claude/queue7-8-repairs-s8-1-rv-8` (4634f32; awaits review) · was S8-1 (Codex: `.tmp/` creation and named producers in the CSTR test and indexed verifiers); CR-2 closed; acceptance also waits for claude-b's CR-1 repair and regenerated CSTR/train numbers (claude-a review, 7 November 2026; roadmap Demo 0.2) |
| 8 | Demo 0.3 Results chart groundwork | Strong | Results; demo-03 | `review pending` · RV-8 repaired by claude-a on `claude/queue7-8-repairs-s8-1-rv-8` (4634f32; awaits review) · was RV-8 (decode lowering-cache constants once; roadmap Demo 0.2, Codex RV-4 / CR-2 repairs); spatial work deferred |

Delivery evidence, counts and timings for these items are in the roadmap (Demo 0.2, F3/F9-R8 and F5 sections). The earlier per-item prompts were removed on 7 November 2026: items 1-9 are delivered, and new work uses the generic prompt.
