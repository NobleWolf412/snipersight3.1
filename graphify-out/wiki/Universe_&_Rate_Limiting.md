# Universe & Rate Limiting

> 46 nodes

## Key Concepts

- **get_logger()** (31 connections) — `app/engine/runlog.py`
- **universe.py** (20 connections) — `app/engine/universe.py`
- **importer.py** (9 connections) — `app/engine/importer.py`
- **rank_by_volume()** (7 connections) — `app/engine/universe.py`
- **refresh()** (7 connections) — `app/engine/universe.py`
- **backfill()** (6 connections) — `app/engine/importer.py`
- **rank_all_venues()** (6 connections) — `app/engine/universe.py`
- **aggregator.py** (5 connections) — `app/engine/aggregator.py`
- **_fetch_rows()** (5 connections) — `app/engine/importer.py`
- **_RateLimiter** (5 connections) — `app/engine/universe.py`
- **shadow_candidates()** (5 connections) — `app/engine/universe.py`
- **_AuditFilter** (4 connections) — `app/engine/runlog.py`
- **_get()** (4 connections) — `app/engine/universe.py`
- **_base_asset()** (4 connections) — `app/engine/universe.py`
- **scan_symbols()** (4 connections) — `app/engine/universe.py`
- **aggregate()** (3 connections) — `app/engine/aggregator.py`
- **_fetch()** (3 connections) — `app/engine/importer.py`
- **native_tfs()** (3 connections) — `app/engine/importer.py`
- **current_symbols()** (3 connections) — `app/engine/universe.py`
- **shadow_symbols()** (3 connections) — `app/engine/universe.py`
- **_bucket_start()** (2 connections) — `app/engine/aggregator.py`
- **acknowledged_gaps()** (2 connections) — `app/engine/importer.py`
- **_iso()** (2 connections) — `app/engine/importer.py`
- **_is_stable()** (2 connections) — `app/engine/universe.py`
- **.acquire()** (2 connections) — `app/engine/universe.py`
- *... and 21 more nodes in this community*

## Relationships

- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (9 shared connections)
- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (4 shared connections)
- [Chart Vendor Marker Rendering](Chart_Vendor_Marker_Rendering.md) (4 shared connections)
- [A/B Test Engine](A-B_Test_Engine.md) (3 shared connections)
- [binance.py](binance.py.md) (2 shared connections)
- [Kraken Adapter](Kraken_Adapter.md) (2 shared connections)
- [_facts](_facts.md) (2 shared connections)
- [Chart Vendor Data Layer](Chart_Vendor_Data_Layer.md) (2 shared connections)
- [volume.py](volume.py.md) (1 shared connections)
- [test_live_clock.py](test_live_clock.py.md) (1 shared connections)
- [Live Scanner Loop](Live_Scanner_Loop.md) (1 shared connections)
- [Engine Fault Row Tests](Engine_Fault_Row_Tests.md) (1 shared connections)

## Source Files

- `app/engine/aggregator.py`
- `app/engine/importer.py`
- `app/engine/runlog.py`
- `app/engine/universe.py`

## Audit Trail

- EXTRACTED: 163 (97%)
- INFERRED: 5 (3%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*