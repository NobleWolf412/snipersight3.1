# Manual Arm Validation Tests

> 27 nodes

## Key Concepts

- **ManualCase** (101 connections) — `app/tests/test_manual.py`
- **.test_the_total_covers_the_priced_trades_and_says_what_it_omits()** (5 connections) — `app/tests/test_manual.py`
- **.test_status_marks_to_the_last_closed_bar_not_a_live_tick()** (3 connections) — `app/tests/test_manual.py`
- **.test_status_reports_a_partly_closed_position_as_partly_closed()** (3 connections) — `app/tests/test_manual.py`
- **.test_an_untouched_position_reports_the_same_numbers_it_always_did()** (3 connections) — `app/tests/test_manual.py`
- **.test_closing_an_engine_position_never_touches_the_strategy_record()** (3 connections) — `app/tests/test_manual.py`
- **.test_a_market_close_pays_slippage_like_every_other_market_exit()** (3 connections) — `app/tests/test_manual.py`
- **.test_the_chart_shows_the_same_sign_the_book_settles()** (3 connections) — `app/tests/test_manual.py`
- **.test_the_bar_in_progress_when_armed_is_not_eligible()** (2 connections) — `app/tests/test_manual.py`
- **.test_the_retired_tags_are_read_and_never_written()** (2 connections) — `app/tests/test_manual.py`
- **.test_live_reports_nothing_when_the_book_is_empty()** (2 connections) — `app/tests/test_manual.py`
- **.setUp()** (1 connections) — `app/tests/test_manual.py`
- **.tearDown()** (1 connections) — `app/tests/test_manual.py`
- **.execs()** (1 connections) — `app/tests/test_manual.py`
- **.test_stop_on_the_wrong_side_is_refused()** (1 connections) — `app/tests/test_manual.py`
- **.test_an_override_without_candles_is_refused_not_guessed()** (1 connections) — `app/tests/test_manual.py`
- **.test_cancel_refuses_an_unknown_intent()** (1 connections) — `app/tests/test_manual.py`
- **A bar that closes exactly AT `armed_at` is still the past.          Bar 9 clos** (1 connections) — `app/tests/test_manual.py`
- **The unrealized figure must come from the same price authority as         every** (1 connections) — `app/tests/test_manual.py`
- **The panel bug this closes: a position with half taken off rendered         as f** (1 connections) — `app/tests/test_manual.py`
- **The new fields must not move the old ones. With nothing scaled out,         `bl** (1 connections) — `app/tests/test_manual.py`
- **The read set only ever grows. Dropping a tag strands every order         still** (1 connections) — `app/tests/test_manual.py`
- **The override is the whole design: the engine's simulation of this         setup** (1 connections) — `app/tests/test_manual.py`
- **execsim charges its market exits fee AND slippage. The first cut of         the** (1 connections) — `app/tests/test_manual.py`
- **status() priced R off the CURRENT stop, so a profit-side stop         inverted** (1 connections) — `app/tests/test_manual.py`
- *... and 2 more nodes in this community*

## Relationships

- [Manual Book Tests](Manual_Book_Tests.md) (43 shared connections)
- [Manual Settlement Tests](Manual_Settlement_Tests.md) (23 shared connections)
- [Manual Version Migration Tests](Manual_Version_Migration_Tests.md) (8 shared connections)
- [Trailing Stop Tests](Trailing_Stop_Tests.md) (7 shared connections)
- [Manual Order Idempotency Tests](Manual_Order_Idempotency_Tests.md) (6 shared connections)
- [Scale-Out Settlement Tests](Scale-Out_Settlement_Tests.md) (5 shared connections)
- [Manual Fill Timing Tests](Manual_Fill_Timing_Tests.md) (1 shared connections)
- [Chart Vendor Line Renderers](Chart_Vendor_Line_Renderers.md) (1 shared connections)

## Source Files

- `app/tests/test_manual.py`

## Audit Trail

- EXTRACTED: 146 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*