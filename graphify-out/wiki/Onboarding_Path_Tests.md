# Onboarding Path Tests

> 31 nodes

## Key Concepts

- **RunRecorder** (48 connections) — `app/engine/runlog.py`
- **runlog.py** (24 connections) — `app/engine/runlog.py`
- **regime.py** (10 connections) — `app/engine/regime.py`
- **TestPipelineContracts** (9 connections) — `app/tests/test_pipeline_quality.py`
- **test_pipeline_quality.py** (8 connections) — `app/tests/test_pipeline_quality.py`
- **TestOnboardingIsNotAFailure** (6 connections) — `app/tests/test_pipeline_quality.py`
- **basis.py** (4 connections) — `app/engine/basis.py`
- **run()** (3 connections) — `app/engine/basis.py`
- **run()** (3 connections) — `app/engine/regime.py`
- **._fingerprint()** (3 connections) — `app/engine/runlog.py`
- **.__exit__()** (3 connections) — `app/engine/runlog.py`
- **.candle_at()** (3 connections) — `app/tests/test_pipeline_quality.py`
- **.test_freshly_imported_history_is_lag_not_missing()** (3 connections) — `app/tests/test_pipeline_quality.py`
- **TestStrategyRulesRemainFrozen** (3 connections) — `app/tests/test_pipeline_quality.py`
- **_classify()** (2 connections) — `app/engine/regime.py`
- **.__enter__()** (2 connections) — `app/engine/runlog.py`
- **.test_long_unaggregated_history_still_blocks()** (2 connections) — `app/tests/test_pipeline_quality.py`
- **.test_run_recorder_carries_lineage_envelope()** (2 connections) — `app/tests/test_pipeline_quality.py`
- **Cross-venue basis — the spread between where you trade and where depth is.  algo** (1 connections) — `app/engine/basis.py`
- **Record the close-to-close basis for one (symbol, tf) series.      Facts key on t** (1 connections) — `app/engine/basis.py`
- **Regime engine — market-state classification from structure facts. algo regime-v** (1 connections) — `app/engine/regime.py`
- **.__init__()** (1 connections) — `app/engine/runlog.py`
- **Run logging — every engine invocation is recorded (file log + engine_runs table)** (1 connections) — `app/engine/runlog.py`
- **Context manager: times an engine run and records it on exit.** (1 connections) — `app/engine/runlog.py`
- **.test_fact_causality_violation_is_visible()** (1 connections) — `app/tests/test_pipeline_quality.py`
- *... and 6 more nodes in this community*

## Relationships

- [t](t.md) (10 shared connections)
- [Indicator Engines](Indicator_Engines.md) (9 shared connections)
- [TestMarketQuality](TestMarketQuality.md) (8 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (7 shared connections)
- [Chart Vendor Chart API](Chart_Vendor_Chart_API.md) (4 shared connections)
- [_facts](_facts.md) (4 shared connections)
- [cycles.py](cycles.py.md) (3 shared connections)
- [Confound Guard Tests](Confound_Guard_Tests.md) (3 shared connections)
- [zt](zt.md) (3 shared connections)
- [volatility.py](volatility.py.md) (3 shared connections)
- [volume.py](volume.py.md) (3 shared connections)
- [scan_symbols](scan_symbols.md) (2 shared connections)

## Source Files

- `app/engine/basis.py`
- `app/engine/regime.py`
- `app/engine/runlog.py`
- `app/tests/test_pipeline_quality.py`

## Audit Trail

- EXTRACTED: 137 (91%)
- INFERRED: 14 (9%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*