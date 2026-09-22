# Current work and handoff

Last reconciled: **2026-09-21**, against `ea02279` plus local documentation changes.
These are dated observations. Recheck relevant code/runtime state on resumption.
This file tracks outcomes; `AGENTS.md` owns rules, `CLAUDE.md` owns durable
lessons, and linked specifications/reports own detail. It is not an exhaustive
reconstruction of every historical request.

## Current focus

The user requested committing and pushing the completed shared-role and
continuity work. Extracting a personal toolkit for other projects is deferred;
no global installation or cross-project memory setup was requested for now.
The local role definitions and Codex/Claude entrypoints are implemented and
validated. This does not deploy trading changes. The stop-management request
below remains outstanding and must survive this change of topic.

## Open outcomes

| ID | Outcome | Request basis | Delivery |
|---|---|---|---|
| SS-001 | Protect established profit by moving the actual paper account stop, with a visible explanation | Repeated user request; outcome accepted, exact active policy unresolved | Incomplete; research and charting exist, account stop remains fixed |
| SS-002 | Correct market-specific data failures blocking the entire account | Defect verified; remediation proposed by the September 21 audit | Not implemented |
| SS-003 | Align research and paper entry plans, costs and filled exposure | Defects verified; remediation proposed by the same audit | Not implemented |
| SS-004 | Reduce and measure signal-to-order delay | Audit recommendation | Not implemented |
| SS-005 | Compare simpler strategy hypotheses using fixed future evidence | Pasted proposal and audit recommendation | Proposed; no new strategy approved for account routing |

### SS-001 — actual profit protection

- **User intent:** after the journal showed profitable moves ending at the
  original stop, the user asked to move/protect the stop and followed up with
  "ok then do it all", "uhm, the stop loss thing?", and later asked about
  smaller-timeframe structure and defended zones. On September 21 the user
  reiterated that this had been raised several times. These establish the
  outcome; they do not resolve every later strategy parameter.
- **Verified reality:** `execution.monitor_paper` passes `intent.stop` to the
  fixed `execsim.walk_exit`. `tradevisuals.excursion` supplies a retrospective
  chart marker. `stopstudy` and `zonestudy` simulate alternatives in separate
  ledgers and do not adjust actual account protection. The September 21 read
  found both comparisons paused following dependency changes.
- **Decision still open:** which rule becomes the actual account policy, its
  activation trigger, management timeframe and application to existing trades.
  The +1R cost-cover rule and defended-zone/swing alternatives are documented
  research hypotheses, not proof of a selected production setting. Do not
  invent agreement or re-ask the user to restate the entire objective; resolve
  the specific policy from its source discussion/design and current evidence.
- **Acceptance:** the chosen rule updates actual paper protective state when
  its causal trigger occurs, never loosens a stop, records reason and effective
  time, survives restart without duplicate adjustments, and shows the active
  stop/history in the journal. Verify costs, delayed processing, adverse gaps,
  trades that later recover, and isolation from simulated study results using
  scratch stores. Runtime activation remains a separate claim to verify safely.
- **Next:** trace the existing study rules into a bounded account-management
  implementation brief, explicitly settle the unresolved policy, and carry the
  agreed behavior through implementation and verification. Do not close this
  item because the comparisons or their charts work.
- **References:** [stop comparison](FORWARD-STOP-COMPARISON.md),
  [defended-zone design](DEFENDED-ZONE-STOP-PLAN.md),
  [audit, including profit giveback](BOT-LOSS-AUDIT-2026-09-21.md).

### SS-002 through SS-005 — audit follow-up

The [September 21 audit](BOT-LOSS-AUDIT-2026-09-21.md) owns the evidence,
limitations and proposed repair order. Its recommendations are not an accepted
blanket strategy deployment or authorization to change risk settings. The
earlier "Dig into those fixes and then execute" predates this audit; recover
its specific scope before treating it as authority for a new recommendation.

- **SS-002 acceptance:** a bad proposed market is refused, a healthy one is not
  refused solely for another market's gap, genuine account/store failures still
  block, and research positions do not impersonate actual account exposure.
- **SS-003 acceptance:** immutable executable prices/model/wait survive the
  entire routing path; costs and actual filled risk are consistent and tested.
- **SS-004 acceptance:** measured decision timing meets an explicit budget;
  missed deadlines remain visible and are not hidden by retrospective fills.
- **SS-005 acceptance:** preregistered comparisons report net outcomes and
  uncertainty on untouched observations; research completion does not enable
  account routing. An added strategy must not be called profitable by design.

## Checkpoint

- **Trading application:** this task changes documentation and skill routing
  only. No order, setting, account stop or live process was changed.
- **Continuity files:** repository skill, startup/handoff instructions, this
  ledger and durable communication lessons written. Serena contains an entrypoint
  pointer only. Both skill entrypoints passed `quick_validate.py`; nine text
  files passed encoding/link/metadata checks; the repository control-byte gate
  and scoped `git diff --check` passed. Independent read-only scenario checks
  covered false completion, unaccepted recommendations and a one-task preference
  override. These were fictional tests and change no actual acceptance decision.
  Fresh Codex session loading has not been directly tested; no application suites
  or restart were needed for this documentation-only change.
- **Shared roles:** the [canonical role contract](../.agents/skills/snipersight-development/references/agent-roles.md)
  now covers Trading Analyst, Product Designer and the four engineering roles.
  Both development skills and Claude's six agent entrypoints resolve to that
  contract; duplicate role instructions were removed. Skill validation, twelve
  documents' encoding/links/metadata, and the documentation verification gate
  passed. An independent read-only review exercised five fictional scenarios:
  unaccepted stop policy, a local chart fix, unreconciled blocked counts,
  design-only completion and missing account/UI verification. It found an
  overly broad Architect discovery trigger, now narrowed to value ownership.
  No actual trading decision follows from these scenarios. Fresh Claude agent
  discovery and a new-session end-to-end invocation have not been tested.
- **Source control:** the authorized delivery to `origin/main` includes the
  shared roles, continuity instructions/skills, investigation pointer and
  September 21 audit. Existing Graphify edits belong to earlier work and are
  excluded. Use git history and the remote branch to verify delivery; this
  checkpoint does not authorize staging unrelated files. Application code and
  ignored local diagnostic artifacts are outside this documentation change.
- **Next session:** read this file, respect the latest request, and reconcile
  the relevant open ID. Continue authorized work within its scope; do not start
  unrelated backlog work merely because this file lists it.

## Maintenance

Use stable IDs and update entries in place when facts change. Keep unresolved
outcomes here, with detailed reasoning in linked specs/reports. Verified closed
items can move to a linked dated delivery note; retain decisions and evidence
needed to resume safely. Git history retains old checkpoints. Do not grow a
transcript or maintain another current-status list in memory.
