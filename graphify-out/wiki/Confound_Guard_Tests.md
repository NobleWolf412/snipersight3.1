# Confound Guard Tests

> 10 nodes

## Key Concepts

- **ConfoundGuard** (8 connections) — `app/tests/test_edgestats.py`
- **._t()** (5 connections) — `app/tests/test_edgestats.py`
- **.test_a_handful_of_orphan_rows_is_residue_not_a_split_book()** (3 connections) — `app/tests/test_edgestats.py`
- **.test_a_slice_from_one_generation_in_a_split_book_is_confounded()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_a_slice_spanning_both_generations_is_comparable()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_a_single_generation_book_can_never_be_confounded()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_an_unversioned_setup_id_is_named_not_guessed()** (2 connections) — `app/tests/test_edgestats.py`
- **A slice is only comparable to another if the same code produced both.      Por** (1 connections) — `app/tests/test_edgestats.py`
- **Three stragglers out of 340 flagged 3 of 4 timeframes as CONFOUNDED         on** (1 connections) — `app/tests/test_edgestats.py`
- **Guessing which generation an unlabelled fact came from is exactly the         c** (1 connections) — `app/tests/test_edgestats.py`

## Relationships

- [Edge Stats Determinism Tests](Edge_Stats_Determinism_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_edgestats.py`

## Audit Trail

- EXTRACTED: 27 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*