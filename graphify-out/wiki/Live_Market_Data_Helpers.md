# Live Market Data Helpers

> 8 nodes

## Key Concepts

- **marketdata.py** (5 connections) — `app/engine/marketdata.py`
- **last_prices()** (5 connections) — `app/engine/marketdata.py`
- **fetch_tickers()** (5 connections) — `app/engine/marketdata.py`
- **_coinbase_ticker()** (3 connections) — `app/engine/marketdata.py`
- **_is_perp()** (3 connections) — `app/engine/marketdata.py`
- **Display-only live market-data helpers; never consumed by fact engines.  Venue-** (1 connections) — `app/engine/marketdata.py`
- **symbol -> last traded price. Missing symbols are absent, never zero.      Perp** (1 connections) — `app/engine/marketdata.py`
- **Per-symbol status map for the UI. DEGRADED is reported, never hidden.** (1 connections) — `app/engine/marketdata.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/engine/marketdata.py`

## Audit Trail

- EXTRACTED: 24 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*