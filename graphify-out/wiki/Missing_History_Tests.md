# Missing History Tests

> 15 nodes

## Key Concepts

- **MissingHistory** (10 connections) — `app/tests/test_cold_start.py`
- **_warm()** (8 connections) — `app/tests/test_cold_start.py`
- **.test_a_partial_timeframe_is_flagged()** (3 connections) — `app/tests/test_cold_start.py`
- **.test_a_young_listing_is_never_flagged()** (3 connections) — `app/tests/test_cold_start.py`
- **.test_aggregate_candles_are_not_history()** (3 connections) — `app/tests/test_cold_start.py`
- **.setUp()** (2 connections) — `app/tests/test_cold_start.py`
- **.test_an_empty_timeframe_is_flagged()** (2 connections) — `app/tests/test_cold_start.py`
- **.test_a_complete_timeframe_is_not_flagged()** (2 connections) — `app/tests/test_cold_start.py`
- **.test_the_1970_rows_do_not_count_as_having_asked()** (2 connections) — `app/tests/test_cold_start.py`
- **.tearDown()** (1 connections) — `app/tests/test_cold_start.py`
- **PF_XLMUSD exactly: 1D warm, 1H and 15m at zero.** (1 connections) — `app/tests/test_cold_start.py`
- **The case `history_floor` CANNOT reach — a non-NULL watermark means         the l** (1 connections) — `app/tests/test_cold_start.py`
- **A coin listed ten days ago has ten days of 15m and that is the truth,         no** (1 connections) — `app/tests/test_cold_start.py`
- **The 4,950 epoch rows reached back further than any floor but imported         NO** (1 connections) — `app/tests/test_cold_start.py`
- **A 4H bar is derived from 1H candles we already hold. Counting it         would l** (1 connections) — `app/tests/test_cold_start.py`

## Relationships

- [Cold Start Live Loop Tests](Cold_Start_Live_Loop_Tests.md) (2 shared connections)
- [History Repair Tests](History_Repair_Tests.md) (2 shared connections)
- [Import Self-Termination Tests](Import_Self-Termination_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_cold_start.py`

## Audit Trail

- EXTRACTED: 41 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*