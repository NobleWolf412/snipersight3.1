# Watchdog Child Capture Tests

> 15 nodes

## Key Concepts

- **TestChildErrorCapture** (10 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **._child()** (7 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_a_child_can_flush_the_handle_it_inherits()** (3 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_heavy_child_logging_does_not_corrupt_the_stream()** (3 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_the_capture_file_is_rotated()** (3 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_capture_failure_never_blocks_a_start()** (3 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_only_the_scanner_has_its_stderr_captured()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_a_traceback_is_captured_and_surfaced()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **.test_a_clean_child_surfaces_nothing()** (2 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **An exit code alone cannot tell a crash from a deliberate terminate.      Childre** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **Handing uvicorn an inherited stderr handle broke its access logger —         8,4** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **The precise property, because the indirect test missed it.          Python's "a"** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **The capture must not break the thing it captures.          The first version han** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **A diagnostic that fills the disk is a fault of its own.** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`
- **Logging is housekeeping; it must not stop the scanner coming back.** (1 connections) — `app/tests/test_watchdog_rung_dispatch.py`

## Relationships

- [Watchdog Kill Attribution Tests](Watchdog_Kill_Attribution_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_watchdog_rung_dispatch.py`

## Audit Trail

- EXTRACTED: 41 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*