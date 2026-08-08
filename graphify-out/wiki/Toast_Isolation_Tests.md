# Toast Isolation Tests

> 11 nodes

## Key Concepts

- **ToastIsSpawnedIsolated** (7 connections) — `app/tests/test_toast_isolation.py`
- **test_toast_isolation.py** (3 connections) — `app/tests/test_toast_isolation.py`
- **._spawn_kwargs()** (3 connections) — `app/tests/test_toast_isolation.py`
- **.test_the_child_does_not_borrow_our_console()** (2 connections) — `app/tests/test_toast_isolation.py`
- **.test_the_child_is_in_its_own_process_group()** (2 connections) — `app/tests/test_toast_isolation.py`
- **.test_a_toast_failure_is_never_raised_at_the_caller()** (2 connections) — `app/tests/test_toast_isolation.py`
- **.test_the_kill_switch_spawns_nothing()** (2 connections) — `app/tests/test_toast_isolation.py`
- **.test_the_temp_script_is_always_cleaned_up()** (1 connections) — `app/tests/test_toast_isolation.py`
- **A notification must not be able to kill the process that emits it.  The live sca** (1 connections) — `app/tests/test_toast_isolation.py`
- **check_drift and refresh_universe call this mid-cycle. A notification         tha** (1 connections) — `app/tests/test_toast_isolation.py`
- **SNIPERSIGHT_NO_TOAST is what made the failure bisectable, and is the         rig** (1 connections) — `app/tests/test_toast_isolation.py`

## Relationships

- [Notification Delivery](Notification_Delivery.md) (1 shared connections)

## Source Files

- `app/tests/test_toast_isolation.py`

## Audit Trail

- EXTRACTED: 25 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*