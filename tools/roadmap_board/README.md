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

## Refreshing the board (Claude sessions)

1. Run `node tools/roadmap_board/build_board.mjs`. It writes `tools/roadmap_board/out/{capabilities,milestones,gates,decisions,risks}.json` (git-ignored).
2. For each changed file, upload it as an asset of the board (Artifact tool, `url` = the board, `asset: true`, `file_path` = the file), one call per JSON file.
3. Read `datasets/<id>` with ArtifactData. Then `update` its `source.url` with the new `/_blob/...` url and `source.name`, and set `updated: {at, by}`. Pin each write with `if_version` and use one batch.
4. Read `data/users/me/check` until it is no longer `checking`. No document means the page passed.
5. The page source is `tools/roadmap_board/page.html`, which the generator also packs as `out/page.json`. Change it only for layout or new sections. Then write `files/index.html` from `out/page.json`, pinned with `if_version`. The dataset ids are `capabilities`, `milestones`, `gates`, `decisions` and `risks`. Follow the dashboard type's own instructions for marks.

## Schema of `docs/engine/project-board.json`

- `milestones[]`: `id`, `track` (`m1`, `phases`, `families`, `reliability`, `cleanup`), `order` (1..n per track, no gaps), `title`, `status`, `owner` (`codex`, `claude`, `user`, `shared`), `dependsOn` (ids), `summary`, `nextAction` (empty if none), `source` (`path#heading-anchor`).
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
- `decisions[]`: `id`, `date`, `status` (`taken` or `open`), `owner`, `title`, `detail`, `source`.
- `risks[]`: `id`, `severity` (`high`, `medium`, `low`), `owner`, `title`, `mitigation`, `status` (`open` or `closed`).

A new field or status value needs the generator, the board page and this document updated together. Registry text is English. The board page translates statuses and owners for the user.
