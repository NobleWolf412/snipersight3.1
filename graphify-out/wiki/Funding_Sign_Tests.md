# Funding Sign Tests

> 14 nodes

## Key Concepts

- **series()** (9 connections) — `app/tests/test_funding.py`
- **TheSign** (6 connections) — `app/tests/test_funding.py`
- **CoverageIsRefused** (6 connections) — `app/tests/test_funding.py`
- **.test_a_long_pays_a_positive_rate()** (2 connections) — `app/tests/test_funding.py`
- **.test_a_short_is_paid_the_same_rate()** (2 connections) — `app/tests/test_funding.py`
- **.test_a_negative_rate_reverses_both()** (2 connections) — `app/tests/test_funding.py`
- **.test_only_settlements_inside_the_hold_are_charged()** (2 connections) — `app/tests/test_funding.py`
- **.test_a_hold_that_starts_before_the_history_is_not_covered()** (2 connections) — `app/tests/test_funding.py`
- **.test_a_hold_that_ends_after_the_history_is_not_covered()** (2 connections) — `app/tests/test_funding.py`
- **.test_a_fully_spanned_hold_is_covered()** (2 connections) — `app/tests/test_funding.py`
- **.test_an_empty_series_is_never_covered()** (1 connections) — `app/tests/test_funding.py`
- **(hour offset, rate) -> the (unix, Decimal) shape history() returns.** (1 connections) — `app/tests/test_funding.py`
- **A short is PAID when the rate is positive. execsim subtracts funding in     bot** (1 connections) — `app/tests/test_funding.py`
- **A hold priced from a partial window reports a cost that is too small for     th** (1 connections) — `app/tests/test_funding.py`

## Relationships

- [Funding Read-Only Tests](Funding_Read-Only_Tests.md) (3 shared connections)

## Source Files

- `app/tests/test_funding.py`

## Audit Trail

- EXTRACTED: 39 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*