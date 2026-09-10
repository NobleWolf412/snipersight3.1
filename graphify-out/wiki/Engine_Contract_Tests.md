# Engine Contract Tests

> 58 nodes

## Key Concepts

- **insert_candle()** (16 connections) — `app/tests/test_engine_contracts.py`
- **TestAggregator** (14 connections) — `app/tests/test_engine_contracts.py`
- **test_engine_contracts.py** (11 connections) — `app/tests/test_engine_contracts.py`
- **._acknowledge()** (10 connections) — `app/tests/test_engine_contracts.py`
- **TestImporter** (8 connections) — `app/tests/test_engine_contracts.py`
- **validate.py** (8 connections) — `app/validate.py`
- **EngineStoreCase** (7 connections) — `app/tests/test_engine_contracts.py`
- **.test_acknowledged_partial_bucket_builds()** (4 connections) — `app/tests/test_engine_contracts.py`
- **.test_quarantined_acknowledgment_is_ignored()** (4 connections) — `app/tests/test_engine_contracts.py`
- **.test_counted_but_unlisted_gap_blocks()** (4 connections) — `app/tests/test_engine_contracts.py`
- **.test_rejected_candle_row_acknowledges_nothing()** (4 connections) — `app/tests/test_engine_contracts.py`
- **.test_misaligned_extra_candle_blocks_the_bucket()** (4 connections) — `app/tests/test_engine_contracts.py`
- **.test_late_candle_rewrite_is_loud()** (4 connections) — `app/tests/test_engine_contracts.py`
- **.test_partial_developing_bucket_never_emits()** (4 connections) — `app/tests/test_engine_contracts.py`
- **.test_acknowledged_partial_week_builds()** (4 connections) — `app/tests/test_engine_contracts.py`
- **TestSwingCausality** (4 connections) — `app/tests/test_engine_contracts.py`
- **main()** (4 connections) — `app/validate.py`
- **.test_gap_prevents_aggregate()** (3 connections) — `app/tests/test_engine_contracts.py`
- **.test_pre_listing_window_stays_unbuilt()** (3 connections) — `app/tests/test_engine_contracts.py`
- **.test_empty_answer_after_listing_acknowledges_the_quiet_window()** (3 connections) — `app/tests/test_engine_contracts.py`
- **.test_served_window_with_omitted_head_after_listing_acknowledges_the_head()** (3 connections) — `app/tests/test_engine_contracts.py`
- **._series()** (3 connections) — `app/tests/test_engine_contracts.py`
- **TestStructureBreaks** (3 connections) — `app/tests/test_engine_contracts.py`
- **TestLiquidityCanonicalization** (3 connections) — `app/tests/test_engine_contracts.py`
- **stats()** (3 connections) — `app/validate.py`
- *... and 33 more nodes in this community*

## Relationships

- [Kraken Adapter](Kraken_Adapter.md) (1 shared connections)
- [Chart Vendor Price Scale Formatting](Chart_Vendor_Price_Scale_Formatting.md) (1 shared connections)

## Source Files

- `app/tests/test_engine_contracts.py`
- `app/validate.py`

## Audit Trail

- EXTRACTED: 182 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*