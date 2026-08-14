# CalibrationAgainstTheLiveStore

> 13 nodes

## Key Concepts

- **_bars()** (10 connections) — `app/tests/test_abtest.py`
- **SimulatorConventions** (7 connections) — `app/tests/test_abtest.py`
- **.test_same_bar_stop_and_target_counts_as_the_stop()** (3 connections) — `app/tests/test_abtest.py`
- **.test_partial_is_refused_when_the_same_bar_also_trades_through_entry()** (3 connections) — `app/tests/test_abtest.py`
- **.test_partial_is_booked_when_the_bar_never_returns_to_entry()** (3 connections) — `app/tests/test_abtest.py`
- **.test_unresolved_position_is_open_not_a_zero()** (3 connections) — `app/tests/test_abtest.py`
- **.test_short_side_mirrors_the_long_side()** (2 connections) — `app/tests/test_abtest.py`
- **spec = [(o,h,l,c), ...] -> store-shaped candle dicts.** (1 connections) — `app/tests/test_abtest.py`
- **Rules that decide whether a backtest flatters itself.** (1 connections) — `app/tests/test_abtest.py`
- **The metric this whole version moves is the same-bar stop-out rate.         If a** (1 connections) — `app/tests/test_abtest.py`
- **A partial moves the stop to breakeven. Booking one on a bar that also         t** (1 connections) — `app/tests/test_abtest.py`
- **The mirror of the above — the rule must not refuse every partial.** (1 connections) — `app/tests/test_abtest.py`
- **Running out of data is not a flat trade. Counting it as 0R would         dilute** (1 connections) — `app/tests/test_abtest.py`

## Relationships

- [Engine Fault Row Tests](Engine_Fault_Row_Tests.md) (3 shared connections)
- [Next Wake Math Tests](Next_Wake_Math_Tests.md) (2 shared connections)

## Source Files

- `app/tests/test_abtest.py`

## Audit Trail

- EXTRACTED: 37 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*