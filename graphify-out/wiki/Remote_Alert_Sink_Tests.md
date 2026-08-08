# Remote Alert Sink Tests

> 10 nodes

## Key Concepts

- **RemoteDeliveryIsOffUntilAskedFor** (8 connections) — `app/tests/test_alerts.py`
- **.test_quiet_events_can_be_withheld_from_a_sink()** (2 connections) — `app/tests/test_alerts.py`
- **.test_ntfy_sends_the_title_once_with_its_symbol()** (2 connections) — `app/tests/test_alerts.py`
- **.test_delivery_records_the_outcome_rather_than_raising()** (2 connections) — `app/tests/test_alerts.py`
- **.test_no_config_means_no_remote_sinks()** (1 connections) — `app/tests/test_alerts.py`
- **.test_a_configured_sink_is_used()** (1 connections) — `app/tests/test_alerts.py`
- **An alert carries the operator's symbol, direction and P&L. Sending that     any** (1 connections) — `app/tests/test_alerts.py`
- **Drift runs 13-44 a day against 2-8 setups and is awareness-only.         Three** (1 connections) — `app/tests/test_alerts.py`
- **The header form sends Title: in an HTTP header, and headers are         ASCII —** (1 connections) — `app/tests/test_alerts.py`
- **An unreachable phone must not stop the local toast, and neither         must st** (1 connections) — `app/tests/test_alerts.py`

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