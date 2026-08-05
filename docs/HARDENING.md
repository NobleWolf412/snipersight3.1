# Hardening contract

This branch remediates the 2026-07-21 full audit. It intentionally changes
historical results. Older validation reports are retained as historical
artifacts and are not comparable with the current engine chain.

## Current venue contract

Revised 2026-07-31. The previous text — "Coinbase Advanced spot / shorts
rejected / leverage capped at 1× cash notional" — was written 2026-07-22 and had
been wrong for weeks: the scan universe is **19 Phemex perps and zero Coinbase
symbols**. A venue contract that misdescribes the venue is worse than no contract
at all, because it is the document someone checks *instead of* the code.

- Venue/instrument: **three venues, derived per symbol, never globally selected.**
  `BTC-USD` → Coinbase **spot**; `BTCUSDT` → Phemex **perp**; `PF_XBTUSD` →
  Kraken **perp**. `venues.venue_for()` is the only thing that decides this and
  it raises rather than guessing.
- Shorts: **permitted on perps, rejected on spot** — a venue capability
  (`venues.allow_shorts`), not a risk preference. Spot cannot sell what it does
  not hold.
- Leverage: **operator dial, capped at the venue maximum** (1× spot, 10× perps,
  declared well below what the venues permit). It sets the MARGIN posted and the
  liquidation price. It never changes position size, which stays
  `risk / distance-to-stop` at every setting.
- Liquidation: **ISOLATED margin, declared** (`venues.margin_mode`). A setup
  whose stop sits beyond liquidation is refused — by `risk.py` for the strategy
  book and by `manual.validate` for the operator's, on the same formula.
- Funding: charged per settlement on perps; zero on spot by construction.
- Execution: **paper research only. No order-placement code exists anywhere in
  this repository.** `live_enabled` is a hard-coded literal in `server.py`, not a
  setting, and there is nothing behind it to enable.
- Cost profile: per venue, immutable, content-addressed. `costs.profile_for()`
  raises on an unknown symbol rather than falling back.

Changing venue, margin availability, fee tier, or execution policy requires a
new immutable manifest and engine version. It must never be a hidden config edit.

## Engine chain

**Not duplicated here.** Listing versions in prose is what made this document
wrong for six consecutive bumps. The chain is pinned in
`app/tests/test_version_cascade.py`, which fails the suite when any version moves
without its consumers moving with it, and carries the reason for each bump beside
it. That file is the authority; this one would only ever be a stale copy.

## Operational visibility

- SQLite starts with foreign-key enforcement and a busy timeout. Explicit,
  idempotent migrations make upgrades from legacy databases observable.
- Universe ranking is bounded-concurrent and publishes coverage, failure, and
  warning counts instead of silently treating missing products as valid data.
- The cockpit exposes data health, synchronized multi-timeframe context, setup
  stage counts, rejection reasons, missed-entry rate, and degraded API states.
- The diagnostic-only setup trace joins validation, risk, shadow execution,
  fills, and exits. It exposes the exact entry rationale and attributes each
  failure to portfolio, execution, setup/stop, exit logic, or economics. Shadow
  orders rejected by risk are never presented as portfolio exposure.
- Validation reports pin strategy and execution manifests. Bootstrap intervals
  are reported when a sample exists; PBO is marked unavailable until multiple
  independently retained strategy paths exist.

## A-to-Z quality contract

Observability does not change strategy constants. Before downstream engines run,
native and aggregated candles are checked for alignment, OHLC validity, gaps,
developing bars, and exact higher-timeframe reconciliation. A critical market
input failure raises a fail-closed blocker instead of producing more facts.

The full audit then checks fact causality, setup brackets and lineage, rejected
risk exposure, order availability, orphan orders/exits, exit-before-fill errors,
and authoritative equity reconciliation. Performance is marked invalid whenever
any stage is blocked. Every engine invocation records a unique run ID, input
watermark, input fingerprint, output fingerprint, status, counts, and duration;
new facts automatically retain that producer run ID. Legacy unattributed facts
remain visible as a warning until the baseline is rebuilt.

The cockpit's **PIPELINE** view is the operational source of truth. Its stages
are DATA → AGGREGATION → FACTS → SETUP → RISK → EXECUTION → ACCOUNTING. A red
evaluation banner means downstream performance must not be interpreted.

## Research gates that code cannot honestly “fix”

No refactor can turn 30 hindsight-influenced trades into proof of edge. The
system remains paper-only until all of these are met:

1. A frozen manifest is forward-tested for at least 90 calendar days and 50
   closed, filled trades.
2. Real fee tier, spread, and shadow-fill observations are reconciled against
   simulation.
3. Performance remains positive under stressed costs and after removing the
   largest winners.
4. No critical data, replay, execution, or accounting defect remains open.
5. A locked temporal holdout is evaluated once, with all attempted strategy
   variants retained in the trial ledger.

## Verification

```bash
cd app
python -m compileall -q .
python -m unittest discover -s tests -v
for f in tests/test_*.js; do node "$f" || break; done
```

The JavaScript suites are not optional extras: `ticket-math.js` decides how big
a trade is and re-implements `venues.liquidation_price`, so it is the only thing
proving the ticket and the engine agree about where a position dies.

Run them by GLOB, never by name. This section listed two files, written when
there were two; seventeen more were added over the following weeks and none of
them were added here — and the same list had been pasted into the CI workflow,
so the suite that prices every position was landing on `main` unverified while
this document said it was covered. A named list is a second place to remember
something, and it was not remembered.

CI runs all of it on every push and pull request — `.github/workflows/ci.yml`,
which fails if the glob matches nothing rather than passing an empty loop.
