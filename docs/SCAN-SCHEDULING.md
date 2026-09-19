# Live scan scheduling

The account should get a decision as soon as the inputs used for trading are
ready across all markets. Research calculations can finish afterward.

An investigation on 2026-09-17 measured a completed scan at 789 seconds: 141
seconds of preparation, 493 seconds through the per-market engines, about 10
seconds through the paper decision, then 145 seconds before the cycle ended.
Most engine calls produced no new facts. A slow scan consumes the entry window
before an order can be placed; it does not prove that an earlier order would
have filled or been profitable.

## Execution order

1. Import completed candles using one fixed scan clock, and aggregate the
   higher timeframes. Existing orders keep their market-data feeds.
2. Run the existing trading dependencies on 15m and higher timeframes across
   every scanned market. Preserve the two execution-simulation passes around
   scale-in and the subsequent cooldown pass.
3. Update paper orders, settle the account, run paper risk, and consider orders
   using the existing global candidate ranking and shared admission gate.
4. Finish the remaining descriptive engines, 5m analysis, research-only
   strategies and replay, studies, quality report and maintenance.

The phases partition the shared pipeline roster; there is no second engine
list to keep in sync. Off-universe paper holdings receive aggregation and a
quality-gated volatility refresh for settlement, without generating new setups.
Paper settlement stays after its volatility inputs because exit slippage reads
that evidence. An idle import cannot skip checks on an existing paper order.

## Reusing unchanged calculations

Only explicitly enumerated, deterministic descriptive engines are eligible.
The process-local cache is tied to one connection and is lost on restart. A
successful run is reusable only when its exact candle content, relevant
versions, upstream fact revisions and existing output revision still match.
Candle import timestamps are excluded because engines do not read them.

An old-candle repair invalidates the cache even if row count and latest
timestamp stay unchanged. Swings include their pinned prior-generation
structure and liquidity inputs. Failed calculations are retried. If upstream
inputs change during an engine run, the run is not cached as current. Fact
revision checks rely on the repository's append-only fact invariant.

Quality, account, setup, execution and cross-timeframe consumers are not
cached. Strategy rules, risk settings, entry deadlines, fact versions and
existing account/history records remain in place. Only the operational live
runner version changes.

## Verification and limits

Tests compare full and phased fact hashes, including candle repairs and
higher-timeframe updates; cover the complete roster including its repeated
execution pass; and assert that all markets and fresh account state precede
dispatch. A second SQLite connection tests concurrent upstream writes.

A scratch copy of BNBUSDT's real history produced identical fact hashes. The
full per-symbol pipeline took 11.34 seconds; the initial priority portion took
3.08 seconds and its warm repeat took 0.93 seconds. These are engine-only
measurements, not claims about complete production cycles or trade outcomes.

Production checks after deployment on 2026-09-17:

| Observed pass | Account decision | Whole scan |
| --- | --- | --- |
| Earlier investigation sample | About 644 seconds | 789 seconds |
| First new pass, empty cache | 300 seconds | 874 seconds |
| Repeat with new candles | About 249 seconds to the paper-risk log | Included the scheduled daily log cleanup; not a normal-cycle comparison |

These are operational observations on changing market data, not a controlled
speed benchmark. The repeat scan woke at 23:40:05 Eastern and recorded its paper
risk pass at 23:44:14. It processed the existing ADA paper order's fill during
normal monitoring. No new engine fault was recorded during these checks.

The repeat's routine data audit finished around 23:52:50, after which the daily
retention job planned removal of 499,442 old engine-run rows. That maintenance
continues to occupy the scanner between account passes. The deployed change
demonstrates earlier account decisions; it does not establish a substantially
faster full-cycle cadence. The existing cleanup retains trade facts and the
engine-run records those facts reference.

`SCAN TIMING` records preparation, priority analysis, account decision, deferred
work and total duration, plus cache skips. `ORDER LATENCY` joins a dispatched
order's recorded creation time to its matching strategy version and attempt's
confirmation time. Both survive log rotation. Deferred research and the final
quality audit still delay the next scan: earlier dispatch and faster repeat
calculations do not eliminate that cost.
