# Current work and handoff

Last reconciled: **2026-09-24** for trading outcomes; the Research-page UX item below was checked on **2026-09-25** against `origin/main` and the running page.
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
| SS-006 | Collect five locked detector hypotheses as point-in-time research and expose their unscored confluence and graded results | User specification, 2026-09-22 | Implemented, verified and activated forward-only; collection is healthy and waiting for future closed trades |
| SS-001 | Protect established profit by moving the actual paper account stop, with a visible explanation | Repeated user request; user chose a toggle and paper/private rule parity on 2026-09-24 | Off-by-default cost-cover rule, paper stop changes, private testnet amendment, Settings control and journal history coded and scratch-tested in isolated worktree; not activated or account-proven |
| SS-002 | Correct market-specific data failures blocking the entire account | Defect verified; remediation proposed by the September 21 audit | Candidate-scoped gate coded and scratch-tested in an isolated worktree; not activated or account-proven |
| SS-003 | Align research and paper entry plans, costs and filled exposure | Defects verified; remediation proposed by the same audit | Maker price, causal ATR and actual paper fill risk coded and scratch-tested; private maker-to-market conversion still absent, now explicitly refused; not activated |
| SS-004 | Reduce and measure signal-to-order delay | Audit recommendation | Late-decision guard and recorded intent-to-route timing coded and tested; faster cycle and measured dispatch-time replay comparison remain open |
| SS-005 | Compare simpler strategy hypotheses using fixed future evidence | Pasted proposal and audit recommendation | Prospective research collector, API and Results card coded and scratch-tested in the isolated branch; no future cohort or account activation yet |
| SS-007 | Make the Research page understandable without changing research or trading rules | User request, 2026-09-25 | Merged in PR #8, restarted and verified in the running paper app on 2026-09-25; research studies remain subject to their own collection state |

### SS-007 — Research-page clarity

The running page made traders scroll through five full signal cards, several
large studies and up to 50 expanded setup records. Most statistical fields
repeated “Not gradeable” before a trader could see what was being tested.
The isolated UI change leads with the evidence verdict, uses plain
present/absent counts for each signal, and groups strategy comparisons and
setup records behind keyboard-accessible disclosures. Every original study,
method and record remains available on demand. The work changes no detector,
grading threshold, setup decision, account setting or routing behavior.
Section jumps stay on the Research route, and one unavailable study displays
an explicit failure without erasing other research. Desktop Chromium at
1440px and mobile WebKit at 390px passed 12 focused browser checks, including
research interactions, overflow and WCAG 2.1 AA, using the scratch-only
preview. The full repository gate passed 2,137 Python tests, 13 skipped and
230 subtests; its JavaScript, ESLint and source-byte checks also passed. The
JavaScript gate and focused browser checks passed again after the navigation
and failure-state correction. PR #8 merged to `origin/main` as `5d607c4` on
2026-09-25. At the user's request, the operating checkout fast-forwarded to
`8c09edd` with unrelated staged Graphify edits preserved. The guarded
`/api/system/restart?target=both` acknowledged both children with no warnings
at 16:32 ET; the watchdog respawned the server and scanner. A read-only check
found the server serving the new Research headings and section controls, the
paper read model at `paperbook-v0.7-draft`, and the scanner heartbeat at
`live-v0.17-draft`. The running Research page visibly showed the compact five
signal rows, study disclosures and setup-record disclosure. The breakout,
stop and zone studies still displayed Paused; this restart does not establish
their collection or any trading outcome. The older local work-state edit was
preserved in a stash during the fast-forward; its changed facts were already
present in main. No trading write endpoint was used for verification.

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
  checkpoint is included in that `origin/main` delivery. At the user's explicit
  request on 2026-09-24, the guarded scanner-only restart stopped the prior
  child and the watchdog respawned it at 09:52 ET. The replacement scanner's
  heartbeat advanced with `live-v0.12-draft`, and the API remained reachable;
  the original 2026-09-23 research activation boundary is unchanged.
- **2026-09-24 review correction (active):** two research defects were
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
  Research-only; no trading behaviour changed. **Activated 2026-09-24:** the
  user pulled `4b28d2a` and ran the guarded both-process restart; the served
  research read model then reported `research-observation-v0.2-draft`. That
  restart is the v0.2 activation boundary. A first attempt restarted on the
  old code because an uncommitted local work-log edit blocked the pull.
- **Current collection:** a read-only check on 2026-09-24 confirmed the v0.2
  research read model, 124 fresh Phemex OI contracts with no failed or missing
  collection attempts, and current BTCUSDT 1H order-block, sequence, hidden-
  divergence, Stoch-RSI and OI series. The five grade cohorts remain at zero
  because no qualifying setup snapshot has yet reached a closed trade under the
  new forward-only versions; this is expected collection time, not unfinished
  implementation. Exploratory variants need separately locked detector
  definitions before collection; they remain visible as uncollected and cannot
  receive a research verdict.

### SS-001 — actual profit protection

- **User intent:** after the journal showed profitable moves ending at the
  original stop, the user asked to move/protect the stop and followed up with
  "ok then do it all", "uhm, the stop loss thing?", and later asked about
  smaller-timeframe structure and defended zones. On September 21 the user
  reiterated that this had been raised several times. These establish the
  outcome; they do not resolve every later strategy parameter.
- **Prior verified reality:** `execution.monitor_paper` passed `intent.stop` to
  the fixed `execsim.walk_exit`; `tradevisuals.excursion` was retrospective.
  `stopstudy` and `zonestudy` remain separate simulations and do not adjust
  account protection. Their existing stored comparisons pause when pinned
  dependencies no longer match.
- **2026-09-24 decision:** the user wants paper and future live to share the
  rule and asked for a toggle. The isolated branch implements **Off** by
  default or **cost cover after +1R** on new bot intents. The intent pins the
  choice, so a later Settings change leaves existing trades alone. One full
  parent candle must survive; the confirmation candle must reach +1R and
  close beyond the proposed stop; missing ATR leaves the stop unchanged. A
  paper move takes effect no earlier than the next candle after the scanner
  actually observes the trigger; a late scan cannot backdate protection.
  Private custody uses the same
  candidate calculation, rounded to an exchange tick, and records a move only
  after the broker confirms the requested stop. The live router remains locked.
  Swing and defended-zone policies remain unselected research alternatives.
- **Acceptance:** the chosen rule updates actual paper protective state when
  its causal trigger occurs, never loosens a stop, records reason and effective
  time, survives restart without duplicate adjustments, and shows the active
  stop/history in the journal. Verify costs, delayed processing, adverse gaps,
  trades that later recover, and isolation from simulated study results using
  scratch stores. Runtime activation remains a separate claim to verify safely.
- **Implementation checkpoint:** `profit-protection-v0.2`, `settings-v0.3`,
  `contracts-v0.8`, `autotrader-v0.10`, `execution-core-v0.14`,
  `positions-v0.4`, `lifecycle-v0.3`, `phemex-private-v0.5` and
  `live-v0.16` are coded only in `codex/complete-open-trading-work`.
  Scratch tests cover Off, on, stop-after-trigger timing, journal history,
  delayed scanner observation, a private testnet amendment and repeated monitoring. No running scanner,
  actual paper book or private order was changed by this branch.
- **Next:** activate only through an ordinary reviewed rollout,
  and confirm an actual forward paper stop movement before closing SS-001.
- **References:** [stop comparison](FORWARD-STOP-COMPARISON.md),
  [defended-zone design](DEFENDED-ZONE-STOP-PLAN.md),
  [audit, including profit giveback](BOT-LOSS-AUDIT-2026-09-21.md).

### SS-002 through SS-005 — audit follow-up

- **2026-09-24 continuation, still isolated:** Private Phemex cancel now uses
  the venue's `clOrdID` cancel parameter (`phemex-private-v0.6`). Private
  cumulative partial fills are priced from incremental notional and fee, and
  a later fill cannot reset a tightened stop or overwrite the weighted entry
  (`execution-core-v0.15`, `positions-v0.5`). The dependent stop and zone
  studies moved to v0.5. The separate `simple-trial-v0.1` prospective ledger
  locks one primary comparison: a prior-20-bar 4H close breakout versus the
  current 4H pullback/reversal playbooks. Trend pullback/reclaim is exploratory.
  Each arm has its own $10,000 simulated book, $100 planned price risk,
  five-slot/cash limits, identical entry/exit cost model and a fixed 90-day
  window. Observation and fixed candle cutoff are recorded separately;
  no earlier setups are admitted, fills use only frozen future bars, and
  neither trial touches account routing. Its main comparison stays UNKNOWN
  until both groups have at least 30 closed trades and 8 symbols. The Results
  card shows separate long/short and net outcomes, drawdown and uncertainty.
  Focused Python checks and desktop/phone Research card browser checks passed
  with protected POSTs stubbed. The full repository gate passed after the
  three clock-test fixtures were updated for the new collector: 2,137 Python
  tests passed, 13 skipped, 230 subtests passed, then JavaScript, ESLint and
  control-byte checks passed. No running process, account, setting, private
  order or root store was changed. Commit `01afe57` was pushed to draft PR #7;
  both remote CI checks passed. The branch has not been merged or activated.

- **Remaining after this branch:** SS-004 still misses some 5-minute entry
  deadlines: read-only scanner logs show roughly 141–168 seconds preparing
  data and 126–171 seconds in priority analysis on three consecutive cycles,
  with whole cycles taking 1,000–1,291 seconds because deferred research ran
  afterward. No measured scheduling improvement has been made yet, so do not
  call SS-004 complete. SS-003's private maker-wait-to-market conversion still
  needs a durable two-leg order/cancel/reconcile state machine; the private
  route refuses such plans today. SS-005's future result cannot exist until
  a new cohort is activated and observed; passing tests is not proof of edge.

- **2026-09-24 isolated worktree checkpoint:** `codex/complete-open-trading-work`
  contains a candidate-scoped risk gate (`risk-v0.32`, `riskpaper-v0.8`),
  actual maker-limit routing and paper fill risk (`opportunity-v0.11`,
  `contracts-v0.8`, `execution-core-v0.14`, `paperbook-v0.7`), and a causal
  prior-closed-bar cross ATR (`exec-v0.30`) with its version cascade. A late
  account decision now logs a missed next-candle deadline and skips new entry
  dispatch (`live-v0.16`). The order-latency logger now reads the actual
  routed row's nested intent id and reports both intent-creation and durable
  paper-route/private-ack times; its previous top-level lookup produced no
  production records. Existing paper settlement still runs. Private
  `MAKER_THEN_MARKET` conversion is explicitly refused until implemented; this
  is a visible parity gap, not a matching live execution path. A same-size
  protective stop price change now calls the private replace path
  (`lifecycle-v0.3`); the new optional rule uses that path on testnet only
  after venue custody matches. The new rule has not been activated.
  Existing forward trials and stop studies retain their old stored dependency
  pins and will pause; newly created scratch cohorts use the new versions.
  The fixed tree passed 2,127 Python tests, 13 skipped, 230 subtests and the
  JavaScript, lint and control-byte checks. Four focused browser checks of the
  Settings toggle and actual-stop Journal detail passed at 1440px desktop and
  390px phone using a scratch-only preview with protected POSTs stubbed.
  The full gate was rerun after the observation-time fix and passed on
  2026-09-24. No live account, process, settings or route was changed.
  Verify real scan timing before closing SS-004. The isolated branch is
  committed and pushed as draft PR #7; it has not been merged or activated.

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

- **Trading application:** SS-006 itself remains research-only and does not
  alter setup score, eligibility, order plan, risk, sizing or routing. The
  separate SS-001 through SS-004 work above changes prospective trading rules
  only in an isolated worktree. No live account, setting, stop or process was
  changed by that work.
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
