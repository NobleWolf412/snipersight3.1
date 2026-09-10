# Live Scanner Loop

> 21 nodes

## Key Concepts

- **live.py** (22 connections) — `app/live.py`
- **main()** (8 connections) — `app/live.py`
- **cycle()** (5 connections) — `app/live.py`
- **refresh_universe()** (4 connections) — `app/live.py`
- **_exit_note()** (3 connections) — `app/live.py`
- **install_exit_forensics()** (3 connections) — `app/live.py`
- **next_wake()** (3 connections) — `app/live.py`
- **repair_short_history()** (3 connections) — `app/live.py`
- **execution_rebuild_work()** (3 connections) — `app/live.py`
- **announceable()** (3 connections) — `app/live.py`
- **test_execution_rebuild.py** (3 connections) — `app/tests/test_execution_rebuild.py`
- **check_drift()** (2 connections) — `app/live.py`
- **announce()** (2 connections) — `app/live.py`
- **Forward paper loop — the scanner running live.  Wakes are aligned to the candl** (1 connections) — `app/live.py`
- **Seconds to sleep so the next wake serves both masters.      Lands on whichever** (1 connections) — `app/live.py`
- **Hourly: re-rank live, onboard newly-admitted symbols (backfill+engines).** (1 connections) — `app/live.py`
- **Hourly: re-import timeframes a PARTIAL onboard left short.      The onboarding** (1 connections) — `app/live.py`
- **Plans risk can reserve but an order-only recovery pass cannot discover.      U** (1 connections) — `app/live.py`
- **Run one scan pass.      `beat` is an optional progress callback invoked at eac** (1 connections) — `app/live.py`
- **Which new setup facts deserve to interrupt the operator. THE filter.      Extr** (1 connections) — `app/live.py`
- **A retired market must not strand the sole paper slot after an upgrade.  All wr** (1 connections) — `app/tests/test_execution_rebuild.py`

## Relationships

- [Chart Vendor Price Scale Formatting](Chart_Vendor_Price_Scale_Formatting.md) (1 shared connections)
- [Onboarding Path Tests](Onboarding_Path_Tests.md) (1 shared connections)
- [Watchdog Supervisor](Watchdog_Supervisor.md) (1 shared connections)
- [Boundary Wake Grid Tests](Boundary_Wake_Grid_Tests.md) (1 shared connections)
- [Fact Store & Migrations](Fact_Store_%26_Migrations.md) (1 shared connections)
- [Notification Tests](Notification_Tests.md) (1 shared connections)
- [Onboarding Announce Tests](Onboarding_Announce_Tests.md) (1 shared connections)
- [test_pipeline_gates.py](test_pipeline_gates.py.md) (1 shared connections)
- [Version Cascade Lockfile](Version_Cascade_Lockfile.md) (1 shared connections)
- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (1 shared connections)

## Source Files

- `app/live.py`
- `app/tests/test_execution_rebuild.py`

## Audit Trail

- EXTRACTED: 72 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*