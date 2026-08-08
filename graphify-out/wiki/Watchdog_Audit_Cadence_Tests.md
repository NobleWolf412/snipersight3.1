# Watchdog Audit Cadence Tests

> 14 nodes

## Key Concepts

- **_FakeChild** (11 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **TestAuditCadenceOnSkip** (4 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.kill()** (3 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_a_sustained_quarantine_is_still_reported()** (3 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_db_skip_stamps_at()** (3 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_the_real_scan_can_actually_see_a_process()** (3 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **._run()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_import_skip_stamps_at()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.__init__()** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.alive()** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **Mirrors Child.kill: records our own hand, then terminates. The         attributi** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **Not restarting must not mean not telling. The operator still needs to         kn** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **Skip returns (import or db) must still stamp `at` so cadence stays 60s     inste** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **NOT mocked, deliberately.          The first version of _orphans() shelled out t** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`

## Relationships

- [Watchdog Kill Attribution Tests](Watchdog_Kill_Attribution_Tests.md) (3 shared connections)
- [Watchdog Restart Dispatch Tests](Watchdog_Restart_Dispatch_Tests.md) (2 shared connections)
- [Watchdog Quarantine Persistence Tests](Watchdog_Quarantine_Persistence_Tests.md) (2 shared connections)
- [Multi-Venue Universe Tests](Multi-Venue_Universe_Tests.md) (1 shared connections)
- [Watchdog Orphan Clearing Tests](Watchdog_Orphan_Clearing_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_watchdog_rung_dispatch.py`

## Audit Trail

- EXTRACTED: 36 (97%)
- INFERRED: 1 (3%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*