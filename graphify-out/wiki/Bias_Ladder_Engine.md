# Bias Ladder Engine

> 30 nodes

## Key Concepts

- **log()** (14 connections) — `app/watchdog.py`
- **watchdog.py** (13 connections) — `app/watchdog.py`
- **main()** (12 connections) — `app/watchdog.py`
- **Child** (10 connections) — `app/watchdog.py`
- **retention_tick()** (7 connections) — `app/watchdog.py`
- **audit_tick()** (7 connections) — `app/watchdog.py`
- **.tick()** (7 connections) — `app/watchdog.py`
- **.start()** (6 connections) — `app/watchdog.py`
- **rotate_engine_log()** (5 connections) — `app/watchdog.py`
- **.kill()** (5 connections) — `app/watchdog.py`
- **.alive()** (5 connections) — `app/watchdog.py`
- **_orphans()** (4 connections) — `app/watchdog.py`
- **clear_orphans()** (4 connections) — `app/watchdog.py`
- **._rotate_err()** (4 connections) — `app/watchdog.py`
- **alert_tick()** (4 connections) — `app/watchdog.py`
- **server_up()** (3 connections) — `app/watchdog.py`
- **._child_env()** (3 connections) — `app/watchdog.py`
- **._last_error()** (3 connections) — `app/watchdog.py`
- **.__init__()** (1 connections) — `app/watchdog.py`
- **Watchdog — keeps the scanner and server alive. The forward paper record is the p** (1 connections) — `app/watchdog.py`
- **Is an API server answering?      The timeout was 3s against an endpoint measured** (1 connections) — `app/watchdog.py`
- **Scanner/server processes from a PREVIOUS supervisor, still running.      watchdo** (1 connections) — `app/watchdog.py`
- **Bound the duplicated/operational stream while both children are down.      The s** (1 connections) — `app/watchdog.py`
- **Coordinate a safe hot-log rollover during a scanner idle boundary.      Returns** (1 connections) — `app/watchdog.py`
- **Call quality.audit() and dispatch by Kill-Switch rung.      HALT present or QUAR** (1 connections) — `app/watchdog.py`
- *... and 5 more nodes in this community*

## Relationships

- [Watchdog Restart Dispatch Tests](Watchdog_Restart_Dispatch_Tests.md) (3 shared connections)
- [Watchdog Supervisor](Watchdog_Supervisor.md) (2 shared connections)
- [Watchdog Audit Cadence Tests](Watchdog_Audit_Cadence_Tests.md) (1 shared connections)

## Source Files

- `app/watchdog.py`

## Audit Trail

- EXTRACTED: 126 (98%)
- INFERRED: 2 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*