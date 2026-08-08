# Watchdog Restart Dispatch Tests

> 13 nodes

## Key Concepts

- **._run()** (10 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **TestWatchdogRungDispatch** (8 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **TestAuditWarmup** (5 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_a_single_quarantine_climb_does_not_restart()** (3 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_halt_finding_restarts_live()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_quarantine_stable_does_not_restart()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_serve_flag_only_does_not_restart()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_clean_report_does_not_restart()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_state_tracks_counts_for_climb_detection()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_warmup_suppresses_quarantine_climb_restart()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_warmup_still_dispatches_halt()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **THE 184-RESTART BUG. One tick of climb used to be a kill.          A scan cycle** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **Warmup seeds prior counts so a first-tick QUARANTINE reading isn't     misread a** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`

## Relationships

- [Watchdog Kill Attribution Tests](Watchdog_Kill_Attribution_Tests.md) (2 shared connections)
- [Watchdog Audit Cadence Tests](Watchdog_Audit_Cadence_Tests.md) (2 shared connections)

## Source Files

- `app/tests/test_watchdog_rung_dispatch.py`

## Audit Trail

- EXTRACTED: 42 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*