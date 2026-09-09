# SniperSight: from signal scanner to context-aware trading assistant

Review and first implementation pass, 5 September 2026.
Source baseline: `da4e13b` on `main`. The generated wiki was older; conclusions
below follow the actual engine, server and tests, not its inventory.

## The verdict

The app has substantial analytical machinery, but not yet the integrated
decision system the operator is asking for. It can describe much more than it
currently uses to choose trades. Adding a more articulate model alone would
make its explanations more convincing without necessarily improving decisions.

The priority is to connect trustworthy observations, distinguish hypotheses
from rules that have earned deployment, and measure the entire trade lifecycle.
The first changes below fix concrete evidence and simulation defects. They do
not claim to establish a profitable strategy.

## What exists, and what actually affects trading

| Capability | Source evidence | Current boundary |
| --- | --- | --- |
| Chart structure and regime | `chartread.py`, `regimeread.py`, `regime.py` | Fast window read, structural labels and impulse/turn/drift phases exist. These are different views, not interchangeable labels. |
| Top-down analysis | `bias.py`, `htfread.py`, `setups.py` | Multi-rung bias and entry-time context are recorded. The current bias, pullback-context and chart-window policies allow every configured case. Most new observations do not refuse entries. |
| Indicators | `ma.py`, `momentum.py`, `volatility.py`, `volume.py` | Moving averages, RSI/MACD, volatility and volume evidence exist. An event's recorded value is not necessarily the indicator's latest value. Their presence is not proof of an edge. |
| Playbook choice | `setups.py`, `registry.py`, `pipeline.py` | The enabled book mainly selects pullback/reversal from structural rules. Trend and breakout candidates are separately measured, not an autonomous strategy allocator. |
| Macro | `stockcalendar.py`, `basis.py`, `cycles.py`; new `macro_calendar.py` | The review found no economic-calendar integration. This pass adds official scheduled-event awareness; a rates/dollar model and broad cross-asset regime feed are still missing. |
| Risk | `risk.py`, `sidegovernor.py` | Deterministic sizing, position/open-risk caps, daily loss protection and a same-side loss governor exist. These must remain outside a language model's discretion. |
| Exit management | `execsim.py`, `manual.py`, `trailexit.py`, `abtest.py` | The engine's active simulated exits are fixed stop/target plus timeout. Operator-managed trailing exists separately. Alternative automatic exits are research, not an enabled adaptive policy. |
| AI analyst | `copilot.py`, `/api/copilot` | Chart chat uses the local Claude CLI; the sampled-screen Spotter reviewer uses Codex separately. Astra running in this development task does not install Astra into either product path. |

The earlier UI critique remains useful, but it is not a current bug list. The
product should become a decision surface, not a longer diagnostics page:
**what matters, why it matters, what is allowed now, and what would change that.**

## Implemented in this pass

### 1. Give the analyst the chart evidence the app already computes

New `analyst_context.py` produces versioned, read-only evidence at one closed-bar
cutoff. It includes weekly-to-requested-timeframe chart readings, phase context,
data age, dated indicator events, and the most recent scanner quality verdict
available at that cutoff. Stale/missing charts cannot produce a current
top-down call. Candles closing after the cutoff are excluded.

The chart chat now receives that evidence alongside the setup's separately
labelled **entry-time** chart/context, authoritative bracket, risk decision,
costs and positions. Resumed conversations rebuild their pack and resolve the
position again rather than continuing indefinitely from the first question's
market state. This spends more input context per follow-up in exchange for
current evidence.

Removed two misleading instructions: that the system has no RSI/MACD, and a
hard-coded historical strategy-performance claim. Missing macro feeds and
unsupplied statistical grades are explicitly unknown, not neutral or negative.
The scheduled `strategy_regrades` record exists, but this pass does not promote
it into a current setup-specific grade: its population/version provenance and
freshness need an explicit contract first.

The analyst is instructed to explain the top-down thesis, local confirmation,
invalidation and strongest reason to wait. Trailing or stop changes remain
unexecuted scenarios. Tool access and all trade-management authority remain
disabled in this chat path.

### 2. Repair the trailing-exit measurement before trusting it

Reproduced a concrete failure in the research simulator with a zero-cost
synthetic long: entry 100, original stop 90, distant target 200; one bar trades
high 130 and low 80. The old trail path raised the stop using 130 before testing
the original protection, and reported **+2.5R** on an ambiguous bar that must
conservatively count as **-1R**. The short-side mirror has the same failure.

`abtest-v0.4` checks existing protection before a closed bar can ratchet it for
the next bar. A later opening gap through a managed stop fills at the adverse
open, not an unreachable stop price. Long/short tests pin both rules. Trail-only
reports now include the replay version.

This is a **closed-bar trailing policy**, not a model of a continuously updated
exchange-native trailing order. Lower-timeframe or tick sequencing is needed
to assess the latter. Costs still use the shared execution settlement code.
The active fixed-bracket engine and its fact versions are unchanged.

Earlier managed/trailing measurements require a new replay before being used
to justify a decision. The defect does not establish whether trailing is good
or bad, and it is not evidence that this defect caused the active paper book's
losses: that book does not use this managed-exit path.

### Corrected replay result

**The 5 September figures in this section were withdrawn on 7 September.** They
were produced by `abtest-v0.4`, which applied a gapped-stop fill to the managed
cells and not to the hold cell they were compared against — a bias inside the
paired delta, against trailing. See "Correcting the exit fill" below. The table
that follows replaces them.

Ran `python -m engine.trailexit --json` read-only on 7 September. These are
historical **trend candidate replays**, not the active paper account's executed
trades. Setup `trend-v0.3-draft`, replay `abtest-v0.5` on `exec-v0.26-draft`,
recorded maker-then-market entry model:

| Comparison | Closed replays | Mean net R | Symbol-clustered interval |
| --- | ---: | ---: | ---: |
| Fixed stop/target | 14,050 | -0.2898 | [-0.3212, -0.2578] |
| Trail only | 14,074 | -0.2651 | [-0.2864, -0.2436] |
| Paired trail-minus-hold | 14,050 | **+0.0232** | **[+0.0005, +0.0457]** |

115 symbol clusters; 24 trades resolved in only one variant and were excluded
from the paired delta. The store has grown since 5 September, so this is a
larger sample as well as a corrected convention.

**The verdict is still NOT_PROVEN, and the reason has changed — read this
before quoting the delta.** The paired interval now sits just above zero, where
before it crossed. That is not permission to trail. The floor requires *both*
that the delta clear zero AND that the trail cell's own interval clear zero,
and the trail cell is **-0.2651 with an interval entirely below zero**. What
the corrected number says is that trailing improves a losing playbook by about
two basis points of R, with the lower bound five ten-thousandths above nothing.
That is not an edge; it is a losing cohort losing marginally less.

Two further limits, unchanged: this is not a chronological holdout, and
`trailexit` does not call `calibrate()`, so this replay has not been certified
against the recorded book. That certification is currently impossible — the
`exec-v0.26-draft` re-simulation has not run yet — and it must be re-run and
checked before this number is used for anything.

### Correcting the exit fill

`abtest-v0.4` above had the rule on one side. The fix was not to make the two
cells match, because the two ways of matching them are not equivalent:

| Convention | trail - hold | Interval |
| --- | ---: | --- |
| v0.4 as measured: fill on managed only | +0.0208 | [-0.0012, +0.0425] |
| Fill on **both** (`exec-v0.26-draft`) | +0.0232 | [+0.0005, +0.0457] |
| Fill on **neither** | +0.0670 | [+0.0431, +0.0896] |

Removing the fill from both cells nearly triples the apparent trail edge,
because a trailed stop sits close to price and gaps through on 15.6% of
settlements against 1.5% for an untouched stop. Two-thirds of that version of
the "edge" would have been the fill convention.

So the rule moved into the engine instead. A stop the market gapped through now
fills at the bar's open rather than at a price that never traded —
`execsim.stop_gap_fill`, `exec-v0.26-draft`, cascading to risk / scale /
cooldown. A resting take-profit limit gapped past still fills at its own price,
because that order was in the book at that level; the invariant is one-sided.

Cost to the recorded paper book: **one trade of 605 stop-outs** (TRUMP-USD 15m
REVERSAL, -1.53 R restating to about -1.83 R), **-0.297 R gross across 903
facts** as counted on 7 September. The book must be re-simulated under the new version before any of it
reads as current.

### 3. Official economic-event awareness, visible in the app

The continuation adds `macro-calendar-v0.1-draft`, an informational calendar
read from fixed official Federal Reserve and BLS URLs. Overview now has an
Economic events panel with expandable sources, observation times, coverage
failures and upcoming dates. The chart analyst receives the same evidence on
every turn (`analyst-context-v0.2-draft`). Its starter questions now invite
top-down analysis, event awareness and playbook reasoning.

Runtime verification: the Federal Reserve feed returned the September 15–16,
2026 meeting dates; BLS returned HTTP 403. The app therefore says **Calendar
incomplete**, not "no events". The BLS connector is implemented and tested
offline, but its successful live ingestion is **not verified**. No blocked
source was bypassed, no dates hard-coded as a live fallback, and no paid feed
or new credentials were installed.

Feeds are cached in memory for six hours, with a one-day stale threshold and
bounded public requests. Failure retains old observation times and labels
the source degraded/stale rather than updating its age. The Fed source gives
meeting days, not an exact release time; the app preserves that distinction.
BLS release times are parsed with Eastern-time daylight saving rules.

This is a calendar, not a directional macro model. Actual releases, consensus,
surprises, rates/dollar data, cross-asset breadth and historical vintages remain
absent. An event window is informational and never alters risk, sizing, entry
permission or the active strategy set. Cache state does not persist across an
API restart and must not be used as a historical backtest source.

## The system to build next

### A. A sourced market brief, not a macro story invented by chat

Build a timestamped observation layer for:

- Scheduled event risk: FOMC decisions, CPI and employment releases.
- Slow context: policy rates, yields/curve and dollar conditions.
- Crypto context: BTC/ETH structure, participation/breadth, volatility and
  venue-specific funding/basis, with the execution venue named.

Keep `source`, `observed_at`, `released_at`, `effective_at`, freshness, units and
revision/vintage on every input. Store forecasts/consensus only if a licensed
source actually supplies them; an official release by itself cannot establish
a surprise relative to consensus. Missing feeds must be visible.

Official starting points: the [Federal Reserve's FOMC calendars](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm)
and [BLS release calendar](https://www.bls.gov/help/hlpical.htm). Historical macro
tests must respect what was available then, not use today's revised series;
FRED documents [real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html)
and [vintage dates](https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html).
The first scheduled-event connector and its failure policy are now implemented
above. Reliable BLS access and the remaining macro sources are still needed.

Initially this changes the brief, not trade permission. Event restrictions or
risk adjustments become separately versioned policies after paper evaluation.

### B. One top-down thesis with explicit disagreement

The weekly/daily chart establishes the broad location and nearby obstacles;
4H identifies the working trend/range and extension; 1H/15m supplies the setup
and execution timing. Do not require every rung to point the same way: an
entry-time pullback inside an uptrend is not automatically bearish.

Combine the existing readers through a single evidence contract rather than
introducing another independent regime label. Show trend direction, phase,
location, volatility, liquidity and data confidence separately. A disagreement
should explain why the bot waits or which scenario would resolve it.

Before gating on the chart reader, expand blind, timestamped human-labelled
windows beyond the small pilots already in the repository. Measure failures
by regime, symbol and timeframe; do not tune on the windows used to claim
accuracy. Chart-label agreement is a different test from trade profitability.

### C. A playbook selector that can choose no trade

Candidate mappings to test, not rules already authorized for deployment:

| Context | Candidate playbook | Main reason to refuse |
| --- | --- | --- |
| Established trend with an orderly retracement | Continuation/pullback | Extended entry, nearby higher-timeframe obstacle, poor net reward/risk |
| Compression followed by confirmed expansion | Breakout/retest | Failed acceptance, weak participation, excessive cost |
| Stable range at a meaningful edge | Range fade/reversal | Emerging directional impulse or no causal invalidation |
| Conflicting structure, poor data or disorderly chop | Wait | No defensible advantage |

Keep indicator use narrow: trend state, momentum change, volatility scale,
participation. Three indicators measuring the same momentum do not count as
three independent confirmations. Require ablation tests: does adding this
input improve the same entries after costs, or only make their explanation
longer? Respect existing playbook semantics; the named PULLBACK strategy is
not automatically equivalent to every proposed trend-continuation strategy.

### D. Exit policy matched to the thesis

Compare one change at a time on the same fills:

- Fixed structure stop/target as the baseline.
- Continuation: closed-bar structural or volatility-scaled trail after a
  defined confirmation threshold, with a maximum risk cap.
- Range fade: opposing range/liquidity target, separately testing partials.
- Failed thesis: explicit invalidation/time-based exit, with costs and gaps.

Initial stops define invalidation; they must not widen to rescue a loss.
Trailing only ratchets protection. A structural trail is not assumed to beat
a fixed-R trail until the paired comparison says so. Partial profits,
breakeven moves and trailing must be graded separately before testing a bundle.

### E. Risk remains the final authority

Keep the current mode, caps, daily protection and same-side governor while
testing. Missing or stale required inputs fail closed. The analyst may explain
a risk refusal; it may not override it, size a trade or manufacture a promotion.
If multiple concurrent positions are introduced later, add portfolio exposure
and correlated-asset limits before increasing position slots.

### F. A useful, repeatable user experience

The main brief should read: **market backdrop → likely scenario → permitted
playbook → trigger → invalidation → current bot action**. Each statement should
link to its evidence and age. A trade timeline should show context at entry,
why it qualified, fill/cost differences, protection changes and exit reason.
The review should distinguish bad selection, bad entry, bad execution and bad
exit instead of treating every loss as a strategy failure.

Make return visits useful through changed-condition summaries and honest
learning progress, not streaks or rewards for placing more trades. Waiting
when nothing qualifies is a successful system action.

## Promotion and testing sequence

1. Pin the evidence contract: causal timestamps, freshness, source/version,
   missing-data behavior and no model-originated writes.
2. Rerun corrected exit research. Preserve the old report as superseded rather
   than silently rewriting it. Treat paired unresolved trades explicitly.
3. Pre-register each selector/exit hypothesis and comparison population.
   Use chronological holdouts, symbol-clustered uncertainty, costs/slippage
   stress and per-regime attribution. Respect existing house sample floors.
4. Require both a useful improvement over the matched baseline and acceptable
   absolute results. Beating a losing baseline is not proof of a tradeable edge.
5. Version an approved PAPER experiment, preserve old open-trade exit semantics,
   and reconcile forward decisions against replay. No automatic promotion from
   a good in-sample result or an eloquent model explanation.
6. Only after explicit review: consider SHADOW/TESTNET through the app's existing
   gates. This pass grants no real-money authority.

## Boundaries of this delivery

Implemented: refreshed analyst evidence, causal trailing-research fixes and an
official scheduled-event calendar with an Overview panel. No Astra runtime was
installed, no new trading strategy enabled, and no profit improvement claimed. The larger
build above is the remaining roadmap, not a list of completed features.

Verification after the continuation: the repository gate passed 1,711 Python
tests (one skipped), 213 subtests, JavaScript contract suites, ESLint and the
control-byte scan. The calendar renderer also ran against an offline DOM and
transport. CLI calls in automated tests were stubbed: no model quota
or trading endpoints were used to test the changes. A read-only real-store
snapshot exercised the new evidence assembler. The API health response exposes
the loaded evidence version and every-turn refresh policy. The API was reloaded
under the existing supervisor, leaving the scanner process running. Verified
the Economic events panel, date-only meeting label and BLS refusal in the actual
local browser; no live trade or restart endpoint was used for testing.

Followed the repository's
[SniperSight development skill](../.agents/skills/snipersight-development/SKILL.md):
scratch-store tests, a separate research version, no live trading writes, and
preservation of unrelated working-tree changes.
