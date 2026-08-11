# Trend Engine Tests

> 31 nodes

## Key Concepts

- **TriggerCase** (12 connections) — `app/tests/test_trend.py`
- **._load()** (8 connections) — `app/tests/test_trend.py`
- **IsolationCase** (6 connections) — `app/tests/test_trend.py`
- **._continuation_series()** (6 connections) — `app/tests/test_trend.py`
- **test_trend.py** (5 connections) — `app/tests/test_trend.py`
- **.test_entries_land_on_the_trend_side_of_the_ribbon()** (5 connections) — `app/tests/test_trend.py`
- **.test_a_ribbon_that_never_stacks_produces_nothing()** (3 connections) — `app/tests/test_trend.py`
- **.test_the_stack_agrees_with_the_direction()** (3 connections) — `app/tests/test_trend.py`
- **.test_the_bracket_is_the_house_bracket()** (3 connections) — `app/tests/test_trend.py`
- **.test_short_history_is_declined_rather_than_guessed()** (3 connections) — `app/tests/test_trend.py`
- **.test_it_is_deterministic()** (3 connections) — `app/tests/test_trend.py`
- **RibbonCase** (3 connections) — `app/tests/test_trend.py`
- **.test_the_trading_path_cannot_see_it()** (2 connections) — `app/tests/test_trend.py`
- **.test_it_still_runs_every_cycle()** (2 connections) — `app/tests/test_trend.py`
- **.test_the_ribbon_uses_the_engines_own_averages()** (2 connections) — `app/tests/test_trend.py`
- **.test_it_emits_under_its_own_version()** (1 connections) — `app/tests/test_trend.py`
- **.test_it_is_measured_not_enabled()** (1 connections) — `app/tests/test_trend.py`
- **.setUp()** (1 connections) — `app/tests/test_trend.py`
- **.tearDown()** (1 connections) — `app/tests/test_trend.py`
- **.test_short_windows_yield_no_ribbon_rather_than_a_partial_one()** (1 connections) — `app/tests/test_trend.py`
- **The trend-continuation playbook — what it must enter, and what it must not do.** (1 connections) — `app/tests/test_trend.py`
- **It ships switched off, and the switch is structural rather than a flag.** (1 connections) — `app/tests/test_trend.py`
- **execsim and risk query SETUP_VERSION / SCALE_VERSION. Neither reads         TRE** (1 connections) — `app/tests/test_trend.py`
- **An engine that is built and never run emits nothing to grade —         which is** (1 connections) — `app/tests/test_trend.py`
- **Synthetic candles, because the trigger must be provable rather than     observe** (1 connections) — `app/tests/test_trend.py`
- *... and 6 more nodes in this community*

## Relationships

- [cached_audit](cached_audit.md) (1 shared connections)
- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (1 shared connections)

## Source Files

- `app/tests/test_trend.py`

## Audit Trail

- EXTRACTED: 81 (99%)
- INFERRED: 1 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*