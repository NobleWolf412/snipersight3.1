# Chart Vendor Number Formatting

> 21 nodes

## Key Concepts

- **notify.py** (16 connections) — `app/notify.py`
- **deliver_pending()** (9 connections) — `app/notify.py`
- **config()** (5 connections) — `app/notify.py`
- **toast()** (4 connections) — `app/notify.py`
- **enqueue()** (4 connections) — `app/notify.py`
- **_send_remote()** (4 connections) — `app/notify.py`
- **toast_enabled()** (4 connections) — `app/notify.py`
- **heartbeat()** (4 connections) — `app/notify.py`
- **event()** (4 connections) — `app/notify.py`
- **_queue()** (3 connections) — `app/notify.py`
- **_xml_escape()** (2 connections) — `app/notify.py`
- **_post()** (2 connections) — `app/notify.py`
- **Alerts: one entry point, several destinations, and a queue between them.  WHY A** (1 connections) — `app/notify.py`
- **Show a Windows toast. Returns whether the toast pipeline reported success.** (1 connections) — `app/notify.py`
- **Record that something happened. Returns True if this is the first time.      Che** (1 connections) — `app/notify.py`
- **Remote destinations, or {} when the operator has not set any up.      Absent fil** (1 connections) — `app/notify.py`
- **One remote destination. Returns a short outcome string for the record.      Two** (1 connections) — `app/notify.py`
- **Whether the Windows toast sink runs. OFF unless explicitly turned on.      MEASU** (1 connections) — `app/notify.py`
- **Send what is queued. Call this from the WATCHDOG tick, never the scanner.      E** (1 connections) — `app/notify.py`
- **Tell an OUTSIDE service this machine is still alive.      A heartbeat emitted by** (1 connections) — `app/notify.py`
- **Queue an alert, and optionally send it now.      `deliver=False` is the default** (1 connections) — `app/notify.py`

## Relationships

- [Watchdog Supervisor](Watchdog_Supervisor.md) (2 shared connections)
- [Live Scanner Loop](Live_Scanner_Loop.md) (1 shared connections)
- [Scanner Alert Isolation Tests](Scanner_Alert_Isolation_Tests.md) (1 shared connections)
- [Onboarding Announce Tests](Onboarding_Announce_Tests.md) (1 shared connections)
- [test_autotrader.py](test_autotrader.py.md) (1 shared connections)

## Source Files

- `app/notify.py`

## Audit Trail

- EXTRACTED: 68 (97%)
- INFERRED: 2 (3%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*