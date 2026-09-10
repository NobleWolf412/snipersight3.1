# Manual Book Tests

> 94 nodes

## Key Concepts

- **ManualCase** (101 connections) — `app/tests/test_manual.py`
- **.load()** (82 connections) — `app/tests/test_manual.py`
- **.flat()** (52 connections) — `app/tests/test_manual.py`
- **._rows()** (7 connections) — `app/tests/test_manual.py`
- **.test_a_settled_order_id_is_not_answered_as_still_armed()** (7 connections) — `app/tests/test_manual.py`
- **.test_leverage_changes_margin_but_never_size_or_outcome()** (6 connections) — `app/tests/test_manual.py`
- **.test_a_refused_arm_writes_nothing_at_all()** (5 connections) — `app/tests/test_manual.py`
- **.test_the_same_order_arriving_twice_is_a_receipt_not_a_refusal()** (5 connections) — `app/tests/test_manual.py`
- **.test_a_changed_plan_is_not_the_same_order()** (5 connections) — `app/tests/test_manual.py`
- **.test_two_plans_cannot_share_one_order_id()** (5 connections) — `app/tests/test_manual.py`
- **.test_unresolved_finds_work_wherever_it_lives()** (5 connections) — `app/tests/test_manual.py`
- **.test_a_settled_trade_is_priced_with_the_engine_books_arithmetic()** (5 connections) — `app/tests/test_manual.py`
- **.test_a_settled_trade_with_no_risk_figure_is_counted_never_dropped()** (5 connections) — `app/tests/test_manual.py`
- **.test_pnl_usd_is_a_key_on_every_row_even_when_it_is_absent()** (5 connections) — `app/tests/test_manual.py`
- **.test_the_total_covers_the_priced_trades_and_says_what_it_omits()** (5 connections) — `app/tests/test_manual.py`
- **.test_cancel_resolves_the_intent_without_recording_a_trade()** (5 connections) — `app/tests/test_manual.py`
- **.test_arming_the_same_side_twice_is_refused()** (4 connections) — `app/tests/test_manual.py`
- **.test_the_guard_is_on_the_SIDE_not_the_prices()** (4 connections) — `app/tests/test_manual.py`
- **.test_the_opposite_side_is_left_alone()** (4 connections) — `app/tests/test_manual.py`
- **.test_the_refusal_names_the_order_that_blocked_it()** (4 connections) — `app/tests/test_manual.py`
- **.test_the_receipt_is_the_recorded_plan_not_the_second_request()** (4 connections) — `app/tests/test_manual.py`
- **.test_a_stop_beyond_liquidation_is_refused_by_the_api_not_just_the_ui()** (4 connections) — `app/tests/test_manual.py`
- **.test_spot_is_pinned_to_1x()** (4 connections) — `app/tests/test_manual.py`
- **.test_a_rung_outside_the_bracket_is_refused_before_anything_is_written()** (4 connections) — `app/tests/test_manual.py`
- **.test_a_rung_below_the_entry_is_allowed()** (4 connections) — `app/tests/test_manual.py`
- *... and 69 more nodes in this community*

## Relationships

- [Manual Settlement Tests](Manual_Settlement_Tests.md) (69 shared connections)
- [Manual Version Migration Tests](Manual_Version_Migration_Tests.md) (18 shared connections)
- [Trailing Stop Tests](Trailing_Stop_Tests.md) (12 shared connections)
- [Manual Fill Timing Tests](Manual_Fill_Timing_Tests.md) (1 shared connections)
- [Manual Arm Validation Tests](Manual_Arm_Validation_Tests.md) (1 shared connections)
- [Engine Fault Row Tests](Engine_Fault_Row_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_manual.py`

## Audit Trail

- EXTRACTED: 468 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*