# Universe & Rate Limiting

> 52 nodes

## Key Concepts

- **get_logger()** (38 connections) — `app/engine/runlog.py`
- **universe.py** (20 connections) — `app/engine/universe.py`
- **importer.py** (9 connections) — `app/engine/importer.py`
- **rank_by_volume()** (7 connections) — `app/engine/universe.py`
- **refresh()** (7 connections) — `app/engine/universe.py`
- **rank_all_venues()** (6 connections) — `app/engine/universe.py`
- **aggregator.py** (5 connections) — `app/engine/aggregator.py`
- **_fetch_rows()** (5 connections) — `app/engine/importer.py`
- **backfill()** (5 connections) — `app/engine/importer.py`
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
- **manual_arm()** (3 connections) — `app/server.py`
- **manual_cancel()** (3 connections) — `app/server.py`
- **post_settings()** (3 connections) — `app/server.py`
- **_bucket_start()** (2 connections) — `app/engine/aggregator.py`
- **acknowledged_gaps()** (2 connections) — `app/engine/importer.py`
- *... and 27 more nodes in this community*

## Relationships

- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (9 shared connections)
- [Chart Vendor Marker Rendering](Chart_Vendor_Marker_Rendering.md) (4 shared connections)
- [API Server Endpoints](API_Server_Endpoints.md) (3 shared connections)
- [A/B Test Engine](A-B_Test_Engine.md) (2 shared connections)
- [binance.py](binance.py.md) (2 shared connections)
- [Shell Navigation & Near Levels](Shell_Navigation_%26_Near_Levels.md) (2 shared connections)
- [Kraken Adapter](Kraken_Adapter.md) (2 shared connections)
- [_facts](_facts.md) (2 shared connections)
- [Chart Vendor Data Layer](Chart_Vendor_Data_Layer.md) (2 shared connections)
- [Portfolio & Position Endpoints](Portfolio_%26_Position_Endpoints.md) (2 shared connections)
- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (2 shared connections)
- [volume.py](volume.py.md) (1 shared connections)

## Source Files

- `app/engine/aggregator.py`
- `app/engine/importer.py`
- `app/engine/runlog.py`
- `app/engine/universe.py`
- `app/server.py`

## Audit Trail

- EXTRACTED: 172 (92%)
- INFERRED: 14 (8%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*