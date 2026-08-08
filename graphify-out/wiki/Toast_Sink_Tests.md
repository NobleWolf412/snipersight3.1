# Toast Sink Tests

> 8 nodes

## Key Concepts

- **TheToastSinkIsOffUntilAskedFor** (7 connections) — `app/tests/test_alerts.py`
- **.test_an_undelivered_alert_is_not_reported_as_sent()** (2 connections) — `app/tests/test_alerts.py`
- **.test_a_backlog_drains_over_several_ticks()** (2 connections) — `app/tests/test_alerts.py`
- **.test_no_toast_is_spawned_by_default()** (1 connections) — `app/tests/test_alerts.py`
- **.test_it_can_be_turned_back_on_deliberately()** (1 connections) — `app/tests/test_alerts.py`
- **Measured 2026-08-05, on the first live run of this system.      Moving deliver** (1 connections) — `app/tests/test_alerts.py`
- **With the toast off and no remote sink, nobody was told. Saying         otherwis** (1 connections) — `app/tests/test_alerts.py`
- **14 at once is what caused the kill. The queue is durable, so a small         pe** (1 connections) — `app/tests/test_alerts.py`

## Relationships

- [Scanner Alert Isolation Tests](Scanner_Alert_Isolation_Tests.md) (1 shared connections)
- [Toast Flag Tests](Toast_Flag_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_alerts.py`

## Audit Trail

- EXTRACTED: 16 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*