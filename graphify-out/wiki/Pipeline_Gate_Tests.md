# Pipeline Gate Tests

> 41 nodes

## Key Concepts

- **GateCase** (14 connections) — `app/tests/test_pipeline_gates.py`
- **.candles()** (8 connections) — `app/tests/test_pipeline_gates.py`
- **FaultCase** (8 connections) — `app/tests/test_pipeline_gates.py`
- **test_pipeline_gates.py** (7 connections) — `app/tests/test_pipeline_gates.py`
- **.gates()** (6 connections) — `app/tests/test_pipeline_gates.py`
- **VocabularyCase** (6 connections) — `app/tests/test_pipeline_gates.py`
- **.test_the_gate_clears_the_cycle_the_data_arrives()** (4 connections) — `app/tests/test_pipeline_gates.py`
- **.test_short_history_is_named_but_engines_still_run()** (4 connections) — `app/tests/test_pipeline_gates.py`
- **.faults()** (4 connections) — `app/tests/test_pipeline_gates.py`
- **OneLoopCase** (4 connections) — `app/tests/test_pipeline_gates.py`
- **.test_a_timeframe_with_no_candles_is_skipped_and_named()** (3 connections) — `app/tests/test_pipeline_gates.py`
- **.test_first_seen_survives_a_retrip()** (3 connections) — `app/tests/test_pipeline_gates.py`
- **.test_engine_order_is_module_outer()** (3 connections) — `app/tests/test_pipeline_gates.py`
- **.test_a_blocked_symbol_runs_nothing_and_says_why()** (3 connections) — `app/tests/test_pipeline_gates.py`
- **fake_engine()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.setUp()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.test_onboarding_still_raises_on_a_blocked_symbol()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.test_a_broken_detector_cannot_block_the_loop()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.test_an_unknown_gate_name_raises()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.test_a_throwing_engine_becomes_a_row()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.test_recurrence_counts_and_first_seen_survives()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.test_a_clean_run_clears_the_row()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.tearDown()** (1 connections) — `app/tests/test_pipeline_gates.py`
- **.setUp()** (1 connections) — `app/tests/test_pipeline_gates.py`
- **.tearDown()** (1 connections) — `app/tests/test_pipeline_gates.py`
- *... and 16 more nodes in this community*

## Relationships

- [Live Scanner Loop](Live_Scanner_Loop.md) (1 shared connections)
- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (1 shared connections)

## Source Files

- `app/tests/test_pipeline_gates.py`

## Audit Trail

- EXTRACTED: 111 (99%)
- INFERRED: 1 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*