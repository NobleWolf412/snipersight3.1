---
name: snipersight-continuity
description: "Preserve SniperSight user intent, decisions and unfinished outcomes across sessions. Use when resuming project work, reconciling a repeated request or correction, updating project memory, or preparing a handoff. Keeps research, implementation and active behavior distinct."
---

# SniperSight continuity

Keep the next session able to answer: what did the user ask for, what actually
works, what remains, and what evidence would establish completion? This skill
maintains context; it does not expand the current task or authorize deployment.

## Resume from evidence

1. Read root `AGENTS.md`, `CLAUDE.md` and `docs/WORK-STATE.md`. Follow the
   development skill for code inspection and safety; do not rerun its full
   orientation if already done in this session.
2. Match the current request to the relevant work ID. Compare its last-reviewed
   date/commit with HEAD and relevant dirty files. Read only the linked decisions
   and source needed to check it. Treat stored state as a lead, not proof.
3. Distinguish a new objective from a question, correction or reminder about an
   existing one. Preserve unfinished outcomes when the user changes topic;
   pursue the latest authorized scope, not the whole backlog.
4. On "I already asked" or an equivalent correction, find the earlier intent
   before asking again. Compare the observable user journey with what was
   delivered. Recover the actual choice if recorded; leave an unresolved
   parameter explicit if it was only proposed. Never turn a bare "go" detached
   from its context into standing permission for future actions.

## Store each fact once

| Information | Owner |
|---|---|
| Agent authority, safety and required startup/handoff steps | `AGENTS.md` |
| Explicit stable communication/product preferences and costly durable lessons | `CLAUDE.md` |
| Current commitments, delivery gaps, pending decisions and next action | `docs/WORK-STATE.md` |
| Detailed design, rationale, dated measurements and acceptance evidence | Relevant `docs/` or `sources/` document |
| Investigation breadcrumbs or a pointer to those tracked owners | Project Serena memory, if available |

Do not maintain another current-status list in model memory, Serena or a second
assistant's notebook. The Claude continuity skill is a pointer to this file.
If memory tooling is unavailable, the tracked files still provide the handoff.
Do not claim that file edits update built-in ChatGPT/Codex memory or guarantee
recall in every client. Avoid secrets, private account details and full chat
transcripts in shared instructions.

Promote an explicit stable preference or a repeated, evidenced failure that
changes future decisions. Label an inference until confirmed. A one-off request
is not automatically a global rule. Replace superseded guidance at its owner;
do not append contradictory rules. Mention material corrections to the user.

## Keep an honest work item

Update the existing ID instead of creating a duplicate. Record only fields
that matter for that outcome:

- Requested behavior and its source: dated decision, user wording with context,
  or linked specification. Identify recommendations as proposals.
- Current delivery and evidence: code/test/report reference plus review date
  and commit. Separate source implementation, tested behavior and running
  activation; mark unknowns explicitly. Distinguish paper, research and live.
- Remaining acceptance conditions, unresolved decisions and concrete next step.
- Commit/push/restart status when needed for the next session to observe the
  same build. Read git/runtime evidence before asserting it.

For a research-only request, verified research may complete the outcome. For
active behavior, a plan, passing unit tests or a simulated chart is only partial
evidence. Completion requires the requested behavior in its intended context;
use safe verification paths rather than live write tests. Do not activate an
experiment solely to make its status say complete.

## Checkpoint without building a second job

Update after a material decision, correction, verified milestone, or before
handoff/end of substantial work. Capture a changed commitment promptly rather
than relying on a graceful end to the session. No update is needed when nothing
durable or task-relevant changed; do not add a ledger item for every small edit.

Re-read the affected shared section immediately before patching. Preserve other
sessions' IDs and changes, and resolve conflicting evidence explicitly. Keep
the startup ledger short: open outcomes and current handoff, with detail linked
out. When it grows unwieldy, move verified closed outcomes to a dated delivery
note with evidence and supersession links. Do not discard unresolved work or
purge history to tidy the page; git already retains prior checkpoints.

End with what was accomplished in this request and any material remaining gap.
Updating continuity may be complete while the product work it records remains
open. No scheduled automation, commit, push or account change is implied by
maintaining the handoff. Keep authority changes narrow and justified by the
user's request; ordinary task notes should not modify `AGENTS.md`.
