# Manual Book Tests

> 55 nodes

## Key Concepts

- **.load()** (82 connections) — `app/tests/test_manual.py`
- **.flat()** (52 connections) — `app/tests/test_manual.py`
- **.test_a_settled_trade_is_priced_with_the_engine_books_arithmetic()** (5 connections) — `app/tests/test_manual.py`
- **.test_a_settled_trade_with_no_risk_figure_is_counted_never_dropped()** (5 connections) — `app/tests/test_manual.py`
- **.test_pnl_usd_is_a_key_on_every_row_even_when_it_is_absent()** (5 connections) — `app/tests/test_manual.py`
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
- **.test_a_ladder_that_closes_the_whole_position_is_refused()** (4 connections) — `app/tests/test_manual.py`
- **.test_a_winning_position_may_move_its_stop_into_profit()** (4 connections) — `app/tests/test_manual.py`
- **.test_adoption_still_refuses_a_target_on_the_wrong_side()** (4 connections) — `app/tests/test_manual.py`
- **.test_book_reports_only_manual_trades()** (4 connections) — `app/tests/test_manual.py`
- **.test_a_cancelled_order_contributes_no_dollars()** (4 connections) — `app/tests/test_manual.py`
- **.test_live_reports_open_intents_across_every_market()** (4 connections) — `app/tests/test_manual.py`
- **.test_cancel_refuses_a_position_that_already_filled()** (4 connections) — `app/tests/test_manual.py`
- **.test_a_cancelled_intent_stays_invisible_to_every_strategy_query()** (4 connections) — `app/tests/test_manual.py`
- **.test_spot_cannot_short_and_nothing_is_written()** (3 connections) — `app/tests/test_manual.py`
- **.test_a_perp_may_short()** (3 connections) — `app/tests/test_manual.py`
- *... and 30 more nodes in this community*

## Relationships

- [Manual Arm Validation Tests](Manual_Arm_Validation_Tests.md) (43 shared connections)
- [Manual Settlement Tests](Manual_Settlement_Tests.md) (35 shared connections)
- [Manual Order Idempotency Tests](Manual_Order_Idempotency_Tests.md) (10 shared connections)
- [Manual Version Migration Tests](Manual_Version_Migration_Tests.md) (10 shared connections)
- [Trailing Stop Tests](Trailing_Stop_Tests.md) (5 shared connections)
- [Scale-Out Settlement Tests](Scale-Out_Settlement_Tests.md) (4 shared connections)
- [Chart Vendor Line Renderers](Chart_Vendor_Line_Renderers.md) (2 shared connections)

## Source Files

- `app/tests/test_manual.py`

## Audit Trail

- EXTRACTED: 275 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*