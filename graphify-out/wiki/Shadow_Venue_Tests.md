# Shadow Venue Tests

> 12 nodes

## Key Concepts

- **ShadowIsNotTradeable** (9 connections) — `app/tests/test_shadow_venue.py`
- **.test_shadow_is_scanned_so_its_data_stays_warm()** (2 connections) — `app/tests/test_shadow_venue.py`
- **.test_risk_refuses_a_shadow_symbol_at_any_time()** (2 connections) — `app/tests/test_shadow_venue.py`
- **.test_the_two_sets_are_distinct_functions()** (2 connections) — `app/tests/test_shadow_venue.py`
- **.setUp()** (1 connections) — `app/tests/test_shadow_venue.py`
- **.tearDown()** (1 connections) — `app/tests/test_shadow_venue.py`
- **.test_shadow_is_NOT_in_the_tradeable_set()** (1 connections) — `app/tests/test_shadow_venue.py`
- **.test_scan_set_is_a_superset_of_the_traded_set()** (1 connections) — `app/tests/test_shadow_venue.py`
- **.test_live_loop_scans_rather_than_trades()** (1 connections) — `app/tests/test_shadow_venue.py`
- **The entire point. A shadow symbol that is not scanned goes cold and         the** (1 connections) — `app/tests/test_shadow_venue.py`
- **`admitted_at` gates every sizing decision. If it ever returned True         for** (1 connections) — `app/tests/test_shadow_venue.py`
- **Collapsing `scan_symbols` into `current_symbols` is exactly how a         shado** (1 connections) — `app/tests/test_shadow_venue.py`

## Relationships

- [Shadow Classification Tests](Shadow_Classification_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_shadow_venue.py`

## Audit Trail

- EXTRACTED: 23 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*