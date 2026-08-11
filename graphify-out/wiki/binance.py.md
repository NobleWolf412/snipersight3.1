# binance.py

> 10 nodes

## Key Concepts

- **binance.py** (5 connections) — `app/engine/binance.py`
- **_RateLimiter** (4 connections) — `app/engine/binance.py`
- **_get()** (4 connections) — `app/engine/binance.py`
- **fetch_candles()** (4 connections) — `app/engine/binance.py`
- **.acquire()** (2 connections) — `app/engine/binance.py`
- **.__init__()** (1 connections) — `app/engine/binance.py`
- **Binance public market data — REFERENCE feeds only. Nothing trades here.  This ad** (1 connections) — `app/engine/binance.py`
- **Shared spacing — same shape as kraken.py's, same reason: a per-worker     sleep** (1 connections) — `app/engine/binance.py`
- **Throttled GET with backoff. Same contract as kraken._get: a dropped     request** (1 connections) — `app/engine/binance.py`
- **Closed candles in [start_ts, end_ts), ascending, as store-shaped dicts.      `sy** (1 connections) — `app/engine/binance.py`

## Relationships

- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (2 shared connections)

## Source Files

- `app/engine/binance.py`

## Audit Trail

- EXTRACTED: 24 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*