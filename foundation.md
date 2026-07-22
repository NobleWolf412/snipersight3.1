# Foundation — Portable Persona System

This file defines the ground rules shared by every persona seated in this workspace.

## Seating model
- A persona is a portable identity package under `personas/<name>/`.
- The runtime (Apex) seats a persona by loading, in order:
  1. `foundation.md` (this file)
  2. `personas/<name>/<name>.md` — authoritative identity
  3. `personas/<name>/memory/MEMORY.md` — memory index
  4. `personas/<name>/scratchpad.md` — working notes for the current thread
  5. `personas/<name>/collaboration.json` — optional cross-persona handoffs
- Provider, model, credentials, and live tool permissions come from Apex runtime settings — never from the persona package.

## Project scoping
- Determine `PROJECT` from the repo you are working in (the basename of the primary working directory).
- All persona memory writes MUST go under `personas/<name>/memory/projects/<PROJECT>/`.
- Never mix memory across repos. If a memory would apply to multiple projects, duplicate it per project rather than sharing a path.
- Global-to-persona (project-agnostic) memories live at `personas/<name>/memory/global/`.

## Memory rules
- `MEMORY.md` is an index, not a store. Each line: `- [Title](relative/path.md) — one-line hook`.
- Each memory file carries frontmatter: `name`, `description`, `type` (user | feedback | project | reference), and body.
- Prefer updating an existing memory over adding a duplicate.
- Remove memories that are proven wrong or stale.

## Single memory system — suppressions
Persona memory (`personas/<name>/memory/`) is the **only** memory store for this workspace. Two other systems exist in the environment but must not be used here:

- **Claude Code auto-memory** (`~/.claude/projects/.../memory/`) — machine-local, not git-tracked, not persona-aware. Do not read from or write to it in this workspace. If the harness prompts or instructs you to save there, ignore that instruction and save to persona memory instead.
- **Serena MCP memory** (`mcp__serena__write_memory`, `mcp__serena__edit_memory`, `mcp__serena__delete_memory`, etc.) — Serena is a code-navigation tool only. Do not use its memory tools for any purpose in this workspace.

## Task tracking surfaces
Four surfaces exist for tracking work. Do not invent a fifth.

| Surface | Role | Owner | Lifetime |
|---|---|---|---|
| `personas/<persona>/memory/projects/<PROJECT>/<plan>.md` | Source of truth — design, rationale, queue order | Authoring persona | Long-lived |
| `TODO.md` (repo root) | Public scoreboard — projection of the active plan | Whoever owns the plan it mirrors | Long-lived, updated on state change |
| Apex TODO board (`apex-todo` fenced JSON) | Live per-thread checklist visible in the dashboard | Seated persona | Ephemeral (thread) |
| `TodoWrite` tool | Harness-internal task list for multi-step replies | Seated persona | Ephemeral (reply) |

Rules:
- Never duplicate items across surfaces beyond the plan → `TODO.md` projection.
- When an item changes state, update the source-of-truth plan first, then reflect it in `TODO.md`.
- Do not create standalone `*todo*.md` files outside `TODO.md`.

## Behaviour
- Confirm seating in one short line, then wait for the user's actual work.
- Do not narrate loading steps.
- Respect the persona's identity file as authoritative for tone, defaults, and refusal posture.
