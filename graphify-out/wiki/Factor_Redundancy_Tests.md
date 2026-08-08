# Factor Redundancy Tests

> 19 nodes

## Key Concepts

- **candidates()** (23 connections) — `app/tests/test_factorstats.py`
- **TestDispersion** (5 connections) — `app/tests/test_factorstats.py`
- **TestRedundancy** (4 connections) — `app/tests/test_factorstats.py`
- **.test_perfectly_correlated_pair_is_flagged_redundant()** (3 connections) — `app/tests/test_factorstats.py`
- **.test_redundancy_is_transitive_across_a_cluster()** (3 connections) — `app/tests/test_factorstats.py`
- **.test_binary_flag_is_not_mistaken_for_zero_dispersion()** (3 connections) — `app/tests/test_factorstats.py`
- **.test_missing_is_not_imputed_as_zero()** (3 connections) — `app/tests/test_factorstats.py`
- **TestContribution** (3 connections) — `app/tests/test_factorstats.py`
- **.test_duplicated_factor_makes_the_share_sum_exceed_one()** (3 connections) — `app/tests/test_factorstats.py`
- **.test_independent_factors_are_not_merged()** (2 connections) — `app/tests/test_factorstats.py`
- **.test_constant_factor_is_flagged_zero_dispersion()** (2 connections) — `app/tests/test_factorstats.py`
- **.test_rare_factor_is_flagged_rare()** (2 connections) — `app/tests/test_factorstats.py`
- **.test_shares_sum_to_one_when_the_composite_is_the_factor_sum()** (2 connections) — `app/tests/test_factorstats.py`
- **Build the shape `analyze` consumes without touching the store: each row is     (** (1 connections) — `app/tests/test_factorstats.py`
- **Two names, one signal. `b` is `a` on a different scale — the exact shape** (1 connections) — `app/tests/test_factorstats.py`
- **A~B and B~C means all three read one thing, even when A and C never touch** (1 connections) — `app/tests/test_factorstats.py`
- **A 0/1 flag is constant *when present* by construction. Grading it on that** (1 connections) — `app/tests/test_factorstats.py`
- **An omitted key means "never recorded", not "recorded as zero". Imputing** (1 connections) — `app/tests/test_factorstats.py`
- **The double-counting alarm. Adding a copy of `a` under a new name does not** (1 connections) — `app/tests/test_factorstats.py`

## Relationships

- [Factor Stats Determinism Tests](Factor_Stats_Determinism_Tests.md) (5 shared connections)
- [Outcome Edge Tests](Outcome_Edge_Tests.md) (4 shared connections)
- [Outcome Split Tests](Outcome_Split_Tests.md) (4 shared connections)
- [Default Factor Extractor Tests](Default_Factor_Extractor_Tests.md) (1 shared connections)
- [Per-Factor Noise Floor Tests](Per-Factor_Noise_Floor_Tests.md) (1 shared connections)
- [Rank Decomposition Tests](Rank_Decomposition_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_factorstats.py`

## Audit Trail

- EXTRACTED: 64 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*