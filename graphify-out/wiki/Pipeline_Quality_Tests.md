# Pipeline Quality Tests

> 23 nodes

## Key Concepts

- **QualityStoreCase** (9 connections) — `app/tests/test_pipeline_quality.py`
- **TestKillSwitchRungs** (8 connections) — `app/tests/test_pipeline_quality.py`
- **test_pipeline_quality.py** (7 connections) — `app/tests/test_pipeline_quality.py`
- **TestPipelineContracts** (7 connections) — `app/tests/test_pipeline_quality.py`
- **TestMarketQuality** (6 connections) — `app/tests/test_pipeline_quality.py`
- **.candle()** (4 connections) — `app/tests/test_pipeline_quality.py`
- **.complete_market()** (4 connections) — `app/tests/test_pipeline_quality.py`
- **TestStrategyRulesRemainFrozen** (3 connections) — `app/tests/test_pipeline_quality.py`
- **.test_complete_aggregates_reconcile()** (2 connections) — `app/tests/test_pipeline_quality.py`
- **.test_gap_blocks_downstream_engines()** (2 connections) — `app/tests/test_pipeline_quality.py`
- **.test_aggregate_mismatch_is_blocking()** (2 connections) — `app/tests/test_pipeline_quality.py`
- **.test_run_recorder_carries_lineage_envelope()** (2 connections) — `app/tests/test_pipeline_quality.py`
- **.test_stale_series_routes_to_quarantine_not_halt()** (2 connections) — `app/tests/test_pipeline_quality.py`
- **.setUp()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **.tearDown()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **.test_fact_causality_violation_is_visible()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **.test_equity_summary_must_reconcile_to_ledger()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **.test_quality_history_is_persisted()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **.test_code_rung_is_the_watchdog_dispatch_table()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **.test_halt_codes_carry_halt_rung()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **.test_persisted_checks_include_rung_column()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **.test_observability_did_not_change_strategy_constants()** (1 connections) — `app/tests/test_pipeline_quality.py`
- **Every _issue() code declares its watchdog dispatch rung. This coverage     test** (1 connections) — `app/tests/test_pipeline_quality.py`

## Relationships

- [Bias, Trend & Setups](Bias%2C_Trend_%26_Setups.md) (6 shared connections)
- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (1 shared connections)
- [Retired Symbol Staleness Tests](Retired_Symbol_Staleness_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_pipeline_quality.py`

## Audit Trail

- EXTRACTED: 62 (91%)
- INFERRED: 6 (9%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*