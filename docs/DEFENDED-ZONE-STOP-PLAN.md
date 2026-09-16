# Defended-zone stop comparison

Implemented research design, 2026-09-15. This study never changes account stops.
Parameters are hypotheses, not proven settings.

## Revised comparison

A new prospective cohort has five paths: original stop, smaller-timeframe swing
trail at candle-close timing, the same swing trail at scanner timing, defended
zone at candle-close timing, and defended zone at scanner timing. All paths
share the actual source fill, size, original target, cost profile and management
candles. Compare zones directly with the matching swing path, not just with the
original stop. Both trails use a 0.25 ATR(14) buffer and accept any valid tightening;
they do not require break-even. Never widen a stop.

Management mapping: 15m -> 5m; 1H -> 15m; 4H -> 1H. Other timeframes are excluded.
Swings require strict two-candle neighbors on each side. A higher low (lower
high for shorts) tightens the simple trail, buffered below (above) the pivot.

The zone path requires a close through an already-confirmed swing high/low,
with directional candle body at least the preceding candle's ATR. Choose the
last opposing candle among five preceding candles, using its full high-low.
Identify the zone at breakout close, never at its source candle. A subsequent
candle must overlap the zone, close beyond its favorable edge, and not wick
through the opposite edge. Process defense/breach before replacing a candidate.
Process the twelfth subsequent candle before expiring an untested candidate.
Only one candidate is pending; replacing it does not remove an active stop.

A qualified defense proposes the buffered zone edge. Stops must tighten, remain
on the safe side of current close and target. Reasons for no move, failed zones,
expiry, and replacements are recorded. Wicks invalidating a zone are a frozen
initial design choice, not a claim about how all order blocks behave.

## Honest timing and evidence

Every accepted management bar records its first study observation time. Ideal
moves become eligible next candle; scanner-timed moves become eligible at the
first management boundary strictly after observation. Pending proposals survive
replay/restart through frozen bars. If an observed proposal is already crossed
at application, it is rejected as missed protection; no favorable retrospective
fill is awarded. Simultaneous proposals consolidate to the final tightest stop.

The entire source parent entry candle is excluded from management decisions.
Its stop touches count conservatively; target-only touches do not, because the
intrabar entry time is unknown. Stop wins when both stop and target are touched.
Holding deadline remains parent-fill-open + original max-bars * parent duration.
All arms use management bars for settlement, fees and slippage; dollars are
computed from exact simulated exit values, not rounded R. Gaps can cause losses.

Enrollment uses activation watermarks and creation timestamps. Source trades
must remain bot-controlled and grade eligible. Warmup and accepted bars freeze;
fewer than fifteen valid contiguous warmup candles excludes the comparison.
Missing or invalid forward candles pauses rather than skipping ahead. Both
parent and management feeds remain pinned until every path finishes. Only
complete five-path comparisons with full cost estimates enter totals.

The earlier three-rule study is unchanged and separately reported. Its frozen
dependency mismatch pauses it visibly; no history is rewritten or force-closed.
The new study has its own tables, dependencies, version and activation watermark.
Two-process writers serialize with BEGIN IMMEDIATE; reads never activate it.

## Product surfaces

Research shows five path totals, zone-versus-swing differences, activation and
never-activated counts, and trails stopping trades that eventually reached the
original target. Results group by source, strategy and parent timeframe; unknown
strategy remains visibly unknown. Individual trades show exclusion/data reasons.
Journal has a recorded-chart / smaller-comparison toggle, simulated stop traces,
zone boundaries and a text timeline with confirmation, observation and effective
times. Recorded entry, exit and original stop remain distinct from simulations.

## Verification and interpretation

Scratch tests cover timing, mirrored shorts, original holding duration, entry
ambiguity, zone defense, delayed observation, missed protection, frozen candles,
missing data, warmup exclusion, account isolation and two real process writers.
Desktop/mobile validation is required before deployment.

Historical ENA is an illustration only, never enrolled retrospectively. A
five-minute replay found no qualifying defended zone; the simple buffered swing
trail did move. Historical scanner-observation times are unavailable, so only
ideal timing can be interpreted directly. Import timestamps are not study
observation timestamps. Do not tune the zone rule to rescue that single trade.

Remaining limits: this compares exits on identical source trades, not whole-book
slot availability or future entries. No statistical superiority claim, automated
selection or actual stop activation is implemented. New prospective evidence and
a separate deployment decision are required before changing real stop behavior.
No new image assets, packages or chart library are needed. More candle history,
storage and scanner capacity are the operational dependencies.
