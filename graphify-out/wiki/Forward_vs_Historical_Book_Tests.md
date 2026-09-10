# Forward vs Historical Book Tests

> 19 nodes

## Key Concepts

- **GateCase** (14 connections) — `app/tests/test_pipeline_gates.py`
- **.candles()** (8 connections) — `app/tests/test_pipeline_gates.py`
- **.gates()** (5 connections) — `app/tests/test_pipeline_gates.py`
- **.test_the_gate_clears_the_cycle_the_data_arrives()** (4 connections) — `app/tests/test_pipeline_gates.py`
- **.test_short_history_is_named_but_engines_still_run()** (4 connections) — `app/tests/test_pipeline_gates.py`
- **.test_a_timeframe_with_no_candles_is_skipped_and_named()** (3 connections) — `app/tests/test_pipeline_gates.py`
- **.test_first_seen_survives_a_retrip()** (3 connections) — `app/tests/test_pipeline_gates.py`
- **.test_engine_order_is_module_outer()** (3 connections) — `app/tests/test_pipeline_gates.py`
- **.test_a_blocked_symbol_runs_nothing_and_says_why()** (3 connections) — `app/tests/test_pipeline_gates.py`
- **.test_onboarding_still_raises_on_a_blocked_symbol()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.test_a_broken_detector_cannot_block_the_loop()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.test_an_unknown_gate_name_raises()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.tearDown()** (1 connections) — `app/tests/test_pipeline_gates.py`
- **Current state, not history: a stale row would keep reporting a hole         the** (1 connections) — `app/tests/test_pipeline_gates.py`
- **NO_DATA since 26 Jul' is the useful sentence; a timestamp that         resets ev** (1 connections) — `app/tests/test_pipeline_gates.py`
- **Load-bearing: scalein's 1H pass reads the HTF facts execsim writes         on 4H** (1 connections) — `app/tests/test_pipeline_gates.py`
- **The loop is shared; the POLICY is not. Onboarding a symbol whose         market** (1 connections) — `app/tests/test_pipeline_gates.py`
- **Blocking on short history would change what the recorded book         contains u** (1 connections) — `app/tests/test_pipeline_gates.py`
- **Gates are minted beside their declaration; drift here is a typo,         not voc** (1 connections) — `app/tests/test_pipeline_gates.py`

## Relationships

- [test_pipeline_gates.py](test_pipeline_gates.py.md) (2 shared connections)

## Source Files

- `app/tests/test_pipeline_gates.py`

## Audit Trail

- EXTRACTED: 60 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*