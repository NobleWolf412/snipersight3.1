# Toast Flag Tests

> 7 nodes

## Key Concepts

- **QueueCase** (8 connections) — `app/tests/test_alerts.py`
- **TheToastFlagGatesOnlyTheToast** (5 connections) — `app/tests/test_alerts.py`
- **.setUp()** (1 connections) — `app/tests/test_alerts.py`
- **.tearDown()** (1 connections) — `app/tests/test_alerts.py`
- **.test_the_flag_does_not_stop_an_event_being_recorded()** (1 connections) — `app/tests/test_alerts.py`
- **.test_the_flag_is_checked_in_the_toast_sink_only()** (1 connections) — `app/tests/test_alerts.py`
- **SNIPERSIGHT_NO_TOAST=1 is set on the scanner by the supervisor.      Hoisted i** (1 connections) — `app/tests/test_alerts.py`

## Relationships

- [Scanner Alert Isolation Tests](Scanner_Alert_Isolation_Tests.md) (3 shared connections)
- [Alert Idempotency Tests](Alert_Idempotency_Tests.md) (1 shared connections)
- [Remote Alert Sink Tests](Remote_Alert_Sink_Tests.md) (1 shared connections)
- [Toast Sink Tests](Toast_Sink_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_alerts.py`

## Audit Trail

- EXTRACTED: 18 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*