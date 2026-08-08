# Heartbeat Assertion Tests

> 5 nodes

## Key Concepts

- **TheHeartbeatAssertsTheStack** (4 connections) — `app/tests/test_alerts.py`
- **.test_an_unreadable_heartbeat_file_does_not_claim_health()** (2 connections) — `app/tests/test_alerts.py`
- **.test_the_ping_is_withheld_when_the_scanner_is_dark()** (1 connections) — `app/tests/test_alerts.py`
- **Silence is the signal, so the ping must mean more than "I am running".      Th** (1 connections) — `app/tests/test_alerts.py`
- **A monitor that cannot read its input must not declare either         verdict —** (1 connections) — `app/tests/test_alerts.py`

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