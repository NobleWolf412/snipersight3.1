# Watchdog Restart Dispatch Tests

> 17 nodes

## Key Concepts

- **._run()** (12 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **TestWatchdogRungDispatch** (10 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **TestAuditWarmup** (5 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_unknown_timeframe_halt_does_not_restart()** (3 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_mixed_halt_including_healable_code_still_restarts()** (3 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_a_single_quarantine_climb_does_not_restart()** (3 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_halt_finding_restarts_live()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_quarantine_stable_does_not_restart()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_serve_flag_only_does_not_restart()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_clean_report_does_not_restart()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_state_tracks_counts_for_climb_detection()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_warmup_suppresses_quarantine_climb_restart()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_warmup_still_dispatches_halt()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **The 2026-08-08 loop. Candles are keyed (symbol, tf, open_ts) and         the sca** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **The exemption is narrow. If any HALT finding names a code the         scanner CA** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **THE 184-RESTART BUG. One tick of climb used to be a kill.          A scan cycle** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **Warmup seeds prior counts so a first-tick QUARANTINE reading isn't     misread a** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`

## Relationships

- [Watchdog Audit Cadence Tests](Watchdog_Audit_Cadence_Tests.md) (2 shared connections)
- [Chart Vendor Grid & Axis](Chart_Vendor_Grid_%26_Axis.md) (2 shared connections)

## Source Files

- `app/tests/test_watchdog_rung_dispatch.py`

## Audit Trail

- EXTRACTED: 54 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*