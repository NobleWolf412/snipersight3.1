# Fact Store & Migrations

> 43 nodes

## Key Concepts

- **store.py** (15 connections) — `app/engine/store.py`
- **_Connection** (13 connections) — `app/tests/test_live_clock.py`
- **stockstore.py** (6 connections) — `app/engine/stockstore.py`
- **test_live_clock.py** (5 connections) — `app/tests/test_live_clock.py`
- **insert_fact()** (5 connections) — `app/engine/store.py`
- **_require_scope()** (4 connections) — `app/engine/stockstore.py`
- **connect()** (4 connections) — `app/engine/store.py`
- **_migrate()** (4 connections) — `app/engine/store.py`
- **_Rows** (3 connections) — `app/tests/test_live_clock.py`
- **LiveClockContract** (3 connections) — `app/tests/test_live_clock.py`
- **current_run_id()** (3 connections) — `app/engine/runlog.py`
- **connect()** (3 connections) — `app/engine/stockstore.py`
- **insert_fact()** (3 connections) — `app/engine/stockstore.py`
- **insert_candle()** (3 connections) — `app/engine/stockstore.py`
- **insert_paper_event()** (3 connections) — `app/engine/stockstore.py`
- **checkpoint_wal()** (3 connections) — `app/engine/store.py`
- **get_active_baseline()** (3 connections) — `app/engine/store.py`
- **start_baseline()** (3 connections) — `app/engine/store.py`
- **canonical_payload()** (3 connections) — `app/engine/store.py`
- **record_manifest()** (3 connections) — `app/engine/store.py`
- **get_facts()** (3 connections) — `app/engine/store.py`
- **.execute()** (2 connections) — `app/tests/test_live_clock.py`
- **.test_cycle_passes_its_opening_clock_to_the_importer()** (2 connections) — `app/tests/test_live_clock.py`
- **.test_cycle_imports_an_unresolved_trade_after_universe_removal()** (2 connections) — `app/tests/test_live_clock.py`
- **fact_hash()** (2 connections) — `app/engine/store.py`
- *... and 18 more nodes in this community*

## Relationships

- [Live Scanner Loop](Live_Scanner_Loop.md) (1 shared connections)
- [Onboarding Path Tests](Onboarding_Path_Tests.md) (1 shared connections)

## Source Files

- `app/engine/runlog.py`
- `app/engine/stockstore.py`
- `app/engine/store.py`
- `app/tests/test_live_clock.py`

## Audit Trail

- EXTRACTED: 122 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*