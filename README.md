# SniperSight

A deterministic, explainable market-structure trading platform for crypto across
**three venues** — Coinbase spot, Phemex perps, Kraken perps.
Paper-trading only — **no live order execution anywhere in this codebase**.

## What it does

Maps market structure objectively, detects setups, sizes them through a risk
authority, and paper-trades them with full accounting — every decision recorded
as an append-only, versioned, reproducible fact. **1.9M facts** over **743k
candles**, 78 tracked symbols, 19 in the live scan universe.

- **Data spine** — Coinbase, Phemex and Kraken importers (closed candles only),
  OHLC integrity validation, aggregator (4H/1W built from lower timeframes).
- **Venue abstraction** — venue is derived from the symbol (`BTC-USD` → spot,
  `BTCUSDT` → Phemex perp, `PF_XBTUSD` → Kraken perp), never globally selected.
  Each carries its own fees, funding schedule, short permission, leverage cap and
  ISOLATED liquidation model.
- **Fact engines** — swings (tiered, composite-scored), structure (BOS/CHoCH),
  zones (supply/demand lifecycle + strength), liquidity (pools/sweeps), regime,
  ranges, and four indicator engines (ma, momentum, volatility, volume) that are
  recorded but **not yet consumed** — nothing may read them until `factorstats`
  has graded them.
- **Strategy layer** — pullback / reversal / scale-in playbooks, fee-aware
  gating, cooldowns against re-entry, explainable rationale on every signal.
- **Risk authority** (§9) — position sizing, exposure caps, venue-derived
  leverage cap, liquidation-safety gate, daily-loss kill switch. Strategies
  request; the authority approves / reduces / rejects.
- **Execution sim** — paper fills with fees, slippage and funding, R-multiple
  accounting.
- **Edge statistics** — bootstrap confidence intervals on expectancy
  (`edgestats`), five-axis factor grading with redundancy detection
  (`factorstats`), fill-rate and adverse-selection probes (`entrystats`), and a
  2×2 replay harness (`abtest`).
- **Operator paper book** — trades armed by hand from the chart ticket, recorded
  under their own version so they can never reach the graded strategy record.
- **Dynamic universe** — top pairs by live volume, liquidity + history gated,
  point-in-time so a backtest cannot use tomorrow's listing.
- **Nested cycle satellite** — observational only; never consumed by any trading
  engine.
- **Five-surface UI** — COMMAND, CHART (draggable levels + order ticket),
  RESULTS, SCANNER SETUP, DIAGNOSTICS, plus a LEARN surface and a 40-term
  glossary.

## Design principles

Same data + same algorithm version → same facts, every time. Nothing repaints.
Every fact carries market-time, confirmed-time, and algorithm version. A rule
change means a new version, never an edit to an old one. Rejections are as
auditable as approvals. No uncalibrated "mystery score." Decimal end to end; no
float touches a price. See `sources/ss3_v0.1.txt` for the product constitution
and `docs/PROGRAM-PLAN.md` §6 for the full convention list.

## Run

```
cd app
python -m pip install fastapi uvicorn
python backfill.py            # seeds BTC-USD/ETH-USD history; the scanner onboards the rest
start.bat                     # watchdog: live scanner + API server + browser
```

Then open http://localhost:8422.

To begin a clean forward paper record without deleting candle history or audit
facts, use **NEW BASELINE** in the wallet card. The same operation is available
from `app/`:

```
python reset_baseline.py
```

The active baseline scopes wallet equity, positions, performance, setup
telemetry, orders, and execution results. Reprocessing history cannot repopulate
pre-baseline losses into the current paper record.

## Status

Engine complete and measuring itself honestly. Live execution is gated behind a
proven forward record and **does not exist in this code** — there is no
order-placement function anywhere, and `live_enabled` is a hard-coded literal
rather than a setting.

**No strategy currently clears zero.** REVERSAL sits at +0.15 R with a
confidence interval through zero. That figure was +0.27 R until the execution
simulator was found handing out free entries on crossed orders — two thirds of
the book's apparent edge was an artefact, and removing it is the correct outcome
for an audit and the uncomfortable one for the operator. The remaining edge is
something to test forward, not something to trust.

Older validation reports are not comparable across engine generations. See
`docs/HARDENING.md` for the venue and execution contract, `docs/PROGRAM-PLAN.md`
for where the work actually stands, and `app/BUILDLOG.md` for why every decision
was made.

## Verify

```
cd app
python -m compileall -q .
python -m unittest discover -s tests -v
node tests/test_ticket_math.js
node tests/test_lessons.js
```

The full python suite plus two JavaScript suites. (No count here on purpose —
the suite grows daily and a hardcoded number was stale within a day of being
written; the commands above report the real one.) The JS suites are not extras:
`ticket-math.js` decides how big a trade is, and it is what proves the order
ticket and the engine agree about where a position liquidates.

## Layout

- `app/engine/` — fact engines and the trading path. `pipeline.py` declares the
  per-symbol run order and is imported by every runner; `venues.py` is the only
  thing that knows what a market allows; `store.py` is the append-only fact store.
- `app/server.py` — FastAPI over the fact store. Mostly read paths, plus a small
  number of operator actions (scan, settings, credentials, arm, restart).
- `app/static/` — the five-surface UI.
- `app/tests/` — deterministic engine tests, including
  `test_version_cascade.py`, the lockfile that fails when an engine version
  moves without its consumers.
- `app/engine/quality.py` — fail-closed market-data and A-to-Z workflow audits.
- `app/BUILDLOG.md` — append-only build journal (every decision, including the
  duds and the retractions).
- `docs/` — plans, specs and contracts. `PROGRAM-PLAN.md` is canonical for
  forward work.
- `sources/` — product constitution and design blueprints.
