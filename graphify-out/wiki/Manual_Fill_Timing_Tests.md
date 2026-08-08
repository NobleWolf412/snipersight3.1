# Manual Fill Timing Tests

> 48 nodes

## Key Concepts

- **FinestTimeframeCase** (28 connections) — `app/tests/test_manual.py`
- **.fine()** (17 connections) — `app/tests/test_manual.py`
- **.coarse()** (17 connections) — `app/tests/test_manual.py`
- **.write()** (16 connections) — `app/tests/test_manual.py`
- **.resolve()** (14 connections) — `app/tests/test_manual.py`
- **.arm()** (12 connections) — `app/tests/test_manual.py`
- **.test_a_finer_series_that_begins_after_an_ADOPTED_fill_is_refused()** (10 connections) — `app/tests/test_manual.py`
- **.test_with_no_finer_series_it_falls_back_and_says_so()** (9 connections) — `app/tests/test_manual.py`
- **.test_the_finest_stored_timeframe_is_what_an_open_intent_resolves_on()** (8 connections) — `app/tests/test_manual.py`
- **.test_a_fill_still_needs_a_bar_that_opened_after_the_order()** (8 connections) — `app/tests/test_manual.py`
- **.test_the_entry_window_keeps_its_length_in_time_not_in_bars()** (8 connections) — `app/tests/test_manual.py`
- **.test_a_finer_series_that_begins_after_the_order_is_refused_audibly()** (8 connections) — `app/tests/test_manual.py`
- **.test_a_finer_series_that_stopped_being_ingested_is_refused_audibly()** (8 connections) — `app/tests/test_manual.py`
- **.test_an_adopted_fill_the_finer_series_covers_still_resolves_finely()** (8 connections) — `app/tests/test_manual.py`
- **.test_a_series_beginning_exactly_on_the_fill_is_covered()** (8 connections) — `app/tests/test_manual.py`
- **.test_an_ordinary_order_is_still_anchored_to_when_it_was_armed()** (8 connections) — `app/tests/test_manual.py`
- **.test_a_pending_row_counts_its_remaining_bars_in_the_chart_bars()** (7 connections) — `app/tests/test_manual.py`
- **.test_one_cycle_of_ingestion_lag_does_not_downgrade_the_grid()** (7 connections) — `app/tests/test_manual.py`
- **.test_a_settled_trade_is_not_touched_when_finer_bars_arrive()** (7 connections) — `app/tests/test_manual.py`
- **.half_fine()** (7 connections) — `app/tests/test_manual.py`
- **.test_the_series_is_admitted_and_the_fill_indexed_by_ONE_timestamp()** (7 connections) — `app/tests/test_manual.py`
- **.adopt()** (6 connections) — `app/tests/test_manual.py`
- **.test_cancel_sees_a_fill_that_landed_on_the_finer_series()** (6 connections) — `app/tests/test_manual.py`
- **test_manual.py** (3 connections) — `app/tests/test_manual.py`
- **.notes()** (3 connections) — `app/tests/test_manual.py`
- *... and 23 more nodes in this community*

## Relationships

- [Manual Settlement Tests](Manual_Settlement_Tests.md) (8 shared connections)
- [Manual Arm Validation Tests](Manual_Arm_Validation_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_manual.py`

## Audit Trail

- EXTRACTED: 263 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*