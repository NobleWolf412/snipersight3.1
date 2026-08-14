# Fact Store & Migrations

> 16 nodes

## Key Concepts

- **store.py** (15 connections) — `app/engine/store.py`
- **insert_fact()** (5 connections) — `app/engine/store.py`
- **current_run_id()** (3 connections) — `app/engine/runlog.py`
- **canonical_payload()** (3 connections) — `app/engine/store.py`
- **record_manifest()** (3 connections) — `app/engine/store.py`
- **get_facts()** (3 connections) — `app/engine/store.py`
- **fact_hash()** (2 connections) — `app/engine/store.py`
- **candle_cache()** (2 connections) — `app/engine/store.py`
- **get_manifest()** (1 connections) — `app/engine/store.py`
- **get_candles()** (1 connections) — `app/engine/store.py`
- **Row** (1 connections)
- **Fact store — SQLite, append-only facts with full time/version lineage.  Consti** (1 connections) — `app/engine/store.py`
- **Persist an immutable, content-addressed run/config manifest.** (1 connections) — `app/engine/store.py`
- **Append a fact. Returns True if newly inserted, False if it already existed.** (1 connections) — `app/engine/store.py`
- **Serve repeated whole-series candle reads from memory, for one walk.** (1 connections) — `app/engine/store.py`
- **The as_of-cursored query (§5): only facts confirmed at or before as_of.** (1 connections) — `app/engine/store.py`

## Relationships

- [test_live_clock.py](test_live_clock.py.md) (5 shared connections)
- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (1 shared connections)

## Source Files

- `app/engine/runlog.py`
- `app/engine/store.py`

## Audit Trail

- EXTRACTED: 44 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*