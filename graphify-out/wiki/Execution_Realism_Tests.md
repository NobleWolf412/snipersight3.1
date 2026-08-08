# Execution Realism Tests

> 9 nodes

## Key Concepts

- **candle()** (7 connections) — `app/tests/test_core_hardening.py`
- **TestExecutionRealism** (5 connections) — `app/tests/test_core_hardening.py`
- **TestRiskVenueContract** (5 connections) — `app/tests/test_core_hardening.py`
- **._setup()** (3 connections) — `app/tests/test_core_hardening.py`
- **.test_order_cannot_fill_before_signal_is_available()** (3 connections) — `app/tests/test_core_hardening.py`
- **.test_unrevisited_limit_becomes_missed()** (3 connections) — `app/tests/test_core_hardening.py`
- **.test_forward_baseline_excludes_old_loss_without_deleting_it()** (2 connections) — `app/tests/test_core_hardening.py`
- **.test_short_is_rejected_for_coinbase_spot_and_has_zero_risk()** (2 connections) — `app/tests/test_core_hardening.py`
- **.test_daily_halt_uses_start_of_day_equity()** (2 connections) — `app/tests/test_core_hardening.py`

## Relationships

- [Rejection Fact Tests](Rejection_Fact_Tests.md) (6 shared connections)

## Source Files

- `app/tests/test_core_hardening.py`

## Audit Trail

- EXTRACTED: 32 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*