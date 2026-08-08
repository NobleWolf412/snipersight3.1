# History Floor Tests

> 10 nodes

## Key Concepts

- **HistoryFloor** (6 connections) — `app/tests/test_cold_start.py`
- **.test_no_timeframe_ever_reaches_back_to_1970()** (2 connections) — `app/tests/test_cold_start.py`
- **.test_floors_are_ordered_by_how_much_history_a_timeframe_needs()** (2 connections) — `app/tests/test_cold_start.py`
- **.test_the_daily_floor_matches_the_declared_constant()** (2 connections) — `app/tests/test_cold_start.py`
- **.test_an_unknown_timeframe_falls_back_to_the_daily_floor()** (2 connections) — `app/tests/test_cold_start.py`
- **.setUp()** (1 connections) — `app/tests/test_cold_start.py`
- **The bug, stated as the property that must never hold again.** (1 connections) — `app/tests/test_cold_start.py`
- **15m needs weeks, 1D needs years. Asking for four years of 15m would         be a** (1 connections) — `app/tests/test_cold_start.py`
- **One floor, defined once. If onboarding and the live loop disagreed,         a sy** (1 connections) — `app/tests/test_cold_start.py`
- **Conservative: too much history is a slow import, too little is a         silentl** (1 connections) — `app/tests/test_cold_start.py`

## Relationships

- [Cold Start Live Loop Tests](Cold_Start_Live_Loop_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_cold_start.py`

## Audit Trail

- EXTRACTED: 19 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*