# Simulator Convention Tests

> 26 nodes

## Key Concepts

- **_bars()** (10 connections) — `app/tests/test_abtest.py`
- **test_abtest.py** (9 connections) — `app/tests/test_abtest.py`
- **SimulatorConventions** (7 connections) — `app/tests/test_abtest.py`
- **OneFillModel** (4 connections) — `app/tests/test_abtest.py`
- **.test_same_bar_stop_and_target_counts_as_the_stop()** (3 connections) — `app/tests/test_abtest.py`
- **.test_partial_is_refused_when_the_same_bar_also_trades_through_entry()** (3 connections) — `app/tests/test_abtest.py`
- **.test_partial_is_booked_when_the_bar_never_returns_to_entry()** (3 connections) — `app/tests/test_abtest.py`
- **.test_unresolved_position_is_open_not_a_zero()** (3 connections) — `app/tests/test_abtest.py`
- **Summary** (3 connections) — `app/tests/test_abtest.py`
- **.test_a_crossed_order_is_priced_on_the_bar_it_crossed_on()** (3 connections) — `app/tests/test_abtest.py`
- **.test_a_missing_atr_on_the_cross_degrades_audibly()** (3 connections) — `app/tests/test_abtest.py`
- **.test_short_side_mirrors_the_long_side()** (2 connections) — `app/tests/test_abtest.py`
- **Determinism** (2 connections) — `app/tests/test_abtest.py`
- **.test_same_inputs_produce_identical_results()** (2 connections) — `app/tests/test_abtest.py`
- **.test_missed_orders_are_counted_but_never_scored_as_zero()** (1 connections) — `app/tests/test_abtest.py`
- **.test_empty_book_refuses_rather_than_reporting_zero()** (1 connections) — `app/tests/test_abtest.py`
- **2x2 replay harness — the properties that make its verdict believable.  The har** (1 connections) — `app/tests/test_abtest.py`
- **spec = [(o,h,l,c), ...] -> store-shaped candle dicts.** (1 connections) — `app/tests/test_abtest.py`
- **Rules that decide whether a backtest flatters itself.** (1 connections) — `app/tests/test_abtest.py`
- **The metric this whole version moves is the same-bar stop-out rate.         If a** (1 connections) — `app/tests/test_abtest.py`
- **A partial moves the stop to breakeven. Booking one on a bar that also         t** (1 connections) — `app/tests/test_abtest.py`
- **The mirror of the above — the rule must not refuse every partial.** (1 connections) — `app/tests/test_abtest.py`
- **Running out of data is not a flat trade. Counting it as 0R would         dilute** (1 connections) — `app/tests/test_abtest.py`
- **The whole fill model is the engine's, not just the crossing price.** (1 connections) — `app/tests/test_abtest.py`
- **The passive limit rests below every low so it can never fill; the         engin** (1 connections) — `app/tests/test_abtest.py`
- *... and 1 more nodes in this community*

## Relationships

- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (1 shared connections)
- [A/B Calibration Tests](A-B_Calibration_Tests.md) (1 shared connections)
- [A/B Verdict Logic Tests](A-B_Verdict_Logic_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_abtest.py`

## Audit Trail

- EXTRACTED: 69 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*