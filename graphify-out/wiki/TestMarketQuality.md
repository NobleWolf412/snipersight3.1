# TestMarketQuality

> 21 nodes

## Key Concepts

- **TestMarketQuality** (13 connections) — `app/tests/test_pipeline_quality.py`
- **.candle()** (8 connections) — `app/tests/test_pipeline_quality.py`
- **._partial_market()** (7 connections) — `app/tests/test_pipeline_quality.py`
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
- **A quiet market retries from the same last candle every cycle.          The 1-gap** (1 connections) — `app/tests/test_pipeline_quality.py`
- **Three of four hours traded; 02:00 the venue served nothing for.          range** (1 connections) — `app/tests/test_pipeline_quality.py`
- **agg-v0.2's mirror: a partial bar the aggregator was entitled to         build i** (1 connections) — `app/tests/test_pipeline_quality.py`
- **A partial bar that does not reconcile to its present source candles         is** (1 connections) — `app/tests/test_pipeline_quality.py`
- **A qualifying partial bucket the aggregator has not built yet is a         DEGRA** (1 connections) — `app/tests/test_pipeline_quality.py`
- **Pin for the 2026-08-08 restart loop. An unrecognised tf may indict         the** (1 connections) — `app/tests/test_pipeline_quality.py`
- **No acknowledgment -> the aggregator refuses the bucket and the         mirror n** (1 connections) — `app/tests/test_pipeline_quality.py`

## Relationships

- [test_pipeline_quality.py](test_pipeline_quality.py.md) (5 shared connections)

## Source Files

- `app/tests/test_pipeline_quality.py`

## Audit Trail

- EXTRACTED: 65 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*