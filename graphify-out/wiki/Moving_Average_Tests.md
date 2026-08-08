# Moving Average Tests

> 53 nodes

## Key Concepts

- **ramp()** (15 connections) — `app/tests/test_ma.py`
- **Decimal** (15 connections)
- **.load()** (13 connections) — `app/tests/test_ma.py`
- **.facts()** (13 connections) — `app/tests/test_ma.py`
- **test_ma.py** (11 connections) — `app/tests/test_ma.py`
- **MaCase** (11 connections) — `app/tests/test_ma.py`
- **TestAverages** (8 connections) — `app/tests/test_ma.py`
- **TestTransitions** (7 connections) — `app/tests/test_ma.py`
- **.test_every_average_matches_its_closed_form_on_a_ramp()** (6 connections) — `app/tests/test_ma.py`
- **.test_a_move_inside_the_deadband_does_not_flip_a_slope()** (6 connections) — `app/tests/test_ma.py`
- **TestWarmup** (5 connections) — `app/tests/test_ma.py`
- **.test_nothing_is_emitted_before_the_slowest_average_exists()** (5 connections) — `app/tests/test_ma.py`
- **.test_a_slope_with_no_history_is_undecided_rather_than_flat()** (5 connections) — `app/tests/test_ma.py`
- **.test_ribbon_values_are_decimal_strings_not_floats()** (5 connections) — `app/tests/test_ma.py`
- **._turn()** (5 connections) — `app/tests/test_ma.py`
- **TestCausality** (5 connections) — `app/tests/test_ma.py`
- **.test_the_last_bar_of_the_series_is_still_a_closed_bar()** (5 connections) — `app/tests/test_ma.py`
- **.test_appending_bars_never_rewrites_an_earlier_fact()** (5 connections) — `app/tests/test_ma.py`
- **TestPredicates** (4 connections) — `app/tests/test_ma.py`
- **.test_the_first_fact_lands_on_the_first_bar_the_ribbon_exists()** (4 connections) — `app/tests/test_ma.py`
- **TestRibbonValues** (4 connections) — `app/tests/test_ma.py`
- **.test_the_slow_slope_flips_only_after_its_own_lookback()** (4 connections) — `app/tests/test_ma.py`
- **.test_a_state_is_knowable_exactly_at_its_own_bar_close()** (4 connections) — `app/tests/test_ma.py`
- **.test_no_fact_is_visible_through_the_as_of_cursor_before_it_confirmed()** (4 connections) — `app/tests/test_ma.py`
- **TestDeterminism** (4 connections) — `app/tests/test_ma.py`
- *... and 28 more nodes in this community*

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_ma.py`

## Audit Trail

- EXTRACTED: 220 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*