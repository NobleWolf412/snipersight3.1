# Venue Resolution Tests

> 11 nodes

## Key Concepts

- **LiquidationTest** (10 connections) — `app/tests/test_venues.py`
- **.test_maintenance_margin_makes_it_conservative()** (2 connections) — `app/tests/test_venues.py`
- **.test_no_liquidation_price_at_1x()** (1 connections) — `app/tests/test_venues.py`
- **.test_long_liquidation_sits_below_entry()** (1 connections) — `app/tests/test_venues.py`
- **.test_short_liquidation_sits_above_entry()** (1 connections) — `app/tests/test_venues.py`
- **.test_spot_always_survives()** (1 connections) — `app/tests/test_venues.py`
- **.test_stop_inside_liquidation_survives()** (1 connections) — `app/tests/test_venues.py`
- **.test_stop_beyond_liquidation_is_refused_long()** (1 connections) — `app/tests/test_venues.py`
- **.test_stop_beyond_liquidation_is_refused_short()** (1 connections) — `app/tests/test_venues.py`
- **.test_short_stop_inside_liquidation_survives()** (1 connections) — `app/tests/test_venues.py`
- **Liquidation is modelled NEARER than the naive 1/leverage estimate.         The** (1 connections) — `app/tests/test_venues.py`

## Relationships

- [test_venues.py](test_venues.py.md) (1 shared connections)

## Source Files

- `app/tests/test_venues.py`

## Audit Trail

- EXTRACTED: 21 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*