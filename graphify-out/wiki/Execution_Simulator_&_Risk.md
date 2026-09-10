# Execution Simulator & Risk

> 21 nodes

## Key Concepts

- **ExecutionRebuild** (17 connections) — `app/tests/test_execution_rebuild.py`
- **.fact()** (7 connections) — `app/tests/test_execution_rebuild.py`
- **.plan()** (7 connections) — `app/tests/test_execution_rebuild.py`
- **.seed_book()** (7 connections) — `app/tests/test_execution_rebuild.py`
- **.cycle()** (5 connections) — `app/tests/test_execution_rebuild.py`
- **.test_real_replay_releases_ghost_but_keeps_a_genuinely_open_slot()** (4 connections) — `app/tests/test_execution_rebuild.py`
- **.test_the_veto_can_never_reach_a_market_holding_a_slot()** (4 connections) — `app/tests/test_execution_rebuild.py`
- **.test_old_generation_close_does_not_hide_missing_current_work()** (3 connections) — `app/tests/test_execution_rebuild.py`
- **.test_only_current_baseline_enabled_plans_need_rebuilding()** (3 connections) — `app/tests/test_execution_rebuild.py`
- **.test_cycle_recovers_removed_market_even_without_new_candles()** (3 connections) — `app/tests/test_execution_rebuild.py`
- **.test_quality_failure_never_fabricates_a_close()** (3 connections) — `app/tests/test_execution_rebuild.py`
- **.test_retired_gap_note_cannot_be_used_to_reconstruct_a_trade()** (3 connections) — `app/tests/test_execution_rebuild.py`
- **.test_a_plan_whose_order_bar_has_not_printed_is_not_missing_work()** (3 connections) — `app/tests/test_execution_rebuild.py`
- **.decisions()** (2 connections) — `app/tests/test_execution_rebuild.py`
- **.test_a_timeframe_risk_cannot_size_is_not_missing_work()** (2 connections) — `app/tests/test_execution_rebuild.py`
- **.setUp()** (1 connections) — `app/tests/test_execution_rebuild.py`
- **.tearDown()** (1 connections) — `app/tests/test_execution_rebuild.py`
- **Run orchestration with network, routing and housekeeping stubbed.** (1 connections) — `app/tests/test_execution_rebuild.py`
- **What makes the retired-gap veto safe, asserted where it is used.          The** (1 connections) — `app/tests/test_execution_rebuild.py`
- **Deleting the risk.TFS filter must fail something.** (1 connections) — `app/tests/test_execution_rebuild.py`
- **Otherwise every fresh setup reads as missing until its next bar.** (1 connections) — `app/tests/test_execution_rebuild.py`

## Relationships

- [Live Scanner Loop](Live_Scanner_Loop.md) (1 shared connections)

## Source Files

- `app/tests/test_execution_rebuild.py`

## Audit Trail

- EXTRACTED: 79 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*