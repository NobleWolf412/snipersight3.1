# System Restart Tests

> 14 nodes

## Key Concepts

- **SystemRestartTests** (8 connections) — `app/tests/test_system_restart.py`
- **test_system_restart.py** (3 connections) — `app/tests/test_system_restart.py`
- **.test_refuses_when_no_supervisor_is_running()** (2 connections) — `app/tests/test_system_restart.py`
- **.test_scanner_only_target_never_exits_this_process()** (2 connections) — `app/tests/test_system_restart.py`
- **.test_no_test_in_this_file_can_reach_a_real_process()** (2 connections) — `app/tests/test_system_restart.py`
- **.test_watchdog_liveness_probe_matches_lock_port()** (2 connections) — `app/tests/test_system_restart.py`
- **.setUp()** (1 connections) — `app/tests/test_system_restart.py`
- **.test_rejects_unknown_target()** (1 connections) — `app/tests/test_system_restart.py`
- **.test_probe_detects_a_held_lock()** (1 connections) — `app/tests/test_system_restart.py`
- **The restart endpoint must be a restart, never a kill switch.** (1 connections) — `app/tests/test_system_restart.py`
- **Without the watchdog, stopping processes would leave the app down —         so** (1 connections) — `app/tests/test_system_restart.py`
- **target=scanner must not schedule an exit of the API server.          THIS TEST** (1 connections) — `app/tests/test_system_restart.py`
- **The guarantee, not just this one call site.          A future test that forces** (1 connections) — `app/tests/test_system_restart.py`
- **The probe must key on the same lock port watchdog.py binds.** (1 connections) — `app/tests/test_system_restart.py`

## Relationships

- [API Server Endpoints](API_Server_Endpoints.md) (1 shared connections)

## Source Files

- `app/tests/test_system_restart.py`

## Audit Trail

- EXTRACTED: 27 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*