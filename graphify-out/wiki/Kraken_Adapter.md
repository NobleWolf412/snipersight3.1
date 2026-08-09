# Kraken Adapter

> 19 nodes

## Key Concepts

- **kraken.py** (10 connections) — `app/engine/kraken.py`
- **_get()** (7 connections) — `app/engine/kraken.py`
- **list_products()** (5 connections) — `app/engine/kraken.py`
- **_RateLimiter** (4 connections) — `app/engine/kraken.py`
- **maintenance_margin()** (4 connections) — `app/engine/kraken.py`
- **rank_by_volume()** (4 connections) — `app/engine/kraken.py`
- **fetch_candles()** (4 connections) — `app/engine/kraken.py`
- **funding_rate()** (3 connections) — `app/engine/kraken.py`
- **.acquire()** (2 connections) — `app/engine/kraken.py`
- **Decimal** (2 connections)
- **.__init__()** (1 connections) — `app/engine/kraken.py`
- **Kraken Futures adapter — market data and ranking. No credentials, no orders.  Op** (1 connections) — `app/engine/kraken.py`
- **Shared spacing. A per-worker sleep still bursts N requests at once, so     the g** (1 connections) — `app/engine/kraken.py`
- **Throttled GET with backoff. A dropped symbol is indistinguishable from an     il** (1 connections) — `app/engine/kraken.py`
- **Tradeable USD-quoted perpetuals, normalised to the fields we care about.      `c** (1 connections) — `app/engine/kraken.py`
- **First-tier maintenance margin as the venue publishes it.      `venues.liquidatio** (1 connections) — `app/engine/kraken.py`
- **USD perps ranked by 24h quote volume.      `volumeQuote` is already notional in** (1 connections) — `app/engine/kraken.py`
- **Current funding rate, or None if the venue does not say.      Only the CURRENT r** (1 connections) — `app/engine/kraken.py`
- **Closed candles in [start_ts, end_ts), ascending, as store-shaped dicts.      Onl** (1 connections) — `app/engine/kraken.py`

## Relationships

- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (2 shared connections)

## Source Files

- `app/engine/kraken.py`

## Audit Trail

- EXTRACTED: 54 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*