# Scanner Alert Isolation Tests

> 8 nodes

## Key Concepts

- **test_alerts.py** (11 connections) — `app/tests/test_alerts.py`
- **TheScannerMustNotSend** (3 connections) — `app/tests/test_alerts.py`
- **.test_enqueue_opens_no_socket_and_spawns_nothing()** (2 connections) — `app/tests/test_alerts.py`
- **TheShadowBookIsNeverAnnounced** (2 connections) — `app/tests/test_alerts.py`
- **.test_the_watchdog_reads_only_risk_and_the_operators_own_trades()** (2 connections) — `app/tests/test_alerts.py`
- **Alerts, and the two ways they have historically gone wrong.  They killed the s** (1 connections) — `app/tests/test_alerts.py`
- **Pinned by substitution rather than by reading the source: anything         that** (1 connections) — `app/tests/test_alerts.py`
- **`exec` and `order` are the engine's simulation — 100-400 events a         day f** (1 connections) — `app/tests/test_alerts.py`

## Relationships

- [Toast Flag Tests](Toast_Flag_Tests.md) (3 shared connections)
- [Notification Delivery](Notification_Delivery.md) (1 shared connections)
- [Alert Idempotency Tests](Alert_Idempotency_Tests.md) (1 shared connections)
- [Remote Alert Sink Tests](Remote_Alert_Sink_Tests.md) (1 shared connections)
- [Heartbeat Assertion Tests](Heartbeat_Assertion_Tests.md) (1 shared connections)
- [Supervisor Announce Tests](Supervisor_Announce_Tests.md) (1 shared connections)
- [Toast Sink Tests](Toast_Sink_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_alerts.py`

## Audit Trail

- EXTRACTED: 23 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*