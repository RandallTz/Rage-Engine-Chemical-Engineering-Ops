# Claude account mailbox

This is the standing channel between the user's two Claude accounts, **claude-a** and **claude-b** (user decision, 5 November 2026). The accounts work on different items toward the same goals, so they never share a chat. CLAUDE.md imports this file, so every Claude session reads it at start.

- **Scope:** short messages only. Examples: a request, a warning about a shared file, an API one account needs from the other, or a review result. Status, priorities and evidence stay in the [project board](project-board.json), the [roadmap](multiphysics-roadmap.md) and the Checklist. Codex uses its own [queue](codex-queue.md).
- **Writing:** add an entry under "Open" with `id` (`mb-YYYYMMDD-n`), date, from, to (`claude-a`, `claude-b` or `both`), the subject, and the message with exact paths or milestone ids. Edit only by exact replacement of your own lines, and re-read the file immediately before each edit.
- **Answering:** the recipient replies under the entry. When nothing more is needed, the recipient deletes the entry in the same edit that records the result in its canonical place. Keep the file short: no history and no closed entries.
- **Commits:** a message reaches the other account once it is on the shared branch. Commit this file by itself, by explicit path, when the user allows commits.

## Open

No open messages.
