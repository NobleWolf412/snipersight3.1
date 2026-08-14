# One Source of Truth JS Tests

> 20 nodes

## Key Concepts

- **test_automation_execution.py** (20 connections) — `app/tests/test_automation_execution.py`
- **memory()** (15 connections) — `app/tests/test_automation_execution.py`
- **plan()** (14 connections) — `app/tests/test_automation_execution.py`
- **shadow_ready()** (6 connections) — `app/tests/test_automation_execution.py`
- **test_accepted_submission_is_recovered_after_crash_without_resubmit()** (5 connections) — `app/tests/test_automation_execution.py`
- **test_live_stays_build_locked_even_when_evidence_is_ready()** (4 connections) — `app/tests/test_automation_execution.py`
- **test_private_monitor_turns_partial_fill_into_exact_protected_custody()** (4 connections) — `app/tests/test_automation_execution.py`
- **intent()** (3 connections) — `app/tests/test_automation_execution.py`
- **test_testnet_requires_shadow_gate_and_exact_acknowledgement()** (3 connections) — `app/tests/test_automation_execution.py`
- **test_safety_drill_requires_testnet_ack_and_real_matching_observation()** (3 connections) — `app/tests/test_automation_execution.py`
- **test_shadow_never_calls_private_broker_and_outbox_is_idempotent()** (3 connections) — `app/tests/test_automation_execution.py`
- **test_execution_core_refuses_unapproved_risk_decision()** (3 connections) — `app/tests/test_automation_execution.py`
- **test_paper_intent_fills_and_closes_from_closed_candles()** (3 connections) — `app/tests/test_automation_execution.py`
- **test_paper_entry_uses_shared_maker_then_market_fill_authority()** (3 connections) — `app/tests/test_automation_execution.py`
- **test_shadow_comparison_is_earned_only_after_paired_paper_result()** (3 connections) — `app/tests/test_automation_execution.py`
- **test_shadow_pair_mismatch_records_integrity_failure_not_result()** (3 connections) — `app/tests/test_automation_execution.py`
- **test_operational_evidence_fails_closed_without_reconciliation_or_drills()** (3 connections) — `app/tests/test_automation_execution.py`
- **test_private_mode_cannot_be_downgraded_while_exposure_is_open()** (3 connections) — `app/tests/test_automation_execution.py`
- **live_gate()** (2 connections) — `app/tests/test_automation_execution.py`
- **test_mode_transition_is_optimistically_locked_and_audited()** (2 connections) — `app/tests/test_automation_execution.py`

## Relationships

- [Chart Vendor Marker Rendering](Chart_Vendor_Marker_Rendering.md) (3 shared connections)
- [A/B Calibration Tests](A-B_Calibration_Tests.md) (2 shared connections)
- [Shared Pipeline Loop Tests](Shared_Pipeline_Loop_Tests.md) (1 shared connections)
- [ProtectedBroker](ProtectedBroker.md) (1 shared connections)

## Source Files

- `app/tests/test_automation_execution.py`

## Audit Trail

- EXTRACTED: 99 (94%)
- INFERRED: 6 (6%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*