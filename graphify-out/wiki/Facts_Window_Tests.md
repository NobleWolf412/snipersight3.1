# Facts Window Tests

> 19 nodes

## Key Concepts

- **FactsWindowTests** (12 connections) — `app/tests/test_phone_front_door.py`
- **._get()** (7 connections) — `app/tests/test_phone_front_door.py`
- **.setUp()** (3 connections) — `app/tests/test_phone_front_door.py`
- **._seed()** (3 connections) — `app/tests/test_phone_front_door.py`
- **.test_the_fixture_reaches_further_back_than_the_window()** (3 connections) — `app/tests/test_phone_front_door.py`
- **.test_the_default_is_still_unbounded()** (3 connections) — `app/tests/test_phone_front_door.py`
- **.test_a_windowed_request_says_what_it_dropped()** (3 connections) — `app/tests/test_phone_front_door.py`
- **.test_the_window_keeps_the_RECENT_end()** (3 connections) — `app/tests/test_phone_front_door.py`
- **.test_both_kinds_are_cut_at_the_same_point_in_time()** (3 connections) — `app/tests/test_phone_front_door.py`
- **.test_the_window_never_returns_more_than_unbounded()** (2 connections) — `app/tests/test_phone_front_door.py`
- **.test_the_chart_asks_for_the_same_window_it_draws()** (2 connections) — `app/tests/test_phone_front_door.py`
- **/api/facts had no limit clause of any kind.      It returned every fact ever w** (1 connections) — `app/tests/test_phone_front_door.py`
- **BARS + OLDER hourly candles, and facts spread across all of them.          Two** (1 connections) — `app/tests/test_phone_front_door.py`
- **The property that made the old version of this suite dishonest.          If th** (1 connections) — `app/tests/test_phone_front_door.py`
- **Changing the default would silently truncate every existing caller.         The** (1 connections) — `app/tests/test_phone_front_door.py`
- **No silent caps. A caller that asked for a window it did not get has         to** (1 connections) — `app/tests/test_phone_front_door.py`
- **The end of the chart the operator is looking at, and the end that         bears** (1 connections) — `app/tests/test_phone_front_door.py`
- **`bars` is a bound on BARS, not on facts. The swings are seeded a         third** (1 connections) — `app/tests/test_phone_front_door.py`
- **Two numbers for 'how much chart is there' would drift, and the         symptom** (1 connections) — `app/tests/test_phone_front_door.py`

## Relationships

- [Baseline Reset Guard Tests](Baseline_Reset_Guard_Tests.md) (1 shared connections)
- [Fact Store & Migrations](Fact_Store_%26_Migrations.md) (1 shared connections)

## Source Files

- `app/tests/test_phone_front_door.py`

## Audit Trail

- EXTRACTED: 51 (98%)
- INFERRED: 1 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*