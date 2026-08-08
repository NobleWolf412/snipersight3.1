# Weather UI Restraint Tests

> 12 nodes

## Key Concepts

- **TestTheUiDoesNotRestateTheRules** (9 connections) — `app/tests/test_weather.py`
- **.setUp()** (2 connections) — `app/tests/test_weather.py`
- **.test_ui_has_a_loud_fallback()** (2 connections) — `app/tests/test_weather.py`
- **.test_the_cycle_backdrop_mounts_beside_the_decision_it_bears_on()** (2 connections) — `app/tests/test_weather.py`
- **.test_the_weather_mount_still_carries_the_failure()** (2 connections) — `app/tests/test_weather.py`
- **.test_ui_does_not_name_a_strategy_or_a_regime_condition()** (1 connections) — `app/tests/test_weather.py`
- **.test_ui_reads_the_weather_endpoint_and_derives_no_verdict()** (1 connections) — `app/tests/test_weather.py`
- **.test_ui_owns_its_own_stylesheet_and_mount_point()** (1 connections) — `app/tests/test_weather.py`
- **weather.js is allowed to decide how a verdict LOOKS, never what it is.** (1 connections) — `app/tests/test_weather.py`
- **A failed fetch must say so; it must never render an empty calm.** (1 connections) — `app/tests/test_weather.py`
- **The backdrop is long-horizon CONTEXT, and its own footer says nothing         i** (1 connections) — `app/tests/test_weather.py`
- **Everything weather.js used to DRAW on Command has moved. The mount         stay** (1 connections) — `app/tests/test_weather.py`

## Relationships

- [Weather Endpoint Tests](Weather_Endpoint_Tests.md) (2 shared connections)

## Source Files

- `app/tests/test_weather.py`

## Audit Trail

- EXTRACTED: 24 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*