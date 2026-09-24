# Current work and handoff

Last reconciled: **2026-09-23**, against `ecd475d` plus local implementation changes.
These are dated observations. Recheck relevant code/runtime state on resumption.
This file tracks outcomes; `AGENTS.md` owns rules, `CLAUDE.md` owns durable
lessons, and linked specifications/reports own detail. It is not an exhaustive
reconstruction of every historical request.

## Current focus

The user requested research-only indicator collection and UI integration across
Setups, Trade, Results/Signals and Phemex data health. The source implementation
is present and the independent audit findings have been remediated. Full Python,
JavaScript and focused desktop/mobile browser contracts pass; the repository
wrapper was also attempted and its remaining failures were isolated to sandbox
temp-directory/process-visibility restrictions. The supervised scanner and API
were restarted at 2026-09-23 08:21 ET, establishing the forward-only research
activation boundary. This does not authorize a detector to affect setup
qualification or activate a production strategy. The older
stop-management outcome below remains outstanding and must survive this work.

## Open outcomes

| ID | Outcome | Request basis | Delivery |
|---|---|---|---|
| SS-006 | Collect five locked detector hypotheses as point-in-time research and expose their unscored confluence and graded results | User specification, 2026-09-22 | Implemented, verified and activated forward-only under the supervised scanner; first post-activation collection cycle pending |
| SS-001 | Protect established profit by moving the actual paper account stop, with a visible explanation | Repeated user request; outcome accepted, exact active policy unresolved | Incomplete; research and charting exist, account stop remains fixed |
| SS-002 | Correct market-specific data failures blocking the entire account | Defect verified; remediation proposed by the September 21 audit | Not implemented |
| SS-003 | Align research and paper entry plans, costs and filled exposure | Defects verified; remediation proposed by the same audit | Not implemented |
| SS-004 | Reduce and measure signal-to-order delay | Audit recommendation | Not implemented |
| SS-005 | Compare simpler strategy hypotheses using fixed future evidence | Pasted proposal and audit recommendation | Proposed; no new strategy approved for account routing |

### SS-006 — indicator research and signal map

- **Locked primary hypotheses:** direction-matched `LAST_OPPOSITE_BEFORE_BREAK`
  order blocks overlapping the originating 3.1 zone; ordered and linked sweep →
  break → block; direction-aligned Stoch RSI 20/80 exit within three closed
  setup-timeframe candles; trend-aligned hidden RSI divergence within ten closed
  candles; and Phemex perpetual price plus open interest expanding together over
  one hour in the trade direction. Listed alternatives remain exploratory.
- **Versions:** `order-block-v0.1-draft`, `structure-sequence-v0.1-draft`,
  `stoch-rsi-v0.1-draft`, `hidden-divergence-v0.1-draft`,
  `open-interest-signal-v0.1-draft`, immutable setup snapshots under
  `research-snapshot-v0.1-draft`, and evidence under
  `research-evidence-v0.1-draft`.
- **Research contract:** each primary exposed and control cohort needs at least
  **30 closed trades and 8 symbol clusters**. Below either floor is `UNKNOWN`.
  Observations and grades are research-only: they do not change score,
  eligibility, order plan, risk, sizing or routing. Confluence/alignment is not
  confidence, missing open interest is not zero, and exploratory variants can
  never be labelled Proven useful.
- **Current delivery:** additive OI collection uses the scanner's fixed
  `observed_at` and performs network I/O only after account routing; detectors
  write versioned facts after the trading phase; setup
  detail returns an immutable confirmation-time snapshot; current chart reads
  remain separate; Setups, Trade, Signals, Research chart layers and Phemex
  health/Diagnostics consume server-owned values. Same-candle sweep/break events
  are explicitly unordered, and the primary sequence control contains only
  unordered/unlinked components. Exploratory definitions remain honestly marked
  `EXPLORATORY_UNCOLLECTED`; no unspecified variant is presented as evidence.
  A post-activation UI correction keeps the price chart as the sole opening and
  navigation range authority: sparse new OI readings can no longer zoom the
  main chart to a few giant candles, while the Stoch RSI and OI panes follow
  price-chart pans and scaling. The corrected Research preset was verified in
  the running app and in desktop Chromium plus 390px WebKit; the focused chart
  contracts passed 7 Python, 23 JavaScript and 4 browser tests. A subsequent
  live check found that BTCUSDT 1H was returning 32 order blocks, but the exact
  regions rendered only 3–5 pixels wide with a faint dashed boundary. Order
  blocks now retain their authoritative price/time bounds while using a solid,
  higher-contrast boundary and explicit `OB ↑` / `OB ↓` labels. Three in-range
  blocks were visibly confirmed in the running chart, and the focused order-
  block regression passed 7 Python contracts plus desktop Chromium and 390px
  WebKit. The follow-up live layer audit confirmed 122 regular and 81 hidden
  divergence series, 5,636 Stoch RSI points with K/D and 20/80 levels, and 49
  current OI points with observation time/value/change. It also found that all
  32 BTCUSDT 1H structure records were partial (no sweep), so the renderer drew
  none while reporting 32. Partial records now render only the known
  `B→OB · partial` relationship, explicitly explain that no sweep was recorded,
  and filter old markers outside the loaded candle window; three live in-range
  markers were confirmed. A deterministic missing-OI fixture remains a blank
  gap. The revised rendering contract passed 7 Python checks plus desktop
  Chromium and 390px WebKit, with scoped syntax and lint clean.
  Full Python contracts passed 2,114 tests plus 230 subtests (one skipped), all
  39 JavaScript contract files passed, and focused Playwright setup/signal-map
  coverage passed at 1440px Chromium and 390px WebKit. The exact final detector,
  migration, Phemex and UI contract selection passed 86 tests plus 11 subtests;
  scoped JavaScript syntax/lint and `git diff --check` also passed. The final
  `scripts/check.ps1` attempt reached 1,993 passing tests plus 230 subtests but
  could not complete because the managed sandbox denied pytest's default temp
  directory (120 collection/setup errors) and hid the watchdog child process
  (one unrelated failure). The same suite passed with a repository-local
  `--basetemp`. No live write endpoint was called during implementation or
  verification.
- **Activation/status:** at the user's explicit request, the guarded
  `/api/system/restart` operation restarted both supervised children at
  2026-09-23 08:21 ET. The replacement scanner entered its live loop and the
  replacement API served the new Signals and Phemex OI contracts. This is the
  forward-only activation boundary; older setups remain unbackfilled. Before
  the first new cycle completed, OI status correctly reported `MISSING` with
  no zero substitute and Signals reported `Data unavailable`. The user
  authorized committing and pushing this implementation on 2026-09-23; this
  checkpoint is included in that `origin/main` delivery.
- **2026-09-24 review correction (not yet active):** two research defects were
  fixed after review. (1) The sweep → break → block exposure had no link to the
  setup: one complete sequence anywhere in a series marked every later setup on
  it exposed. It now links through the setup's originating zone, like the
  order-block hypothesis, and judges order on the break's real confirmation
  rather than the activation-floored one. (2) OI signals were confirmed at the
  scan's opening clock although fetched minutes later, so a setup confirmed at
  a mid-scan candle close could read them. They are now confirmed at
  collection. Versions: `structure-sequence-v0.2-draft`,
  `open-interest-signal-v0.2-draft`, `research-observation-v0.2-draft`,
  `research-snapshot-v0.2-draft`, `research-evidence-v0.2-draft`,
  `chart-insight-v0.3-draft`. v0.1 snapshots are not re-read or rebuilt, so
  setups from the first activation stay unavailable; the new versions start a
  fresh forward-only boundary **only after the supervised scanner restarts**.
  Research-only; no trading behaviour changed.
- **Remaining:** confirm the first completed post-activation scan persisted OI
  and detector observations. Exploratory variants need separately locked
  detector definitions before collection; they remain visible as uncollected
  and cannot receive a research verdict.

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

- **Trading application:** SS-006 adds research collection, read models, APIs and
  UI only. It does not alter setup score, eligibility, order plan, risk, sizing
  or routing. No order, setting, account stop or live process was changed.
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
