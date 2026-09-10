# Missing History Tests

> 17 nodes

## Key Concepts

- **_warm()** (11 connections) — `app/tests/test_cold_start.py`
- **MissingHistory** (10 connections) — `app/tests/test_cold_start.py`
- **.test_a_partial_timeframe_is_flagged()** (3 connections) — `app/tests/test_cold_start.py`
- **.test_a_young_listing_is_never_flagged()** (3 connections) — `app/tests/test_cold_start.py`
- **.test_aggregate_candles_are_not_history()** (3 connections) — `app/tests/test_cold_start.py`
- **.setUp()** (2 connections) — `app/tests/test_cold_start.py`
- **.test_an_empty_timeframe_is_flagged()** (2 connections) — `app/tests/test_cold_start.py`
- **.test_a_complete_timeframe_is_not_flagged()** (2 connections) — `app/tests/test_cold_start.py`
- **.test_a_productive_import_retires_the_question()** (2 connections) — `app/tests/test_cold_start.py`
- **.test_the_1970_rows_do_not_count_as_having_asked()** (2 connections) — `app/tests/test_cold_start.py`
- **.tearDown()** (1 connections) — `app/tests/test_cold_start.py`
- **PF_XLMUSD exactly: 1D warm, 1H and 15m at zero.** (1 connections) — `app/tests/test_cold_start.py`
- **The case `history_floor` CANNOT reach — a non-NULL watermark means         the l** (1 connections) — `app/tests/test_cold_start.py`
- **A coin listed ten days ago has ten days of 15m and that is the truth,         no** (1 connections) — `app/tests/test_cold_start.py`
- **Self-termination. Once we have asked from the floor and the venue         served** (1 connections) — `app/tests/test_cold_start.py`
- **The 4,950 epoch rows reached back further than any floor but imported         NO** (1 connections) — `app/tests/test_cold_start.py`
- **A 4H bar is derived from 1H candles we already hold. Counting it         would l** (1 connections) — `app/tests/test_cold_start.py`

## Relationships

- [Mission Rail & Radar UI](Mission_Rail_%26_Radar_UI.md) (3 shared connections)
- [Cold Start Live Loop Tests](Cold_Start_Live_Loop_Tests.md) (2 shared connections)
- [History Repair Tests](History_Repair_Tests.md) (2 shared connections)

## Source Files

- `app/tests/test_cold_start.py`

## Audit Trail

- EXTRACTED: 47 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*