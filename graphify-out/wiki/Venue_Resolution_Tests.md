# Venue Resolution Tests

> 34 nodes

## Key Concepts

- **LiquidationTest** (10 connections) — `app/tests/test_venues.py`
- **test_venues.py** (7 connections) — `app/tests/test_venues.py`
- **VenueResolutionTest** (5 connections) — `app/tests/test_venues.py`
- **CostTest** (5 connections) — `app/tests/test_venues.py`
- **ShortCapabilityTest** (4 connections) — `app/tests/test_venues.py`
- **.test_unknown_symbol_raises_rather_than_guessing()** (2 connections) — `app/tests/test_venues.py`
- **.test_risk_helper_falls_back_to_refusing_the_short()** (2 connections) — `app/tests/test_venues.py`
- **.test_maintenance_margin_makes_it_conservative()** (2 connections) — `app/tests/test_venues.py`
- **.test_perp_fees_are_cheaper_than_spot()** (2 connections) — `app/tests/test_venues.py`
- **.test_funding_accrues_per_settlement_not_once()** (2 connections) — `app/tests/test_venues.py`
- **.test_leverage_cap_is_conservative_against_the_venue_maximum()** (2 connections) — `app/tests/test_venues.py`
- **VersionTest** (2 connections) — `app/tests/test_venues.py`
- **.test_coinbase_spot_from_dashed_usd_symbol()** (1 connections) — `app/tests/test_venues.py`
- **.test_phemex_perp_from_usdt_symbol()** (1 connections) — `app/tests/test_venues.py`
- **.test_perp_flag()** (1 connections) — `app/tests/test_venues.py`
- **.test_shorts_are_venue_derived_not_global()** (1 connections) — `app/tests/test_venues.py`
- **.test_risk_helper_agrees_with_the_venue_table()** (1 connections) — `app/tests/test_venues.py`
- **.test_no_liquidation_price_at_1x()** (1 connections) — `app/tests/test_venues.py`
- **.test_long_liquidation_sits_below_entry()** (1 connections) — `app/tests/test_venues.py`
- **.test_short_liquidation_sits_above_entry()** (1 connections) — `app/tests/test_venues.py`
- **.test_spot_always_survives()** (1 connections) — `app/tests/test_venues.py`
- **.test_stop_inside_liquidation_survives()** (1 connections) — `app/tests/test_venues.py`
- **.test_stop_beyond_liquidation_is_refused_long()** (1 connections) — `app/tests/test_venues.py`
- **.test_stop_beyond_liquidation_is_refused_short()** (1 connections) — `app/tests/test_venues.py`
- **.test_short_stop_inside_liquidation_survives()** (1 connections) — `app/tests/test_venues.py`
- *... and 9 more nodes in this community*

## Relationships

- [Multi-Venue Universe Tests](Multi-Venue_Universe_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_venues.py`

## Audit Trail

- EXTRACTED: 67 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*