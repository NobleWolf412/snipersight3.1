# Setup Telemetry Tests

> 9 nodes

## Key Concepts

- **TestSetupTelemetry** (9 connections) — `app/tests/test_core_hardening.py`
- **.setUp()** (1 connections) — `app/tests/test_core_hardening.py`
- **.test_record_exposes_entry_geometry_and_reason()** (1 connections) — `app/tests/test_core_hardening.py`
- **.test_risk_rejection_is_owned_by_portfolio()** (1 connections) — `app/tests/test_core_hardening.py`
- **.test_expected_risk_rejection_is_not_a_system_defect()** (1 connections) — `app/tests/test_core_hardening.py`
- **.test_known_parameterised_risk_limit_has_catalog_evidence()** (1 connections) — `app/tests/test_core_hardening.py`
- **.test_known_data_gate_rejection_has_catalog_evidence()** (1 connections) — `app/tests/test_core_hardening.py`
- **.test_unfilled_limit_is_execution_failure()** (1 connections) — `app/tests/test_core_hardening.py`
- **.test_stop_is_distinct_from_cost_failure()** (1 connections) — `app/tests/test_core_hardening.py`

## Relationships

- [Rejection Fact Tests](Rejection_Fact_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_core_hardening.py`

## Audit Trail

- EXTRACTED: 17 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*