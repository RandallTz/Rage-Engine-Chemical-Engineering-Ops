# Codex work queue

The user asked for this queue on 30 October 2026. It lists the work for Codex and is Codex's inbox.

- **Ownership:** the coordinating Claude session keeps the queue up to date; Codex changes only the State cell of the item it works on.
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

- Run `graphify update .` first, and `graphify affected "<path>"` before changing each file.
- Claim a board milestone before editing and release the claim when you stop.
- Never use `git add -A`; commit file by file with `git commit --only`, under `dec-standing-commit-permission` (reviewed and tested work only).
- Never touch port 8005.
- End each run with `node tools/roadmap_board/build_board.mjs --check` passing and the report "board refresh pending".

## Queue

| # | Item | Model | Unblocks | State |
|---|---|---|---|---|
| 1 | `demo-02-contract`: equipment template marker and typed ports in the common model | Strong (Astra) | Every Demo 0.2 equipment; F4 boundaries | `review pending` · re-check of the item 7 repairs |
| 2 | Results: list phase events of derived models; describe `package_closure` in the compilation summary | Light | Demo 0.1/0.2 presentation | `review pending` · re-check of the item 7 repairs |
| 3 | F3 slice 5 inverse specifications over HTTP, contracts, strict readers and Solve/Results | Light | F3; sizing (Demo after 0.3) | `review pending` · independent review (roadmap F3 fifth slice) |
| 4 | F5-C1 equilibrium-reaction constraint in Model/compiler | Strong (Astra) | F5; the reactive stage of `demo-02-column` | `review pending` · re-review of repairs F1-F6; liquid/thermal/steady integration is roadmap F5 work |
| 5 | Steady state as a one-step Transform technique over the current dynamic selection | Light | `demo-02-steady` (UI half) | `review pending` · independent review of RT-1..RT-4 |
| 6 | Template instances: replay a template's recorded recipe into a new connectable model | Strong (Astra) | `demo-02-drum` onward (F4) | `review pending` · independent review |
| 7 | Repairs RC-1 to RC-7 from the independent review of items 1-2 | Light | Commit of items 1-2; `demo-02-drum` (RC-3) | `review pending` · independent review |
| 8 | `demo-02-stages`: one generic template, Solve count, expansion and network execution | Strong (Astra) | F4 + F3; Codex under dec-demo02-codex-numerics and dec-demo02-codex-physics | `review pending` · CSTR/train acceptance review and CR-2 re-review (evidence: roadmap F3/F9-R8 and Demo 0.2) |
| 9 | Demo 0.3 Results chart groundwork | Strong | Results; demo-03 | `review pending` · RV-4 re-review; spatial work deferred |

Delivery evidence, counts and timings for these items are in the roadmap (Demo 0.2, F3/F9-R8 and F5 sections). The earlier per-item prompts were removed on 7 November 2026: items 1-9 are delivered, and new work uses the generic prompt.
