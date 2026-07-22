# SniperSight

A deterministic, explainable market-structure trading platform for crypto (Coinbase spot).
Paper-trading only — **no live order execution anywhere in this codebase**.

## What it does

Maps market structure objectively, detects high-probability setups, sizes them through
a risk authority, and paper-trades them with full accounting — every decision recorded
as an append-only, versioned, reproducible fact.

- **Data spine** — Coinbase importer (closed candles only), OHLC integrity validation,
  aggregator (4H/1W built from lower timeframes).
- **Fact engines** — swings (tiered, composite-scored), structure (BOS/CHoCH), zones
  (supply/demand lifecycle + strength), liquidity (pools/sweeps), regime.
- **Strategy layer** — pullback / reversal / scale-in playbooks, fee-aware gating,
  explainable rationale on every signal.
- **Risk authority** (§9) — position sizing, exposure caps, leverage cap, daily-loss
  kill switch. Strategies request; the authority approves / reduces / rejects.
- **Execution sim** — paper fills with fees + slippage, R-multiple accounting.
- **Validation harness** — walk-forward cohorts, tail-dependence, drawdown.
- **Dynamic universe** — top Coinbase USD pairs by live volume, liquidity + history gated.
- **Nested cycle satellite** — observational only; never consumed by any trading engine.
- **Cockpit UI** — tactical-HUD chart, setup feed, replay (`as_of` time-machine),
  fact inspector, paper account readout.

## Design principles

Same data + same algorithm version → same facts, every time. Nothing repaints.
Every fact carries market-time, confirmed-time, and algorithm version. Rejections are
as auditable as approvals. No uncalibrated "mystery score." See `sources/ss3_v0.1.txt`
for the product constitution.

## Run

```
cd app
python -m pip install fastapi uvicorn
python backfill.py            # seed history (BTC/ETH + universe)
start.bat                     # watchdog: live scanner + API server + chart
```

Then open http://localhost:8422.

## Status

v0 engine complete; forward paper-trade record accumulating. Live execution is
deliberately gated behind a proven forward record and does not exist in this code.

The current hardening branch enforces Coinbase spot constraints, conservative
maker/taker costs, post-confirmation order availability, missed-limit handling,
point-in-time universe eligibility, and immutable strategy/cost manifests. Older
validation reports are not comparable across engine generations. See
`docs/HARDENING.md`.

## Verify

```
cd app
python -m compileall -q .
python -m unittest discover -s tests -v
```

## Layout

- `app/engine/` — fact engines (store, importer, swings, structure, zones, liquidity,
  regime, setups, execsim, risk, scalein, cycles, universe)
- `app/server.py` — read-only FastAPI over the fact store
- `app/static/` — cockpit UI
- `app/tests/` — deterministic engine tests
- `app/BUILDLOG.md` — append-only build journal (every decision, including the duds)
- `sources/` — product constitution and design blueprints
