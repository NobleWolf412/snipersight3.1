# Hardening contract

This branch remediates the 2026-07-21 full audit. It intentionally changes
historical results. Older validation reports are retained as historical
artifacts and are not comparable with the current engine chain.

## Current venue contract

- Venue/instrument: Coinbase Advanced **spot**.
- Shorts: rejected by the risk authority.
- Leverage: capped at 1× cash notional.
- Execution: paper research only; no live order route exists.
- Default cost profile: conservative lowest-volume maker/taker schedule.

Changing venue, margin availability, fee tier, or execution policy requires a
new immutable manifest and engine version. It must never be a hidden config edit.

## Engine chain

- swing-v0.8: Decimal-native logarithmic volume scoring.
- structure-v0.8 / regime-v0.8: version chain follows swing inputs.
- zone-v0.9: formation quality is separate from decaying freshness.
- liq-v0.8: overlapping clusters do not create duplicate pools; a sweep no
  longer erases the later broken state.
- setup-v0.6: a reversal requires both transition structure and a recent
  directionally relevant liquidity sweep; costs come from a manifest; every
  rejected candidate is retained as a reason-coded research fact.
- exec-v0.7: signals are unavailable until confirmation; limit entries may be
  missed; maker/taker fees differ; MAE/MFE and order facts are recorded; the
  execution assumptions are content-addressed independently of the strategy.
- risk-v0.5: start-of-day loss baseline, zero risk on rejection, point-in-time
  universe gate, Coinbase-spot short rejection, 1× cash cap.

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
```

CI runs both commands on every push and pull request.
