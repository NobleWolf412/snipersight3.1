# Entry Stats Tests

> 56 nodes

## Key Concepts

- **.book()** (25 connections) — `app/tests/test_entrystats.py`
- **TempStore** (20 connections) — `app/tests/test_entrystats.py`
- **test_entrystats.py** (16 connections) — `app/tests/test_entrystats.py`
- **._two_books()** (9 connections) — `app/tests/test_entrystats.py`
- **TestVersionSafeJoin** (8 connections) — `app/tests/test_entrystats.py`
- **.exec_manifest()** (7 connections) — `app/tests/test_entrystats.py`
- **.plan()** (7 connections) — `app/tests/test_entrystats.py`
- **.order()** (7 connections) — `app/tests/test_entrystats.py`
- **.test_both_denominators_are_reported_and_named_apart()** (7 connections) — `app/tests/test_entrystats.py`
- **candle()** (6 connections) — `app/tests/test_entrystats.py`
- **TestPlannedVsRealised** (6 connections) — `app/tests/test_entrystats.py`
- **TestSmallSampleRefusal** (6 connections) — `app/tests/test_entrystats.py`
- **.outcome()** (5 connections) — `app/tests/test_entrystats.py`
- **TestDeterminism** (5 connections) — `app/tests/test_entrystats.py`
- **TestFillRate** (5 connections) — `app/tests/test_entrystats.py`
- **.test_a_live_order_is_not_counted_as_a_miss()** (5 connections) — `app/tests/test_entrystats.py`
- **.test_maker_then_market_joins_plan_limit_and_actual_fill_once()** (5 connections) — `app/tests/test_entrystats.py`
- **TestExecutionWindow** (4 connections) — `app/tests/test_entrystats.py`
- **.test_missing_manifest_falls_back_loudly()** (4 connections) — `app/tests/test_entrystats.py`
- **TestCounterfactualLabelling** (4 connections) — `app/tests/test_entrystats.py`
- **TestSameBarResolution** (4 connections) — `app/tests/test_entrystats.py`
- **TestCli** (4 connections) — `app/tests/test_entrystats.py`
- **.test_recorded_gap_is_zero_and_says_why()** (3 connections) — `app/tests/test_entrystats.py`
- **.test_counterfactual_geometry_is_measured_off_the_actual_open()** (3 connections) — `app/tests/test_entrystats.py`
- **.test_short_geometry_is_not_the_long_formula_with_a_sign_flip()** (3 connections) — `app/tests/test_entrystats.py`
- *... and 31 more nodes in this community*

## Relationships

- [Kraken Adapter](Kraken_Adapter.md) (3 shared connections)
- [TestNoLookahead](TestNoLookahead.md) (3 shared connections)
- [ProtectedBroker](ProtectedBroker.md) (2 shared connections)
- [Telemetry API Tests](Telemetry_API_Tests.md) (2 shared connections)

## Source Files

- `app/tests/test_entrystats.py`

## Audit Trail

- EXTRACTED: 229 (99%)
- INFERRED: 3 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*