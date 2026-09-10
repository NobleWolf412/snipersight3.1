# TestMarketQuality

> 31 nodes

## Key Concepts

- **TestMarketQuality** (15 connections) — `app/tests/test_pipeline_quality.py`
- **QualityStoreCase** (10 connections) — `app/tests/test_pipeline_quality.py`
- **.candle()** (8 connections) — `app/tests/test_pipeline_quality.py`
- **._partial_market()** (8 connections) — `app/tests/test_pipeline_quality.py`
- **TestKillSwitchRungs** (8 connections) — `app/tests/test_pipeline_quality.py`
- **.complete_market()** (4 connections) — `app/tests/test_pipeline_quality.py`
- **.test_retried_empty_tail_does_not_multiply_known_gap_budget()** (3 connections) — `app/tests/test_pipeline_quality.py`
- **.test_acknowledged_partial_bar_reconciles()** (3 connections) — `app/tests/test_pipeline_quality.py`
- **.test_corrupted_partial_bar_is_blocking()** (3 connections) — `app/tests/test_pipeline_quality.py`
- **.test_unemitted_partial_bucket_flags_without_blocking()** (3 connections) — `app/tests/test_pipeline_quality.py`
- **.test_unknown_timeframe_is_quarantine_not_halt()** (3 connections) — `app/tests/test_pipeline_quality.py`
- **.test_unacknowledged_partial_stays_outside_the_mirror()** (3 connections) — `app/tests/test_pipeline_quality.py`
- **.test_complete_aggregates_reconcile()** (2 connections) — `app/tests/test_pipeline_quality.py`
- **.test_gap_blocks_downstream_engines()** (2 connections) — `app/tests/test_pipeline_quality.py`
- **.test_final_candle_does_not_erase_prior_gap_acknowledgements()** (2 connections) — `app/tests/test_pipeline_quality.py`
- **.test_aggregate_mismatch_is_blocking()** (2 connections) — `app/tests/test_pipeline_quality.py`
- **.test_acknowledged_gap_is_a_note_not_a_warning()** (2 connections) — `app/tests/test_pipeline_quality.py`
- **.test_stale_series_routes_to_quarantine_not_halt()** (2 connections) — `app/tests/test_pipeline_quality.py`
- **.setUp()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **.tearDown()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **.test_code_rung_is_the_watchdog_dispatch_table()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **.test_halt_codes_carry_halt_rung()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **.test_persisted_checks_include_rung_column()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **A quiet market retries from the same last candle every cycle.          The 1-g** (1 connections) — `app/tests/test_pipeline_quality.py`
- **Three of four hours traded; 02:00 the venue served nothing for.          range** (1 connections) — `app/tests/test_pipeline_quality.py`
- *... and 6 more nodes in this community*

## Relationships

- [Onboarding Path Tests](Onboarding_Path_Tests.md) (8 shared connections)

## Source Files

- `app/tests/test_pipeline_quality.py`

## Audit Trail

- EXTRACTED: 93 (97%)
- INFERRED: 3 (3%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*