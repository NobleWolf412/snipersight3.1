# Manual Settlement Tests

> 39 nodes

## Key Concepts

- **.run_engine()** (40 connections) — `app/tests/test_manual.py`
- **.execs()** (38 connections) — `app/tests/test_manual.py`
- **.test_manual_facts_are_invisible_to_every_strategy_query()** (6 connections) — `app/tests/test_manual.py`
- **.test_a_bar_reaching_both_counts_as_the_stop()** (6 connections) — `app/tests/test_manual.py`
- **.test_unresolved_intent_stays_open_and_writes_nothing()** (6 connections) — `app/tests/test_manual.py`
- **.test_leverage_changes_margin_but_never_size_or_outcome()** (6 connections) — `app/tests/test_manual.py`
- **.test_a_resolved_order_stops_blocking_the_next_one()** (6 connections) — `app/tests/test_manual.py`
- **.test_trailing_stop_locks_in_profit()** (6 connections) — `app/tests/test_manual.py`
- **.test_scaling_out_costs_R_when_the_trade_runs()** (6 connections) — `app/tests/test_manual.py`
- **.test_a_trade_with_no_ladder_settles_exactly_as_it_did_before()** (6 connections) — `app/tests/test_manual.py`
- **.test_an_intent_cannot_fill_on_a_bar_that_already_closed()** (5 connections) — `app/tests/test_manual.py`
- **.test_target_hit_resolves_tp_with_costs_deducted()** (5 connections) — `app/tests/test_manual.py`
- **.test_stop_hit_resolves_sl()** (5 connections) — `app/tests/test_manual.py`
- **.test_rerunning_does_not_resolve_the_same_intent_twice()** (5 connections) — `app/tests/test_manual.py`
- **.test_a_stop_bar_takes_the_whole_remainder_and_fills_no_rung()** (5 connections) — `app/tests/test_manual.py`
- **.test_a_rung_price_never_reached_leaves_one_leg()** (5 connections) — `app/tests/test_manual.py`
- **.test_a_bar_that_reaches_the_target_fills_the_rung_on_its_way()** (5 connections) — `app/tests/test_manual.py`
- **.test_an_adopted_position_can_scale_out()** (5 connections) — `app/tests/test_manual.py`
- **.test_an_adopted_position_holds_instead_of_hunting_for_a_fill()** (5 connections) — `app/tests/test_manual.py`
- **.test_an_adopted_position_can_trail()** (5 connections) — `app/tests/test_manual.py`
- **.test_new_levels_do_not_reach_back_and_stop_an_old_bar()** (5 connections) — `app/tests/test_manual.py`
- **.test_entry_never_touched_within_the_window_is_missed()** (4 connections) — `app/tests/test_manual.py`
- **.test_a_profit_stop_settles_as_a_win_on_the_original_R()** (4 connections) — `app/tests/test_manual.py`
- **The separation must be structural, not a filter someone remembers.          `e** (1 connections) — `app/tests/test_manual.py`
- **Arming at bar 30 must ignore bars 0-29 entirely.          Those bars trade str** (1 connections) — `app/tests/test_manual.py`
- *... and 14 more nodes in this community*

## Relationships

- [Manual Book Tests](Manual_Book_Tests.md) (35 shared connections)
- [Manual Arm Validation Tests](Manual_Arm_Validation_Tests.md) (23 shared connections)
- [Scale-Out Settlement Tests](Scale-Out_Settlement_Tests.md) (8 shared connections)
- [Manual Fill Timing Tests](Manual_Fill_Timing_Tests.md) (8 shared connections)
- [Trailing Stop Tests](Trailing_Stop_Tests.md) (7 shared connections)
- [Manual Version Migration Tests](Manual_Version_Migration_Tests.md) (5 shared connections)
- [Manual Order Idempotency Tests](Manual_Order_Idempotency_Tests.md) (2 shared connections)
- [Chart Vendor Line Renderers](Chart_Vendor_Line_Renderers.md) (1 shared connections)

## Source Files

- `app/tests/test_manual.py`

## Audit Trail

- EXTRACTED: 205 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*