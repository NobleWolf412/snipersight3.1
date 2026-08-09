# Watchdog Quarantine Persistence Tests

> 11 nodes

## Key Concepts

- **TestQuarantinePersistence** (9 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **._sequence()** (8 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_a_sustained_climb_does_not_restart_either()** (3 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_a_young_scanner_is_not_killed_mid_cycle()** (3 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_the_observed_recovering_sequence_never_restarts()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_stuck_at_a_high_level_does_not_restart()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_recovery_rearms_the_streak()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **A climb must PERSIST before it counts as a fault.      The whole point is the di** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **Feed consecutive audits and report when a terminate happened.** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **A quarantine NEVER restarts the scanner now. Measured 2026-07-31:              0** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **A cycle needs ~296s. Terminating before that guarantees it never         complet** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`

## Relationships

- [Chart Vendor Grid & Axis](Chart_Vendor_Grid_%26_Axis.md) (2 shared connections)
- [Watchdog Audit Cadence Tests](Watchdog_Audit_Cadence_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_watchdog_rung_dispatch.py`

## Audit Trail

- EXTRACTED: 33 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*