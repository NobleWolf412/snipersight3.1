# Weather Row Accounting Tests

> 13 nodes

## Key Concepts

- **.weather()** (10 connections) — `app/tests/test_weather.py`
- **.regime_fact()** (8 connections) — `app/tests/test_weather.py`
- **TestEveryRowIsAccountedFor** (7 connections) — `app/tests/test_weather.py`
- **.snapshot()** (6 connections) — `app/tests/test_weather.py`
- **.test_only_the_latest_regime_per_timeframe_is_reported()** (5 connections) — `app/tests/test_weather.py`
- **.test_an_unknown_future_state_lands_in_other_rather_than_nowhere()** (5 connections) — `app/tests/test_weather.py`
- **.test_warming_symbols_are_not_reported_as_a_quiet_market()** (4 connections) — `app/tests/test_weather.py`
- **.test_tradeable_symbols_sort_first()** (4 connections) — `app/tests/test_weather.py`
- **.test_the_four_buckets_sum_to_the_rows()** (2 connections) — `app/tests/test_weather.py`
- **.test_a_state_outside_the_three_named_ones_is_counted_not_dropped()** (2 connections) — `app/tests/test_weather.py`
- **Regime facts are appended on every change; the strip shows now.** (1 connections) — `app/tests/test_weather.py`
- **The panel's counts have to add up to the panel's rows.      They did not. The** (1 connections) — `app/tests/test_weather.py`
- **The point of counting the remainder instead of naming REJECTED.** (1 connections) — `app/tests/test_weather.py`

## Relationships

- [Weather Endpoint Tests](Weather_Endpoint_Tests.md) (9 shared connections)
- [Universe Coverage Tests](Universe_Coverage_Tests.md) (7 shared connections)
- [Regime Wording Tests](Regime_Wording_Tests.md) (2 shared connections)

## Source Files

- `app/tests/test_weather.py`

## Audit Trail

- EXTRACTED: 56 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*