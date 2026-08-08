# Fact Store & Migrations

> 27 nodes

## Key Concepts

- **store.py** (15 connections) — `app/engine/store.py`
- **connect()** (5 connections) — `app/engine/store.py`
- **Connection** (5 connections)
- **insert_fact()** (5 connections) — `app/engine/store.py`
- **_migrate()** (4 connections) — `app/engine/store.py`
- **current_run_id()** (3 connections) — `app/engine/runlog.py`
- **checkpoint_wal()** (3 connections) — `app/engine/store.py`
- **get_active_baseline()** (3 connections) — `app/engine/store.py`
- **start_baseline()** (3 connections) — `app/engine/store.py`
- **canonical_payload()** (3 connections) — `app/engine/store.py`
- **record_manifest()** (3 connections) — `app/engine/store.py`
- **get_facts()** (3 connections) — `app/engine/store.py`
- **fact_hash()** (2 connections) — `app/engine/store.py`
- **candle_cache()** (2 connections) — `app/engine/store.py`
- **Path** (1 connections)
- **get_manifest()** (1 connections) — `app/engine/store.py`
- **get_candles()** (1 connections) — `app/engine/store.py`
- **Row** (1 connections)
- **Fact store — SQLite, append-only facts with full time/version lineage.  Consti** (1 connections) — `app/engine/store.py`
- **Reclaim the write-ahead log. Safe to call whenever; never raises.      Call th** (1 connections) — `app/engine/store.py`
- **Small explicit migration runner; every schema change is recorded.** (1 connections) — `app/engine/store.py`
- **Return the active forward-test window without mutating legacy stores.** (1 connections) — `app/engine/store.py`
- **Start a new non-destructive research window and retain all prior facts.** (1 connections) — `app/engine/store.py`
- **Persist an immutable, content-addressed run/config manifest.** (1 connections) — `app/engine/store.py`
- **Append a fact. Returns True if newly inserted, False if it already existed.** (1 connections) — `app/engine/store.py`
- *... and 2 more nodes in this community*

## Relationships

- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (1 shared connections)
- [Facts Window Tests](Facts_Window_Tests.md) (1 shared connections)

## Source Files

- `app/engine/runlog.py`
- `app/engine/store.py`

## Audit Trail

- EXTRACTED: 71 (99%)
- INFERRED: 1 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*