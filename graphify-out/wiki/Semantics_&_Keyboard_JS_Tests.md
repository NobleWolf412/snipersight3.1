# Semantics & Keyboard JS Tests

> 28 nodes

## Key Concepts

- **AuditStreamCase** (15 connections) — `app/tests/test_audit_log.py`
- **.audit()** (8 connections) — `app/tests/test_audit_log.py`
- **.hot()** (6 connections) — `app/tests/test_audit_log.py`
- **.test_a_degraded_path_warning_reaches_the_evidence_stream()** (4 connections) — `app/tests/test_audit_log.py`
- **.test_the_run_line_that_is_985_percent_of_the_log_is_not_duplicated()** (4 connections) — `app/tests/test_audit_log.py`
- **.test_the_evidence_stream_is_a_subset_never_a_replacement()** (4 connections) — `app/tests/test_audit_log.py`
- **AuditPrefixCoverageCase** (4 connections) — `app/tests/test_audit_log.py`
- **test_audit_log.py** (3 connections) — `app/tests/test_audit_log.py`
- **._read()** (3 connections) — `app/tests/test_audit_log.py`
- **.test_every_operator_write_action_is_kept()** (3 connections) — `app/tests/test_audit_log.py`
- **.test_loop_heartbeat_is_not_kept()** (3 connections) — `app/tests/test_audit_log.py`
- **.test_an_error_reaches_the_evidence_stream()** (2 connections) — `app/tests/test_audit_log.py`
- **.test_a_failed_audit_handler_leaves_no_handler_attached()** (2 connections) — `app/tests/test_audit_log.py`
- **.test_an_unrenderable_message_is_kept_not_raised()** (2 connections) — `app/tests/test_audit_log.py`
- **.test_the_autotrader_routing_line_is_evidence()** (2 connections) — `app/tests/test_audit_log.py`
- **.setUp()** (1 connections) — `app/tests/test_audit_log.py`
- **.tearDown()** (1 connections) — `app/tests/test_audit_log.py`
- **.test_every_info_line_that_could_be_evidence_is_classified()** (1 connections) — `app/tests/test_audit_log.py`
- **The evidence stream — what `data/engine-audit.log` must and must not carry.  `en** (1 connections) — `app/tests/test_audit_log.py`
- **Drives the real get_logger() with both files redirected to a temp dir.** (1 connections) — `app/tests/test_audit_log.py`
- **The convention that a fallback must be audible is enforced by this         file** (1 connections) — `app/tests/test_audit_log.py`
- **One line per irreversible thing the operator can do to a real book.** (1 connections) — `app/tests/test_audit_log.py`
- **RunRecorder's DEBUG line is already a row in engine_runs, with more         deta** (1 connections) — `app/tests/test_audit_log.py`
- **Attach-as-you-build leaked one engine.log handler per get_logger         retry w** (1 connections) — `app/tests/test_audit_log.py`
- **Handler.handle runs filters outside emit()'s try/except, so a         filter tha** (1 connections) — `app/tests/test_audit_log.py`
- *... and 3 more nodes in this community*

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_audit_log.py`

## Audit Trail

- EXTRACTED: 78 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*