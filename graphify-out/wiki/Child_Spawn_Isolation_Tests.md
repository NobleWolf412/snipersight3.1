# Child Spawn Isolation Tests

> 8 nodes

## Key Concepts

- **TestChildSpawnIsolation** (6 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_the_scanner_does_not_spawn_toasts()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_the_supervisor_still_notifies()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_children_are_spawned_in_their_own_group_and_console()** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_toasts_can_be_put_back_for_testing()** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **Both children were dying together, unattributed, while the supervisor     surviv** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **Every toast spawns PowerShell, and the scanner's deaths land on toast         si** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **The operator must still be told. The watchdog toasts on restarts and         aud** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`

## Relationships

- [Watchdog Audit Cadence Tests](Watchdog_Audit_Cadence_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_watchdog_rung_dispatch.py`

## Audit Trail

- EXTRACTED: 15 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*