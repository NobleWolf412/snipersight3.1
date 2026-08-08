# Outcome Split Tests

> 9 nodes

## Key Concepts

- **TestOutcomeSplit** (8 connections) — `app/tests/test_factorstats.py`
- **._book()** (4 connections) — `app/tests/test_factorstats.py`
- **.test_missing_is_its_own_group_never_folded_into_below()** (3 connections) — `app/tests/test_factorstats.py`
- **.test_reports_win_rate_and_mean_r_on_each_side()** (2 connections) — `app/tests/test_factorstats.py`
- **.test_a_backwards_factor_reports_a_negative_delta()** (2 connections) — `app/tests/test_factorstats.py`
- **.test_a_group_under_the_floor_keeps_its_counts_but_withholds_rates()** (2 connections) — `app/tests/test_factorstats.py`
- **.test_open_and_missed_candidates_are_excluded()** (2 connections) — `app/tests/test_factorstats.py`
- **The readable form of a 0/1 factor's outcome edge. A rank term paying points to** (1 connections) — `app/tests/test_factorstats.py`
- **Folding 'the store never recorded it' into 'it was absent' is how a         cove** (1 connections) — `app/tests/test_factorstats.py`

## Relationships

- [Factor Redundancy Tests](Factor_Redundancy_Tests.md) (4 shared connections)
- [Factor Stats Determinism Tests](Factor_Stats_Determinism_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_factorstats.py`

## Audit Trail

- EXTRACTED: 25 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*