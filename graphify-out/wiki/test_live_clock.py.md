# test_live_clock.py

> 18 nodes

## Key Concepts

- **_Connection** (8 connections) — `app/tests/test_live_clock.py`
- **connect()** (5 connections) — `app/engine/store.py`
- **test_live_clock.py** (5 connections) — `app/tests/test_live_clock.py`
- **_migrate()** (4 connections) — `app/engine/store.py`
- **checkpoint_wal()** (3 connections) — `app/engine/store.py`
- **get_active_baseline()** (3 connections) — `app/engine/store.py`
- **start_baseline()** (3 connections) — `app/engine/store.py`
- **_Rows** (3 connections) — `app/tests/test_live_clock.py`
- **.test_cycle_passes_its_opening_clock_to_the_importer()** (3 connections) — `app/tests/test_live_clock.py`
- **.execute()** (2 connections) — `app/tests/test_live_clock.py`
- **LiveClockContract** (2 connections) — `app/tests/test_live_clock.py`
- **Path** (1 connections)
- **Reclaim the write-ahead log. Safe to call whenever; never raises.      Call th** (1 connections) — `app/engine/store.py`
- **Small explicit migration runner; every schema change is recorded.** (1 connections) — `app/engine/store.py`
- **Return the active forward-test window without mutating legacy stores.** (1 connections) — `app/engine/store.py`
- **Start a new non-destructive research window and retain all prior facts.** (1 connections) — `app/engine/store.py`
- **.fetchone()** (1 connections) — `app/tests/test_live_clock.py`
- **A live scan has one clock snapshot from import through quality.  The scan takes** (1 connections) — `app/tests/test_live_clock.py`

## Relationships

- [Fact Store & Migrations](Fact_Store_%26_Migrations.md) (5 shared connections)
- [Facts Window Tests](Facts_Window_Tests.md) (1 shared connections)
- [Live Scanner Loop](Live_Scanner_Loop.md) (1 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (1 shared connections)

## Source Files

- `app/engine/store.py`
- `app/tests/test_live_clock.py`

## Audit Trail

- EXTRACTED: 46 (96%)
- INFERRED: 2 (4%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*