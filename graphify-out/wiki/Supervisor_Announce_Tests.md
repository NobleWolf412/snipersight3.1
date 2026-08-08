# Supervisor Announce Tests

> 5 nodes

## Key Concepts

- **TheSupervisorNeverSpawnsToAnnounce** (4 connections) — `app/tests/test_alerts.py`
- **.test_the_restart_announcement_is_keyed_per_death()** (2 connections) — `app/tests/test_alerts.py`
- **.test_the_watchdog_does_not_call_the_spawning_sink()** (1 connections) — `app/tests/test_alerts.py`
- **The restart loop, and why it ran for 356 exits.      watchdog.toast() called n** (1 connections) — `app/tests/test_alerts.py`
- **Not per tick. A supervisor in a bad patch must report a restart         once, o** (1 connections) — `app/tests/test_alerts.py`

## Relationships

- [Scanner Alert Isolation Tests](Scanner_Alert_Isolation_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_alerts.py`

## Audit Trail

- EXTRACTED: 9 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*