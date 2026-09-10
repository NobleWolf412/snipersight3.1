# Edge Stats Determinism Tests

> 23 nodes

## Key Concepts

- **test_edgestats.py** (13 connections) — `app/tests/test_edgestats.py`
- **build()** (13 connections) — `app/tests/test_edgestats.py`
- **TempStore** (10 connections) — `app/tests/test_edgestats.py`
- **TestDeterminism** (6 connections) — `app/tests/test_edgestats.py`
- **TestKnownBooks** (6 connections) — `app/tests/test_edgestats.py`
- **TestSmallSampleRefusal** (5 connections) — `app/tests/test_edgestats.py`
- **TestFeeScenarios** (4 connections) — `app/tests/test_edgestats.py`
- **add_missed()** (3 connections) — `app/tests/test_edgestats.py`
- **.test_two_independently_built_stores_agree_byte_for_byte()** (3 connections) — `app/tests/test_edgestats.py`
- **.test_unfilled_orders_never_reach_the_statistics()** (3 connections) — `app/tests/test_edgestats.py`
- **.test_thin_timeframe_is_refused_without_poisoning_the_book()** (3 connections) — `app/tests/test_edgestats.py`
- **.test_filters_narrow_the_book()** (3 connections) — `app/tests/test_edgestats.py`
- **.test_two_runs_over_the_same_store_are_identical()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_report_writes_no_facts()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_positive_book_has_a_ci_entirely_above_zero()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_negative_book_has_a_ci_entirely_below_zero()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_longest_losing_streak_is_counted_in_confirmation_order()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_short_book_refuses_instead_of_returning_a_confident_zero()** (2 connections) — `app/tests/test_edgestats.py`
- **.tearDown()** (1 connections) — `app/tests/test_edgestats.py`
- **.test_empty_book_refuses_rather_than_reporting_zero_expectancy()** (1 connections) — `app/tests/test_edgestats.py`
- **An order that never filled. Not a trade — must not reach the statistics.** (1 connections) — `app/tests/test_edgestats.py`
- **A book of `wins` winners then `losses` losers, interleaved by time.** (1 connections) — `app/tests/test_edgestats.py`
- **A recorded result that changes between runs is not a result (§4).** (1 connections) — `app/tests/test_edgestats.py`

## Relationships

- [FaultCase](FaultCase.md) (7 shared connections)
- [test_pipeline_gates.py](test_pipeline_gates.py.md) (2 shared connections)
- [ssdata.js](ssdata.js.md) (2 shared connections)
- [Telemetry API Tests](Telemetry_API_Tests.md) (2 shared connections)
- [Kraken Adapter](Kraken_Adapter.md) (1 shared connections)
- [ni](ni.md) (1 shared connections)

## Source Files

- `app/tests/test_edgestats.py`

## Audit Trail

- EXTRACTED: 88 (99%)
- INFERRED: 1 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*