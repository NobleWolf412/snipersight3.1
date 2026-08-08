---
name: snipersight-development
description: Safely investigate, implement, test, review, or debug changes in the SniperSight 3.1 repository, including token-conscious multi-agent architect, implementer, auditor, and contrarian workflows when explicitly requested. Use for work involving its Python engines, FastAPI server, static JavaScript cockpit, append-only fact store, algo_version cascade, live supervisor, tests, Graphify map, or Serena project memory.
---

# SniperSight development

Follow `AGENTS.md` as authority and read `CLAUDE.md` for the current operational
notebook. Do not copy either into this skill. Keep durable behavioural lessons
in the notebook; discover current layout, versions, and counts from the repo.

## Orient

1. Run `scripts/preflight.ps1` from the repository root.
2. Read the top of `graphify-out/wiki/index.md` and the relevant article before
   broad searching. Skip vendored chart-library communities.
3. Read source before claiming a cross-file flow; the graph is file-shaped.
4. Check `git status --short` and preserve unrelated changes.

## Route the work

Use one lead agent by default. Do not delegate merely because roles are
available. Treat these user phrases as explicit delegation requests:

- **Lightweight workflow** or **no subagents**: lead handles the task alone.
- **Audit this** or **independent review**: add a read-only Auditor after the
  change or against the supplied diff.
- **Competing hypotheses** or **contrarian pass**: add a read-only Contrarian
  before editing when the diagnosis is uncertain.
- **Full workflow**: Architect, one Implementer, then independent Auditor; add
  the Contrarian only when diagnosis or evidence is genuinely uncertain.

Read [references/agent-roles.md](references/agent-roles.md) before delegating.
Use the smallest requested workflow. State which roles are being used and why.
If the user did not request delegation, keep the work single-agent even when a
larger workflow might help; recommend it when risk warrants rather than silently
spending the tokens.

Maintain a single writer. Never allow two agents to edit the shared working
tree concurrently. Architect, Contrarian, and Auditor are read-only. Give each
agent a bounded question, the minimum relevant context, and a stopping rule.

## Change

1. Identify the authority for every affected value. Keep prices as `Decimal`
   and do not move calculations into the UI.
2. Treat any behaviour change as an `algo_version` bump. Inspect
   `app/tests/test_version_cascade.py` before selecting the cascade.
3. Keep facts append-only and make degraded paths audible.
4. Patch narrowly. Do not edit generated Graphify artifacts by hand.

## Verify safely

1. Never call a live write or restart endpoint for verification.
2. Inspect tests that instantiate the application. If a test opens a safety
   guard, require the protected effect to be stubbed in the same test.
3. Prefer focused tests while iterating, then run `scripts/check.ps1`.
4. After scripted edits containing escapes, require the control-byte scan in
   the check script to pass.
5. Restart the supervised app after Python changes before browser verification.
   Do not restart merely to prove a unit-level change.
6. For browser work, follow the preview limitations and shims documented in
   `CLAUDE.md`; verify canvas-derived values through instrumentation.

## Hand off

Lead with what is true now and its practical consequence. Report tests actually
run, anything not verified, version changes, live-state risk avoided, and which
delegated findings materially changed the result. Do not dump agent transcripts.
