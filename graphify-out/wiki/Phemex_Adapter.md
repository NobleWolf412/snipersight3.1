# Phemex Adapter

> 18 nodes

## Key Concepts

- **phemex.py** (8 connections) — `app/engine/phemex.py`
- **_get()** (8 connections) — `app/engine/phemex.py`
- **_RateLimiter** (4 connections) — `app/engine/phemex.py`
- **list_products()** (4 connections) — `app/engine/phemex.py`
- **rank_by_volume()** (4 connections) — `app/engine/phemex.py`
- **fetch_candles()** (4 connections) — `app/engine/phemex.py`
- **last_prices()** (3 connections) — `app/engine/phemex.py`
- **funding_rate()** (3 connections) — `app/engine/phemex.py`
- **.acquire()** (2 connections) — `app/engine/phemex.py`
- **.__init__()** (1 connections) — `app/engine/phemex.py`
- **Phemex USDT-perpetual adapter — market data and ranking.  Why this venue exist** (1 connections) — `app/engine/phemex.py`
- **Shared spacing, same reasoning as universe._RateLimiter: a per-worker     sleep** (1 connections) — `app/engine/phemex.py`
- **Throttled GET with backoff. See universe._get — a dropped symbol is     indisti** (1 connections) — `app/engine/phemex.py`
- **Live USDT-settled perpetuals, normalised to the fields we care about.** (1 connections) — `app/engine/phemex.py`
- **USDT perps ranked by 24h turnover in quote currency (USD-equivalent).      One** (1 connections) — `app/engine/phemex.py`
- **Last traded price per perp, from the single 24h ticker call.      One request** (1 connections) — `app/engine/phemex.py`
- **Closed candles in [start_ts, end_ts), ascending, as store-shaped dicts.      O** (1 connections) — `app/engine/phemex.py`
- **Current funding rate for a perp, or None if the venue does not say.      Fundi** (1 connections) — `app/engine/phemex.py`

## Relationships

- [Venue Policy & Contract](Venue_Policy_%26_Contract.md) (1 shared connections)

## Source Files

- `app/engine/phemex.py`

## Audit Trail

- EXTRACTED: 48 (98%)
- INFERRED: 1 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*