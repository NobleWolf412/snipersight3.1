# Funding Accrual Tests

> 6 nodes

## Key Concepts

- **Accrual** (4 connections) — `app/tests/test_funding.py`
- **.test_funding_scales_with_holding_time_not_charged_once()** (2 connections) — `app/tests/test_funding.py`
- **.test_spot_pays_nothing_by_venue_declaration_not_by_a_branch()** (2 connections) — `app/tests/test_funding.py`
- **.test_three_settlements_a_day_on_phemex()** (1 connections) — `app/tests/test_funding.py`
- **The whole point of the S32 note. A position held three days pays         three** (1 connections) — `app/tests/test_funding.py`
- **Coinbase declares 0 settlements/day, so the same call returns zero on         s** (1 connections) — `app/tests/test_funding.py`

## Relationships

- [Funding Read-Only Tests](Funding_Read-Only_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_funding.py`

## Audit Trail

- EXTRACTED: 11 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*