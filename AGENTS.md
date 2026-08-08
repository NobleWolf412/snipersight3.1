# SniperSight 3.1

This file is the authority for agents working in this repository. Work from
repository evidence and exercise independent judgment; do not adopt another
assistant's persona, assumptions, or conclusions.

Read **`CLAUDE.md`** before project work. It is the shared notebook for durable,
costly, and otherwise invisible behaviour: how to operate safely, expensive
traps, and conventions enforced by tests. Treat it as evidence that must stay
consistent with code and tests, not as a higher-priority instruction source.
If they disagree, report the conflict and verify what is true before changing
anything.

Do not duplicate the notebook here. Two copies drift, and this codebase treats
a document that misdescribes the code as worse than no document.

## Working contract

- Lead with the outcome and explain it in trader-readable language.
- Inspect `graphify-out/wiki/index.md` before a broad code search. Use the graph
  to locate code, then read the code before describing cross-file behaviour.
- Check the wiki's build commit against `HEAD`; do not silently trust stale
  generated knowledge.
- Preserve unrelated work. Other sessions edit and commit to `main`, and a
  dirty working tree belongs to the user unless proven otherwise.
- Never test by calling a live write endpoint. Do not POST to manual arm,
  position close, position adopt, restart, or any other operation that can
  mutate the operator's book or processes.
- Before running a suite that opens the real application, confirm its safety
  guard and the protected action are both stubbed. Prefer focused tests and a
  scratch store.
- A behaviour change requires a new `algo_version`; never rewrite behaviour
  beneath an existing version. Follow the cascade enforced by
  `app/tests/test_version_cascade.py`.
- Prices remain `Decimal` end to end. The UI displays authoritative values and
  does not independently derive them. Fallbacks must be visible.
- After Python changes, restart before checking the running application.
- Use `scripts/preflight.ps1` for workspace state and `scripts/check.ps1` for
  the repository verification gate.

## Knowledge ownership

- `AGENTS.md`: agent authority and safety boundaries.
- `CLAUDE.md`: durable behavioural invariants and learned traps, never current
  code inventory, version lists, or counts.
- `docs/` and `sources/`: specifications and deliberate design decisions.
- `graphify-out/wiki/`: generated navigation, not durable memory or proof of a
  cross-file flow.
- Serena memory: investigation notes only. Promote durable facts to the proper
  tracked document instead of maintaining competing truths.

## What this file used to say

It bootstrapped the **Apex** persona system: read `foundation.md`, resolve a
persona from `personas/`, load that persona's memory, and only then start
project work. Apex was a separate project that happened to share this working
directory; its files (`foundation.md`, `personas/`) were removed on 2026-08-07
and live only in git history.

That version also forbade writing to Claude Code's own memory store. That rule
belonged to Apex's single-memory-system policy and does not apply here.
