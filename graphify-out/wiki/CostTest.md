# CostTest

> 8 nodes

## Key Concepts

- **CostTest** (5 connections) — `app/tests/test_venues.py`
- **.test_perp_fees_are_cheaper_than_spot()** (2 connections) — `app/tests/test_venues.py`
- **.test_funding_accrues_per_settlement_not_once()** (2 connections) — `app/tests/test_venues.py`
- **.test_leverage_cap_is_conservative_against_the_venue_maximum()** (2 connections) — `app/tests/test_venues.py`
- **.test_spot_pays_no_funding()** (1 connections) — `app/tests/test_venues.py`
- **Not a preference — it is why perps can carry timeframes spot cannot.** (1 connections) — `app/tests/test_venues.py`
- **A perp held over a weekend pays every settlement. Charging it once         woul** (1 connections) — `app/tests/test_venues.py`
- **Phemex permits 100x. Size here is derived from RISK, so a high cap         adds** (1 connections) — `app/tests/test_venues.py`

## Relationships

- [test_venues.py](test_venues.py.md) (1 shared connections)

## Source Files

- `app/tests/test_venues.py`

## Audit Trail

- EXTRACTED: 15 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*