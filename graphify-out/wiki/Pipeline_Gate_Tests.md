# Pipeline Gate Tests

> 17 nodes

## Key Concepts

- **GateCase** (14 connections) — `app/tests/test_pipeline_gates.py`
- **.candles()** (8 connections) — `app/tests/test_pipeline_gates.py`
- **.gates()** (6 connections) — `app/tests/test_pipeline_gates.py`
- **.test_the_gate_clears_the_cycle_the_data_arrives()** (4 connections) — `app/tests/test_pipeline_gates.py`
- **.test_a_blocked_symbol_runs_nothing_and_says_why()** (4 connections) — `app/tests/test_pipeline_gates.py`
- **.test_short_history_is_named_but_engines_still_run()** (4 connections) — `app/tests/test_pipeline_gates.py`
- **.test_a_timeframe_with_no_candles_is_skipped_and_named()** (3 connections) — `app/tests/test_pipeline_gates.py`
- **.test_first_seen_survives_a_retrip()** (3 connections) — `app/tests/test_pipeline_gates.py`
- **.test_engine_order_is_module_outer()** (3 connections) — `app/tests/test_pipeline_gates.py`
- **.test_a_broken_detector_cannot_block_the_loop()** (3 connections) — `app/tests/test_pipeline_gates.py`
- **.test_an_unknown_gate_name_raises()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.tearDown()** (1 connections) — `app/tests/test_pipeline_gates.py`
- **Current state, not history: a stale row would keep reporting a hole         the** (1 connections) — `app/tests/test_pipeline_gates.py`
- **NO_DATA since 26 Jul' is the useful sentence; a timestamp that         resets ev** (1 connections) — `app/tests/test_pipeline_gates.py`
- **Load-bearing: scalein's 1H pass reads the HTF facts execsim writes         on 4H** (1 connections) — `app/tests/test_pipeline_gates.py`
- **Blocking on short history would change what the recorded book         contains u** (1 connections) — `app/tests/test_pipeline_gates.py`
- **Gates are minted beside their declaration; drift here is a typo,         not voc** (1 connections) — `app/tests/test_pipeline_gates.py`

## Relationships

- [Multi-Venue Universe Tests](Multi-Venue_Universe_Tests.md) (3 shared connections)
- [Shared Pipeline Loop Tests](Shared_Pipeline_Loop_Tests.md) (2 shared connections)
- [Bias, Trend & Setups](Bias%2C_Trend_%26_Setups.md) (1 shared connections)

## Source Files

- `app/tests/test_pipeline_gates.py`

## Audit Trail

- EXTRACTED: 57 (95%)
- INFERRED: 3 (5%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*