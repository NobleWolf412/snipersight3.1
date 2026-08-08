# Watchdog Kill Attribution Tests

> 11 nodes

## Key Concepts

- **test_watchdog_rung_dispatch.py** (12 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **TestTakeoverHysteresis** (5 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **TestKillAttribution** (4 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_an_audit_restart_is_attributed()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_a_death_we_did_not_cause_stays_unattributed()** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_probe_timeout_exceeds_the_measured_endpoint()** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_takeover_needs_repeated_misses()** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_grace_covers_the_slowest_measured_cycle()** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **Watchdog dispatches by Kill-Switch rung, not by hardcoded code lists — so every** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **rc=1 looks identical whether this supervisor sent the terminate or     something** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **`server_up()` probed with a 3s timeout an endpoint measured at 6.9s under     a** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`

## Relationships

- [Watchdog Audit Cadence Tests](Watchdog_Audit_Cadence_Tests.md) (3 shared connections)
- [Watchdog Restart Dispatch Tests](Watchdog_Restart_Dispatch_Tests.md) (2 shared connections)
- [Watchdog Child Capture Tests](Watchdog_Child_Capture_Tests.md) (1 shared connections)
- [Child Spawn Isolation Tests](Child_Spawn_Isolation_Tests.md) (1 shared connections)
- [Watchdog Orphan Clearing Tests](Watchdog_Orphan_Clearing_Tests.md) (1 shared connections)
- [Watchdog Quarantine Persistence Tests](Watchdog_Quarantine_Persistence_Tests.md) (1 shared connections)
- [Watchdog Supervisor](Watchdog_Supervisor.md) (1 shared connections)

## Source Files

- `app/tests/test_watchdog_rung_dispatch.py`

## Audit Trail

- EXTRACTED: 30 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*