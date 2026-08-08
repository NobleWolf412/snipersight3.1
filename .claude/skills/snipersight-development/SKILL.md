---
name: snipersight-development
description: Investigate, implement, test, review, or debug changes in the SniperSight 3.1 repository, including the architect / implementer / auditor / contrarian workflow. Use for work involving its Python engines, FastAPI server, static JavaScript cockpit, append-only fact store, algo_version cascade, live supervisor, test suites, the Graphify map, or Serena project memory.
---

# SniperSight development

`CLAUDE.md` is the authority and it is already loaded — do not restate it here.
This skill is the workflow: how to orient, how to route the work across the four
roles, and how to verify without touching a live book.

## Orient

1. `git status --short` — other sessions edit this repo concurrently. Establish
   what is already in the tree before you plan against it, and never revert or
   restage a change you did not make.
2. Read the top of `graphify-out/wiki/index.md` and the one relevant article
   before broad searching. Check the header for **Stale** first. Skip the
   vendored chart-library articles.
3. Read the source before claiming a cross-file flow. The graph is file-shaped
   and will answer "where does this live" far better than "how does this work".

## Route the work

Default to a single agent. Delegate on **task shape**, not on request — the
operator asked for automatic routing on 2026-08-08 — but delegating a bounded
edit against a known authority spends context to rediscover what the lead
already has.

| Signal in the task | Role |
|---|---|
| crosses engines, moves an `algo_version`, more than one plausible home | **architect**, first |
| the cause of the symptom is still a theory | **contrarian**, before editing |
| implementation is being handed off | **implementer**, exactly one |
| facts, versions, sizing arithmetic, a safety guard, a live endpoint | **auditor**, after |

Explicit phrases still override: *lightweight* or *no subagents* keeps it
single-agent; *audit this* adds the auditor; *contrarian pass* adds the
contrarian; *full workflow* runs architect → implementer → auditor.

Sequence, when the full workflow is warranted:

1. Lead bounds the task and checks the tree.
2. Architect returns the brief.
3. Contrarian, only if the diagnosis is still uncertain.
4. Lead resolves conflicts and authorizes **one** implementer.
5. Implementer edits and runs focused tests.
6. Auditor receives the task and the diff from cold context — not the
   implementer's reasoning.
7. Lead resolves findings, runs the full gate, reports once.

Architect and contrarian may run in parallel when their questions are
independent. Never parallelize edits.

## Change

Give each delegated role a bounded question, the minimum context, and a
stopping rule. The rules that are not negotiable — `algo_version` bumps rather
than edits under an existing version, Decimal end to end, one authority per
number, audible fallbacks — are in `CLAUDE.md` and every role file repeats the
ones it can violate.

## Verify

```
cd app
python -m pytest tests -q            # the suite
npx eslint .                         # if any JavaScript changed
```

Never call `/api/manual/arm`, `/api/positions/close`, `/api/positions/adopt` or
`/api/system/restart` to verify anything. If a test forces a safety guard open,
stub what the guard protects in the same test.

Restart the supervised app after a Python change before verifying in a browser
— a running server holds the old module. Do not restart to prove a unit-level
change; the suite is enough.

## Hand off

Lead with what is true now and what it costs the operator to act on it. Report
the tests actually run, what was not verified, any version bump, and which
delegated finding changed the outcome. Do not paste agent transcripts.
