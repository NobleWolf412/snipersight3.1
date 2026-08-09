# Venue Policy & Contract

> 23 nodes

## Key Concepts

- **venues.py** (14 connections) — `app/engine/venues.py`
- **venue_for()** (9 connections) — `app/engine/venues.py`
- **Decimal** (6 connections)
- **Venue** (4 connections) — `app/engine/venues.py`
- **round_trip_cost_rate()** (4 connections) — `app/engine/venues.py`
- **liquidation_price()** (4 connections) — `app/engine/venues.py`
- **stop_survives_liquidation()** (4 connections) — `app/engine/venues.py`
- **funding_cost_rate()** (4 connections) — `app/engine/venues.py`
- **max_leverage()** (3 connections) — `app/engine/venues.py`
- **reference_for()** (2 connections) — `app/engine/venues.py`
- **ref_key()** (2 connections) — `app/engine/venues.py`
- **by_key()** (2 connections) — `app/engine/venues.py`
- **allow_shorts()** (2 connections) — `app/engine/venues.py`
- **.is_perp()** (1 connections) — `app/engine/venues.py`
- **is_reference_key()** (1 connections) — `app/engine/venues.py`
- **Venue descriptors — the single place that knows what a market ALLOWS.  Before** (1 connections) — `app/engine/venues.py`
- **Which venue this symbol trades on. Raises on anything unrecognised —     guessi** (1 connections) — `app/engine/venues.py`
- **(venue_key, native_symbol) of this symbol's reference feed, or None.     None i** (1 connections) — `app/engine/venues.py`
- **The storage key the reference series lives under — 'BICOUSDT@binance-spot'.** (1 connections) — `app/engine/venues.py`
- **Fee rate paid on notional for one full round trip (maker in, taker out).** (1 connections) — `app/engine/venues.py`
- **Approximate liquidation price for a leveraged perp position, ISOLATED.      `(** (1 connections) — `app/engine/venues.py`
- **Would the stop trigger BEFORE liquidation?      Ported intent from the prior p** (1 connections) — `app/engine/venues.py`
- **Funding paid on notional over a holding period. Zero on spot.      Funding is** (1 connections) — `app/engine/venues.py`

## Relationships

- [Volume, Ranges & Aggregation](Volume%2C_Ranges_%26_Aggregation.md) (2 shared connections)

## Source Files

- `app/engine/venues.py`

## Audit Trail

- EXTRACTED: 70 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*