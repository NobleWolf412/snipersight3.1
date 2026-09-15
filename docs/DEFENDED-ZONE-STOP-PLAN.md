# Defended-zone trailing stop — implementation plan

Status: proposed research design, 2026-09-15. No execution change authorized by
this document. Parameters below are initial hypotheses, not proven settings.

## Outcome

Add a fourth simulated exit rule: trail behind a newly formed lower-timeframe
zone after price revisits and defends it. Keep account orders unchanged until
the comparison supports a separate deployment decision. Mirror all long rules
for shorts. Call these price zones; OHLC does not establish institutional orders.

## Fixed first specification

- Management timeframe: 15m trade -> 5m; 1H -> 15m; 4H -> 1H. Unsupported
  timeframes are explicitly ineligible. No discretionary switching mid-trade.
- Confirm swings with two completed candles on each side. A broken swing must
  already have been confirmed before the breakout candle opens.
- For a long, require a completed management candle closing above that swing
  high, with body at least 1.0 ATR(14), measured before that candle opens.
- Candidate zone: full high-low range of the most recent bearish candle among
  the five candles preceding the breakout candle. No such candle: no zone.
- Require breakout close above the zone high. Identify the zone only at the
  breakout close, never at the earlier source candle timestamp.
- Only consider breakouts occurring after the first unambiguously fully held
  management candle. Candle-level source fills cannot locate an intrabar fill.
- A later candle must overlap the zone and close above its high, without
  trading below its low. A breach below the low invalidates the candidate.
- Expire an undefended zone after 12 management candles. Process its twelfth
  candle before expiry. Freeze all timestamps and candidate transitions.
- At defense confirmation, propose zone low minus 0.25 ATR(14), using ATR known
  at that close. Stop must improve the existing stop, remain below current
  close and target, and approximately cover estimated exit costs. Otherwise
  record why it did not move. This variant deliberately requires protection
  above cost-covered entry; it is distinct from the existing swing rule.
- Apply at the next management candle, after checking exits on the confirmation
  candle against the old stop. Never widen. Do not continually change the buffer
  as volatility changes. A later defended zone can tighten the stop again.
- Track at most one pending zone: a newly qualified breakout replaces it.
  Process the existing candidate's defense/invalidation first, then replacement.
  A replacement never removes an already active stop.

## Comparable simulation and data

Create a new versioned study cohort; preserve the current three-rule cohort and
finish its enrolled trades under its frozen rules. Do not append a fourth arm
retroactively or let a dependency bump strand current trades. Implement explicit
cohort/version dispatch and compatibility tests before activation.

Run all four new-cohort arms on the SAME management candles for stop/target
ordering, fill assumptions, holding duration and costs. Original swing and +1R
decisions still use their specified trade-timeframe closes; feed their updates
onto the common management timeline. Keep the original holding deadline in
elapsed time, not the old candle count interpreted as smaller candles. Record
that this is a new-resolution baseline, separate from the earlier experiment.

Freeze the source fill, quantity, original plan, fee role and source identity.
If its timestamp only identifies a parent candle, exclude that entire parent
candle from new zone decisions; preserve and disclose conservative entry-bar
exit ambiguity. Do not pretend a smaller candle reveals the true fill moment.

Pin both required feeds until every arm is terminal, including after account
closure and universe removal. Importer already supports 5m, 15m and 1H; verify
actual contiguous coverage, aggregation alignment and rate-limit capacity.
Freeze accepted candles, reject missing/invalid data, and never silently fall
back to coarser candles. Exclude incomplete comparisons from result totals.

Distinguish candle-close eligibility from actual scanner observation time.
The research replay assumes next-candle eligibility; measure scanner lag and
label it. Real stop execution later requires separate latency-aware validation.

## UI

Research: fourth card, "Trail behind a defended zone", alongside the other
three. Show cohort start, trade/management timeframes, pending and completed
counts, and paired net differences. Separate paper and breakout-trial sources.

Journal: management-timeframe chart toggle, outlined pending zone, filled
confirmed zone, break/defense markers, dashed simulated stop path and distinct
recorded stop. Include a text timeline and tap targets usable on phones.
Use plain labels: "New support forming", "Waiting for a retest", "Support held",
"Stop raised", "Support broke", "Zone expired", and explicit no-move reasons.
Tooltips show zone prices, buffer, confirmation and effective times. Never
draw a zone as known before its detection time.

## Delivery sequence and evidence

1. Audit feed coverage, timestamp precision and scanner latency; resolve common
   timeline and cohort coexistence contracts before writing the rule.
2. Pure deterministic zone detector and four-arm simulator in scratch stores.
3. Append-only, restart-safe cohort integration with two-process idempotency.
4. Historical ENA illustration using available smaller candles, labeled
   retrospective and excluded from prospective totals.
5. Research and journal visual integration; desktop/mobile verification.
6. Activate new prospective cohort only after repository checks and review.

Tests: long/short symmetry; delayed swing confirmation; no source-candle
backdating; no same-bar move; breach versus defense; candidate replacement and
expiry; buffer and fee thresholds; gap fills; stop/target ambiguity; parent-fill
uncertainty; deadline preservation; missing candles; feed retention; independent
old/new cohort continuation; no account writes; immutable events across restart
and two real processes. UI tests verify actual plotted prices and timestamps.

Evaluate paired net return per initial risk, drawdown, stop-out frequency,
profit retained and trades cut before their original target. Report by strategy,
timeframe and source with counts and uncertainty, retaining a forward holdout
after choosing parameters. No fixed number of trades guarantees significance.
One rescued trade, higher win rate alone, or repeated parameter tuning is not
evidence to enable actual stop movement.

## Dependencies

No new image assets or chart library: reuse the installed chart renderer and
server-authoritative Decimal values. Additional lower-timeframe candle history,
storage and importer capacity are the main dependencies. Use existing ATR and
swing primitives where their timing contracts match this specification. New
cohort storage/migrations and version cascade are required; do not force-close
positions or reset existing study history to simplify migration.
