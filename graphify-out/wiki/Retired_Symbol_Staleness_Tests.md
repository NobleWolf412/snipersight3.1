# Retired Symbol Staleness Tests

> 10 nodes

## Key Concepts

- **RetiredSymbolStalenessTest** (9 connections) — `app/tests/test_pipeline_quality.py`
- **.test_fails_open_when_the_universe_is_unreadable()** (4 connections) — `app/tests/test_pipeline_quality.py`
- **._stale_symbols()** (3 connections) — `app/tests/test_pipeline_quality.py`
- **.test_retired_symbol_is_not_reported_stale()** (2 connections) — `app/tests/test_pipeline_quality.py`
- **.test_live_set_is_not_shared_across_connections()** (2 connections) — `app/tests/test_pipeline_quality.py`
- **.setUp()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **.tearDown()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **Staleness is only meaningful for a symbol we still track.      Switching the u** (1 connections) — `app/tests/test_pipeline_quality.py`
- **If we cannot tell what is live, warn rather than silently suppress.** (1 connections) — `app/tests/test_pipeline_quality.py`
- **A module-level cache keyed on nothing would let an audit of one         databas** (1 connections) — `app/tests/test_pipeline_quality.py`

## Relationships

- [Bias, Trend & Setups](Bias%2C_Trend_%26_Setups.md) (1 shared connections)
- [Pipeline Quality Tests](Pipeline_Quality_Tests.md) (1 shared connections)
- [Multi-Venue Universe Tests](Multi-Venue_Universe_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_pipeline_quality.py`

## Audit Trail

- EXTRACTED: 23 (92%)
- INFERRED: 2 (8%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*