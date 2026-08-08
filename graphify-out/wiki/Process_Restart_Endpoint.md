# Process Restart Endpoint

> 8 nodes

## Key Concepts

- **_stop_pid()** (4 connections) — `app/server.py`
- **system_restart()** (4 connections) — `app/server.py`
- **_audit_kill()** (3 connections) — `app/server.py`
- **_watchdog_alive()** (3 connections) — `app/server.py`
- **Write who asked for a process to die, next to the supervisor's own log.      B** (1 connections) — `app/server.py`
- **Stop a process and report the OBSERVED outcome.      Windows note: os.kill(pid** (1 connections) — `app/server.py`
- **True when a supervisor holds the watchdog lock socket. If we can bind it,     n** (1 connections) — `app/server.py`
- **Restart supervised processes.      Deliberately has NO spawn capability: it on** (1 connections) — `app/server.py`

## Relationships

- [API Server Endpoints](API_Server_Endpoints.md) (4 shared connections)

## Source Files

- `app/server.py`

## Audit Trail

- EXTRACTED: 18 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*