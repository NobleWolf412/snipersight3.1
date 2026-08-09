# Weather Row Accounting Tests

> 17 nodes

## Key Concepts

- **.one()** (15 connections) — `app/tests/test_weather.py`
- **TestWhatTheStripSays** (11 connections) — `app/tests/test_weather.py`
- **.weather()** (10 connections) — `app/tests/test_weather.py`
- **.regime_fact()** (8 connections) — `app/tests/test_weather.py`
- **.test_only_the_latest_regime_per_timeframe_is_reported()** (5 connections) — `app/tests/test_weather.py`
- **.test_an_unknown_future_state_lands_in_other_rather_than_nowhere()** (5 connections) — `app/tests/test_weather.py`
- **.test_missing_regime_reads_as_missing_data_not_as_calm()** (4 connections) — `app/tests/test_weather.py`
- **.test_warming_symbols_are_not_reported_as_a_quiet_market()** (4 connections) — `app/tests/test_weather.py`
- **.test_tradeable_symbols_sort_first()** (4 connections) — `app/tests/test_weather.py`
- **.test_every_regime_has_a_display_label_and_a_sentence()** (3 connections) — `app/tests/test_weather.py`
- **.test_agreeing_timeframes_are_marked_aligned()** (2 connections) — `app/tests/test_weather.py`
- **.test_disagreeing_timeframes_say_so()** (2 connections) — `app/tests/test_weather.py`
- **.test_one_live_timeframe_names_which_one()** (2 connections) — `app/tests/test_weather.py`
- **A one-symbol universe with the given 1D / 4H regimes.** (1 connections) — `app/tests/test_weather.py`
- **Loud fallback: an unmapped symbol must never render as tradeable         silenc** (1 connections) — `app/tests/test_weather.py`
- **Regime facts are appended on every change; the strip shows now.** (1 connections) — `app/tests/test_weather.py`
- **The point of counting the remainder instead of naming REJECTED.** (1 connections) — `app/tests/test_weather.py`

## Relationships

- [Weather Endpoint Tests](Weather_Endpoint_Tests.md) (12 shared connections)
- [Universe Coverage Tests](Universe_Coverage_Tests.md) (8 shared connections)
- [TestEveryRowIsAccountedFor](TestEveryRowIsAccountedFor.md) (3 shared connections)
- [Regime Wording Tests](Regime_Wording_Tests.md) (2 shared connections)

## Source Files

- `app/tests/test_weather.py`

## Audit Trail

- EXTRACTED: 79 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*