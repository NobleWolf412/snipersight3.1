# Per-Factor Noise Floor Tests

> 6 nodes

## Key Concepts

- **TestPerFactorNoiseFloor** (5 connections) — `app/tests/test_factorstats.py`
- **._partial_book()** (5 connections) — `app/tests/test_factorstats.py`
- **.test_partial_coverage_gets_its_own_wider_floor()** (2 connections) — `app/tests/test_factorstats.py`
- **.test_a_factor_under_the_trade_floor_is_withheld_even_on_a_big_book()** (2 connections) — `app/tests/test_factorstats.py`
- **A factor the store only recorded on part of the book is measured on part of** (1 connections) — `app/tests/test_factorstats.py`
- **`partial` is recorded on the first `n_covered` candidates and omitted on** (1 connections) — `app/tests/test_factorstats.py`

## Relationships

- [Factor Stats Determinism Tests](Factor_Stats_Determinism_Tests.md) (1 shared connections)
- [Factor Redundancy Tests](Factor_Redundancy_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_factorstats.py`

## Audit Trail

- EXTRACTED: 16 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*