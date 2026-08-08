# Live Scanner Loop

> 17 nodes

## Key Concepts

- **live.py** (17 connections) — `app/live.py`
- **main()** (9 connections) — `app/live.py`
- **refresh_universe()** (4 connections) — `app/live.py`
- **cycle()** (4 connections) — `app/live.py`
- **announceable()** (4 connections) — `app/live.py`
- **_exit_note()** (3 connections) — `app/live.py`
- **install_exit_forensics()** (3 connections) — `app/live.py`
- **next_wake()** (3 connections) — `app/live.py`
- **repair_short_history()** (3 connections) — `app/live.py`
- **check_drift()** (2 connections) — `app/live.py`
- **announce()** (2 connections) — `app/live.py`
- **Forward paper loop — the scanner running live.  Wakes are aligned to the candl** (1 connections) — `app/live.py`
- **Seconds to sleep so the next wake serves both masters.      Lands on whichever** (1 connections) — `app/live.py`
- **Hourly: re-rank live, onboard newly-admitted symbols (backfill+engines).** (1 connections) — `app/live.py`
- **Hourly: re-import timeframes a PARTIAL onboard left short.      The onboarding** (1 connections) — `app/live.py`
- **Run one scan pass.      `beat` is an optional progress callback invoked at eac** (1 connections) — `app/live.py`
- **Which new setup facts deserve to interrupt the operator. THE filter.      Extr** (1 connections) — `app/live.py`

## Relationships

- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (2 shared connections)
- [Notification Delivery](Notification_Delivery.md) (1 shared connections)
- [Boundary Wake Grid Tests](Boundary_Wake_Grid_Tests.md) (1 shared connections)
- [Notification Tests](Notification_Tests.md) (1 shared connections)
- [Onboarding Announce Tests](Onboarding_Announce_Tests.md) (1 shared connections)
- [Shared Pipeline Loop Tests](Shared_Pipeline_Loop_Tests.md) (1 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (1 shared connections)

## Source Files

- `app/live.py`

## Audit Trail

- EXTRACTED: 58 (97%)
- INFERRED: 2 (3%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*