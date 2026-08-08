# Watchdog Supervisor

> 28 nodes

## Key Concepts

- **log()** (12 connections) — `app/watchdog.py`
- **watchdog.py** (11 connections) — `app/watchdog.py`
- **Child** (10 connections) — `app/watchdog.py`
- **main()** (10 connections) — `app/watchdog.py`
- **audit_tick()** (7 connections) — `app/watchdog.py`
- **.tick()** (7 connections) — `app/watchdog.py`
- **.start()** (6 connections) — `app/watchdog.py`
- **toast()** (4 connections) — `app/watchdog.py`
- **_orphans()** (4 connections) — `app/watchdog.py`
- **clear_orphans()** (4 connections) — `app/watchdog.py`
- **.kill()** (4 connections) — `app/watchdog.py`
- **.alive()** (4 connections) — `app/watchdog.py`
- **._rotate_err()** (4 connections) — `app/watchdog.py`
- **alert_tick()** (4 connections) — `app/watchdog.py`
- **server_up()** (3 connections) — `app/watchdog.py`
- **._child_env()** (3 connections) — `app/watchdog.py`
- **._last_error()** (3 connections) — `app/watchdog.py`
- **.__init__()** (1 connections) — `app/watchdog.py`
- **Watchdog — keeps the scanner and server alive. The forward paper record is the p** (1 connections) — `app/watchdog.py`
- **Announce something, WITHOUT spawning anything.      THE RESTART LOOP THIS ENDS.** (1 connections) — `app/watchdog.py`
- **Is an API server answering?      The timeout was 3s against an endpoint measured** (1 connections) — `app/watchdog.py`
- **Scanner/server processes from a PREVIOUS supervisor, still running.      watchdo** (1 connections) — `app/watchdog.py`
- **Call quality.audit() and dispatch by Kill-Switch rung.      HALT present or QUAR** (1 connections) — `app/watchdog.py`
- **Start the child with its stderr captured to a file.          It used to inherit** (1 connections) — `app/watchdog.py`
- **The scanner does not spawn desktop notifications.          Every toast spawns a** (1 connections) — `app/watchdog.py`
- *... and 3 more nodes in this community*

## Relationships

- [Notification Delivery](Notification_Delivery.md) (2 shared connections)
- [Watchdog Kill Attribution Tests](Watchdog_Kill_Attribution_Tests.md) (1 shared connections)

## Source Files

- `app/watchdog.py`

## Audit Trail

- EXTRACTED: 109 (98%)
- INFERRED: 2 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*