# Prospective stop comparison

Approved 2026-09-15 after a journal review: compare original stops, cost-cover
after +1 initial risk, and confirmed swing trailing on the same new trades.
This is simulated research. It never moves an account's stop or places orders.

## Cohort

Activation freezes a wall-clock start and ID watermarks for the paper outbox
and breakout trial events. Only bot paper orders and breakout trial placements
created after that start and watermark are enrolled. Already-open and historical
trades are excluded. New orders already filled and closed when the scanner
observes them still qualify: the rules were declared before those orders existed.
The original plan, actual source fill, quantity and fee role are frozen. Manual
intervention excludes an unfinished comparison, not just its unfavorable arm.

The two source groups share the comparison rules; source is visible per trade.
The comparison does not independently select entries. It follows the existing
paper account's and breakout trial's admitted entries, with their selection
constraints. Results therefore do not describe every market opportunity.

## Exactly three rules

1. **Original stop:** original stop, original target, original holding limit.
2. **Cover costs after +1R:** a surviving completed candle must reach one initial
   fill-to-original-stop distance in profit. The entry candle is excluded
   because its high/low may predate a maker fill. On the next candle, set a
   tighter stop solving for the price covering both fees, modeled funding to
   the next candle, and slippage estimated with the latest known ATR. This is
   done once. Gaps, subsequent funding and changed ATR can still produce loss.
3. **Follow confirmed swings:** a strict pivot requires two candles on either
   side. Successive higher pivot lows raise a long stop to the new low;
   successive lower pivot highs lower a short stop to the new high. Confirmation
   occurs at the second right-hand candle's close, and adjustment takes effect
   next candle. Stops only tighten, remain inside the target, and do not inherit
   the cost-cover rule.

Each bar checks its existing stop and target **before** considering an update.
A candle touching both levels counts as a stop. Gaps use the shared stop-fill
helper; a better-looking intrabar sequence is never assumed. Every arm uses the
same source entry, quantity, target, holding limit and cost profile. Costs use
the shared settlement function with full-candle holding duration. Dollar P&L
is exact price movement minus costs times quantity, never rounded R times risk.
The simulated original-stop baseline can differ from recorded account money,
whose existing timing/ATR conventions are not rewritten by this experiment.

## Integrity and reporting

`stop_study`, `stop_study_events` and `stop_study_checks` are a separate ledger.
Updates use `BEGIN IMMEDIATE`. Configuration, fills, accepted candles, stop moves
and results are immutable. Repeated scans and two processes cannot duplicate
enrollment. Breakout's frozen candles take precedence over revised imports.
Invalid or missing candles stop progress on that trade. Warmup is a contiguous
valid prefix; missing ATR is reported rather than silently estimated as zero.

Every unfinished comparison retains its import feed until all three arms finish,
even if the source position is closed or leaves the universe. Reports total only
completed triplets with usable cost estimates; unfinished or incomplete-cost
comparisons are shown separately. No score or automatic strategy promotion is
derived. Dependency/version changes pause the study. A deliberate migration is
needed to continue under new rules; no automatic reset or force-close occurs.

## Journal visuals

The profit-along-the-way reading uses complete interior candles and a recorded
exit, excluding entry/exit candle extremes. It is a lower bound before fees and
funding, not a guaranteed executable profit. Missing interior candles are labeled
incomplete. Profit given back is the observed positive price profit no longer
present at exit, capped at that profit (not the subsequent loss below entry).
Manual/adjusted sizing is not inferred. Existing historical trades receive these
read-only journal metrics but never enter the prospective study totals.

The server supplies chart price precision from recorded levels. The browser uses
it for candle and marker series; financial values remain server-authoritative.
New enrolled journal trades additionally show simulated stop paths, adjustments
and results, clearly separate from recorded execution.
