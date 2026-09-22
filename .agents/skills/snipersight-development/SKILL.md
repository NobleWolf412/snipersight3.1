---
name: snipersight-development
description: Investigate, design, implement, test or review SniperSight 3.1 trading behavior and its UI. Use the shared Trading Analyst, Product Designer and engineering roles when relevant, with bounded delegation for broad, risky or uncertain work. Applies to this repository, not general trading advice.
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
5. Read `docs/WORK-STATE.md`; follow the repository continuity contract and
   [continuity skill](../snipersight-continuity/SKILL.md) for relevant unfinished
   outcomes, user corrections and handoffs.

## Route the work

Default to one agent. For substantive trading, product-design or engineering
work, read the shared rules and relevant sections of the canonical
[role contract](references/agent-roles.md). It owns role selection, evidence
requirements and completion criteria for both Codex and Claude.

Apply a role's questions directly for bounded work. Delegate on task shape
when work is broad, risky or uncertain and independent scrutiny adds value;
this is the operator's requested routing, not a requirement to run every role.
"No subagents" keeps work local; "contrarian pass" selects Contrarian;
"full workflow" uses Architect → one Implementer → Auditor, with trading or
design input only where needed. An unavailable independent review stays an
explicit gap, not a claim that switching roles supplied it.

State which delegated roles are used and why. Give each a bounded question,
the canonical contract path and relevant role name, the original requested
outcome, necessary evidence and a stopping rule. Keep exactly one writer:
the Lead or Implementer. All other delegated roles are read-only. The Lead
reconciles findings and updates the shared work ledger.

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
Reconcile the relevant work item before claiming completion; name any remaining
activation or verification gap in the requested user journey.
