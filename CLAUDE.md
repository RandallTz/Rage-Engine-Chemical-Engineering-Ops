@AGENTS.md

Apply [model-equation-deduction](.agents/skills/model-equation-deduction/SKILL.md) when changing Model equations, assumptions, coupling or examples. The user prioritizes the shared equation-manipulation engine. A finished formula with a descriptive flag history does not satisfy the deduction requirement. The maintained [workspace specification](docs/engine/model-workspaces.md#granular-equation-authoring) records current expression-graph scope and pending adapters.

Before resuming the Engine, read [Model workspaces](docs/engine/model-workspaces.md). The user creates models through Model → Transform → Solve → Results. This governs every future simulation; Transform includes mathematical techniques beyond nondimensionalization. All new work is in English.

Current decision (20 October 2026): consolidate nonspatial thermodynamics; spatial work is deferred. The product library was cleared and the old template loader removed. Do not reinstall examples. Create new examples only when requested, through the fundamental-law tools. New equations and assumptions extend `ModelWorksheet` and its existing right-hand panel, never another UI. Maintain the canonical documents in place.

For the independent mathematical-kernel review requested on 22 October, follow the [audit assignment and starting prompt](docs/engine/multiphysics-roadmap.md#independent-mathematical-kernel-audit). This assignment reviews the current working tree against the finite [M1 deduction-readiness and usability gates](docs/engine/multiphysics-roadmap.md#m1--minimum-usable-multiphysics-engine). Once D1 passes, prioritize Transform/Solve; exhaustive coefficient-case extensions are not a prerequisite. Its implementation scope is read-only; record reproducible findings in that existing roadmap section. Do not interpret older implementation priorities as authorization to start a parallel rewrite during this review.

## Claude on two accounts (user decision, 5 November 2026)

The user runs Claude on two accounts, **claude-a** and **claude-b**. Each account works on different board items toward the same goals; sessions are not continued across accounts. Signing in to one account hides the other's sessions, linked sessions, scheduled tasks and artifacts. Since 5 November 2026 Codex usage is limited and the two accounts take over its lanes (`dec-claude-absorbs-codex`): claude-a owns product and interface, claude-b owns physics, deduction and the compiler, as set out in the [parallel plan](docs/engine/multiphysics-roadmap.md#parallel-plan-for-the-two-claude-accounts-user-decision-5-november-2026-dec-claude-absorbs-codex). Codex stays optional for light items it claims.

- **Which account you are.** The user-level memory maps each account's email to its label. If it does not, ask the user once and record the answer there. Never write an email address in the repository.
- **Claims.** Both accounts claim as `agent: "claude"`. Start the claim `note` with your label, for example `[claude-b] ...`. The board check does not detect overlap between two Claude claims, so read every Claude claim before claiming, and never claim or edit a path that the other account's claim lists. Continue only claims labelled with your own account. Ask the user before taking over a claim labelled with the other account.
- **Messages.** Use the mailbox below to write to the other account. Read it at session start and act on entries addressed to you.

@docs/engine/claude-mailbox.md

What survives a switch, and what does not:

- **Survives (on disk):** the repository, its worktrees with uncommitted edits, the board registries, `graphify-out/`, and the memory under `~/.claude/projects/` when both accounts use the same Windows user.
- **Lost:** the chat, its task list, sessions it started, background agents, scheduled tasks and the account's artifacts. Do not rely on any of them to carry state.

Before stopping, or when the user says they will switch accounts:

1. Record the exact next step in the milestone's `nextAction`.
2. Name in the claim `note` the worktree path and branch that hold uncommitted work, if any. Do not commit unless the user asks.
3. Stop your own processes by PID.

When a session starts, on either account:

1. Run `node tools/roadmap_board/build_board.mjs --check` and read every claim whose agent is `claude`.
2. Run `git worktree list` and `git -C <path> status --short` for each `.claude/worktrees/*` entry. Uncommitted work there belongs to an earlier Claude session, possibly the other account's. Resume it only if its claim is labelled with your account; otherwise leave it and ask the user. Never discard or overwrite it.
3. Run `graphify update .` in your own checkout before relying on the graph.

**Board publishing.** The board artifact (URL in `tools/roadmap_board/README.md`) belongs to claude-a. claude-b publishes to that same URL only when the user has shared it with edit access. Never publish a second board. Without that access, update the registries, make the check pass, and report "board refresh pending", as Codex does.

## Model tiers (user decision, 5 November 2026)

Use Opus only where its reasoning is needed. Use Sonnet or Haiku for everything else.

| Work | Model | How |
|---|---|---|
| Planning, architecture, equation deduction, the independent mathematical review | Opus | Plan mode under `opusplan`, or an explicit `model: "opus"` |
| Implementation, edits, tests, board and document updates | Sonnet | The default session model (`opusplan` outside plan mode); the `implementer` agent; `model: "sonnet"` for sessions you start |
| Finding files, reading docs, graphify queries, web lookups | Haiku | The `researcher` agent, or `model: "haiku"` |

The project setting `.claude/settings.json` selects `opusplan`. A model the user picks in the app overrides it. Agent definitions are in `.claude/agents/`.
