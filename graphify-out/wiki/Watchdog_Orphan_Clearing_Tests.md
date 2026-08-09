# Watchdog Orphan Clearing Tests

> 12 nodes

## Key Concepts

- **TestOrphanClearing** (10 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **._query()** (6 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_a_supervised_child_is_never_cleared()** (3 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_a_leftover_scanner_is_found()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_this_process_is_never_its_own_orphan()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_unrelated_python_is_left_alone()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_startup_clears_before_spawning()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_clearing_survives_a_failing_taskkill()** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **watchdog.log records 8 starts and 1 clean stop. Seven supervisors died     witho** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **Stub the query's OUTPUT only. These cover the filtering rules; the         test** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **The takeover path clears orphans while this supervisor already has a         sca** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **Order matters: clearing after spawning would kill the new scanner.** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`

## Relationships

- [Watchdog Audit Cadence Tests](Watchdog_Audit_Cadence_Tests.md) (1 shared connections)
- [Chart Vendor Grid & Axis](Chart_Vendor_Grid_%26_Axis.md) (1 shared connections)

## Source Files

- `app/tests/test_watchdog_rung_dispatch.py`

## Audit Trail

- EXTRACTED: 32 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*