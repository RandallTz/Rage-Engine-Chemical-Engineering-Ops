# Project board

The project board is the user's project-management view of the Engine: what is delivered, what is pending, what is deferred and why, and where the current milestone stands. It is generated from canonical registries in this repository and shown as a private claude.ai dashboard:

**Board:** https://claude.ai/artifact/To4AT4usmLkGPfmtDLTA79 (owner: the user; Claude sessions publish to it)

It applies to every agent and every session, Claude or Codex. The board never holds its own truth. If the board and a registry disagree, the registry wins and the board is refreshed.

## Sources of truth

| Registry | Owns | Updated by |
|---|---|---|
| `frontend/app/checklist/datos.ts` (`engineCapabilities`) | Every Engine capability: delivered (`available`), `pending` or `deferred`, by area | The agent that delivers or changes a capability, as AGENTS.md already requires |
| `docs/engine/project-board.json` | Milestones by track (M1 route, physical phases, family deductions, F9 reliability, cleanup), gate criteria (D1/U1), decisions and risks | The agent that changes a milestone, gate, decision or risk, in the same change |

Narrative, evidence and priorities stay in their existing canonical documents (`docs/engine/multiphysics-roadmap.md`, `ARCHITECTURE.md`, `docs/engine/model-workspaces.md`, `docs/repository-cleanup/README.md`). Each board entry links to its section through `source`. Do not copy evidence into the registry. Keep entries to one sentence that points to the section where the evidence lives.

## Before planning any new feature or change

Do this first, before writing code or a plan. The user requires it so that no new work breaks the project.

1. Run `node tools/roadmap_board/build_board.mjs --check` and read its summary: the current M1 step, open decisions and open risks.
2. Locate the request in `docs/engine/project-board.json` and the Checklist registry:
   - Name the milestone, gate criterion or capability it advances.
   - If none fits, say so to the user. Do not invent scope.
3. Check its position against current priorities:
   - If it depends on an unfinished milestone (`dependsOn`, or `blocked_by` in the generated data), say so.
   - If it falls outside M1's declared scope (the roadmap's "Outside M1" list) or into a deferred item, say so. Then follow the user's decision instead of starting it implicitly.
4. Check ownership. Codex owns M1 work. Claude owns the thermodynamics files (`core/mezclas.py`, `core/unifac.py`, `core/termodinamica/`, `core/ensamblaje_red.py`). If the change touches files owned by the other agent, coordinate through the roadmap and the user. Do not edit those files silently.
5. Check open decisions and risks that the change could hit. Example: deleting legacy code while the laboratory decision is open.

## After delivering a change

In the same change that delivers it:

1. Update `datos.ts` for any capability change: move an item between `pending` and `available`, or add one. Then run `node frontend/verificar_physical_journals.mjs --update-checklist`, as AGENTS.md requires.
2. Update `docs/engine/project-board.json` for any milestone, gate, decision or risk change, and set `reviewDate`. Keep `id`s stable. Never mark a gate criterion `passed`, or a milestone `done`, from documentation alone; it needs the evidence its source section asks for.
3. Run `node tools/roadmap_board/build_board.mjs --check`. It must pass. It validates statuses, owners, tracks, unique ids, dependencies, contiguous order and that every `source` file and heading exists.
4. Publish:
   - **Claude** publishes the board refresh (next section).
   - **Codex** cannot publish to claude.ai. After the registries pass validation, Codex states in its final summary: "Project board registries updated; board refresh pending." The user asks any Claude session to refresh it.

## Working in parallel (claims)

Claude and Codex work at the same time, and either may continue in a new chat or, for Codex, on another account. A new session starts from the board, not from memory of an earlier chat. Claims make it visible who is working on what and stop two agents from editing the same files.

1. **Look.** Run `node tools/roadmap_board/build_board.mjs --check`. Its `Claims:` line lists every active claim with its paths. The `Unclaimed active items` line lists items that are in progress but that nobody has claimed yet.
2. **Pick.** Take an item whose `owner` is you, or one the user assigns. A new session of the same agent continues that agent's own claim; for Codex this holds on either account. Do not take an item that the other agent has claimed.
3. **Claim before editing.** In the same edit that sets the milestone to `active`, add `claim: {agent, since, files, note}`. List every file or directory (ending in `/`) that the work will create or change, and keep the list narrow. The check fails when:
   - claims of different agents overlap;
   - a claim covers a path in the other agent's `ownership`;
   - a claim covers a `sharedFiles` entry;
   - a claimed milestone is not `active`.
4. **Stay inside the claim.** Edit only your claimed paths and files no one has claimed. If you need a path that the other agent claims or owns, stop and ask the user.
5. **Shared files.** Both agents edit the `sharedFiles` (this registry, the Checklist registry and snapshot, the roadmap, the workspace specification, ARCHITECTURE.md, AGENTS.md and the cleanup plan). Never claim them. Re-read them immediately before each edit and change them only by exact replacement of the lines you own. Never reformat, reorder or rewrite a whole file.
6. **Release.** When the work stops, finished or not, remove the claim in the same edit that records the result. If unfinished, write the exact next step in `nextAction`, so the next session can resume.

## Refreshing the board (Claude sessions)

1. Run `node tools/roadmap_board/build_board.mjs`. It writes `tools/roadmap_board/out/{capabilities,milestones,gates,decisions,risks,reviews,ownership,queue}.json` (git-ignored).
2. For each changed file, upload it as an asset of the board (Artifact tool, `url` = the board, `asset: true`, `file_path` = the file), one call per JSON file.
3. Read `datasets/<id>` with ArtifactData. Then `update` its `source.url` with the new `/_blob/...` url and `source.name`, and set `updated: {at, by}`. Pin each write with `if_version` and use one batch.
4. Read `data/users/me/check` until it is no longer `checking`. No document means the page passed.
5. The page source is `tools/roadmap_board/page.html`, which the generator also packs as `out/page.json`. Change it only for layout or new sections. Then write `files/index.html` from `out/page.json`, pinned with `if_version`. The dataset ids are `capabilities`, `milestones`, `gates`, `decisions`, `risks`, `reviews`, `ownership` and `queue`. Follow the dashboard type's own instructions for marks.

## Schema of `docs/engine/project-board.json`

- `milestones[]`: `id`, `track` (`demo`, `m1`, `phases`, `families`, `reliability`, `cleanup`), `order` (1..n per track, no gaps), `title`, `status`, `owner` (`codex`, `claude`, `user`, `shared`), `dependsOn` (ids), `summary`, `nextAction` (empty if none), `source` (`path#heading-anchor`).
- `status` values:
  - `done`: delivered with evidence.
  - `review`: delivered, awaiting independent verification.
  - `active`: in progress.
  - `next`: the next item to start.
  - `planned`: ordered but not started.
  - `deferred`: postponed by a decision.
  - `later`: intentionally at the end.
  - `decision`: waits on the user.
- `gates[]`: `id`, `gate` (`D1` or `U1`), `title`, `status` (`passed`, `review`, `open`), `evidence`.
- `waitingOn` (optional on a milestone that is not `done`): who it waits on now, as `[{who, queue?}]`. `who` is `codex`, `claude` or `user`. A `codex` entry may list `queue`, the item numbers of `docs/engine/codex-queue.md` that unblock it; the check validates them against that file's queue table.
- `remainingEs` (optional): one plain line, in Spanish, on what remains. It is board interface text for the user, the only Spanish field in the registry; keep the evidence in the English `nextAction` and the roadmap.
- `claim` (optional on a milestone, only while `active`): `agent` (`codex` or `claude`), `since` (YYYY-MM-DD), `files` (repository-relative paths; a directory ends in `/`), `note`. See "Working in parallel".
- `ownership` (top level): `{claude: [paths], codex: [paths]}`, the standing file ownership decided by the user. A claim may not cover the other agent's paths.
- `sharedFiles` (top level): paths that both agents edit by exact replacement and that no one claims.
- `decisions[]`: `id`, `date`, `status` (`taken` or `open`), `owner`, `title`, `detail`, `source`.
- `risks[]`: `id`, `severity` (`high`, `medium`, `low`), `owner`, `title`, `mitigation`, `status` (`open` or `closed`).

Generated datasets beyond the registry collections: `queue` (one row per numbered item of the `docs/engine/codex-queue.md` queue table), `reviews` (one row per registry with its review date: `reviewDate` here and `capabilityReviewDate` in `datos.ts`) and `ownership` (one row per `ownership` or `sharedFiles` path, with its agent). Milestone rows carry `owner_code`, the registry's owner value, and `waiting_on` (codes), `codex_queue` (item numbers) and `remaining` from the optional fields.

A new field or status value needs the generator, the board page and this document updated together. Registry text is English. The board page translates statuses and owners for the user.
