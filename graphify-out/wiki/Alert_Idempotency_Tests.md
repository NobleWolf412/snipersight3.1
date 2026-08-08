# Alert Idempotency Tests

> 8 nodes

## Key Concepts

- **EnqueueIsCheapAndIdempotent** (7 connections) — `app/tests/test_alerts.py`
- **.test_a_replayed_kill_switch_does_not_re_alarm()** (3 connections) — `app/tests/test_alerts.py`
- **._pending()** (3 connections) — `app/tests/test_alerts.py`
- **.test_distinct_days_are_distinct_events()** (2 connections) — `app/tests/test_alerts.py`
- **.test_enqueue_never_raises_at_the_caller()** (2 connections) — `app/tests/test_alerts.py`
- **.test_the_same_event_queues_once()** (1 connections) — `app/tests/test_alerts.py`
- **The real shape of the bug: same day, same baseline, different P&L         becau** (1 connections) — `app/tests/test_alerts.py`
- **It is called from the scan loop. A notification must never be able         to t** (1 connections) — `app/tests/test_alerts.py`

## Relationships

- [Scanner Alert Isolation Tests](Scanner_Alert_Isolation_Tests.md) (1 shared connections)
- [Toast Flag Tests](Toast_Flag_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_alerts.py`

## Audit Trail

- EXTRACTED: 20 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*