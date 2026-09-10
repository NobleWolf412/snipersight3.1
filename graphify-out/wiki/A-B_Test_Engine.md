# A/B Test Engine

> 49 nodes

## Key Concepts

- **abtest.py** (19 connections) — `app/engine/abtest.py`
- **importer.py** (10 connections) — `app/engine/importer.py`
- **run_variant()** (9 connections) — `app/engine/abtest.py`
- **strategygrade.py** (8 connections) — `app/engine/strategygrade.py`
- **report()** (7 connections) — `app/engine/abtest.py`
- **all_tracked_symbols()** (7 connections) — `app/engine/universe.py`
- **_simulate()** (6 connections) — `app/engine/abtest.py`
- **by_strategy()** (6 connections) — `app/engine/abtest.py`
- **calibrate()** (6 connections) — `app/engine/abtest.py`
- **_Pos** (5 connections) — `app/engine/abtest.py`
- **grade()** (5 connections) — `app/engine/strategygrade.py`
- **_fetch_rows()** (4 connections) — `app/engine/importer.py`
- **backfill()** (4 connections) — `app/engine/importer.py`
- **recorded_entry_model()** (4 connections) — `app/engine/abtest.py`
- **_fetch()** (3 connections) — `app/engine/importer.py`
- **native_tfs()** (3 connections) — `app/engine/importer.py`
- **_leg_r()** (3 connections) — `app/engine/abtest.py`
- **_load_setups()** (3 connections) — `app/engine/abtest.py`
- **_cluster_bootstrap()** (3 connections) — `app/engine/abtest.py`
- **summarise()** (3 connections) — `app/engine/abtest.py`
- **_verdict()** (3 connections) — `app/engine/abtest.py`
- **_holm()** (3 connections) — `app/engine/strategygrade.py`
- **main()** (3 connections) — `app/engine/strategygrade.py`
- **acknowledged_gaps()** (2 connections) — `app/engine/importer.py`
- **_iso()** (2 connections) — `app/engine/importer.py`
- *... and 24 more nodes in this community*

## Relationships

- [t](t.md) (3 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (2 shared connections)
- [Kraken Adapter](Kraken_Adapter.md) (1 shared connections)
- [Chart Vendor Price Scale Formatting](Chart_Vendor_Price_Scale_Formatting.md) (1 shared connections)
- [Chart Vendor Chart API](Chart_Vendor_Chart_API.md) (1 shared connections)
- [T](T_2.md) (1 shared connections)

## Source Files

- `app/engine/abtest.py`
- `app/engine/importer.py`
- `app/engine/strategygrade.py`
- `app/engine/universe.py`

## Audit Trail

- EXTRACTED: 158 (99%)
- INFERRED: 1 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*