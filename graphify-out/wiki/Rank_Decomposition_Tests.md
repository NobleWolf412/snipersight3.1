# Rank Decomposition Tests

> 12 nodes

## Key Concepts

- **TestRankComponents** (8 connections) — `app/tests/test_factorstats.py`
- **.test_shares_sum_to_one_over_a_synthetic_book()** (4 connections) — `app/tests/test_factorstats.py`
- **.test_reproduction_error_is_non_zero_when_the_formula_stops_matching()** (3 connections) — `app/tests/test_factorstats.py`
- **.test_terms_are_points_not_flags()** (3 connections) — `app/tests/test_factorstats.py`
- **.test_unknown_htf_scores_zero_points_because_the_formula_does()** (3 connections) — `app/tests/test_factorstats.py`
- **.test_terms_reproduce_the_shipped_rank_exactly()** (2 connections) — `app/tests/test_factorstats.py`
- **.test_a_non_v07_payload_decomposes_into_nothing()** (1 connections) — `app/tests/test_factorstats.py`
- **The rank decomposition has one job: attribute var(rank) across the terms of** (1 connections) — `app/tests/test_factorstats.py`
- **The self-check is a factor ROW, not an assert, so a formula drift shows up** (1 connections) — `app/tests/test_factorstats.py`
- **cov(20*sweep, rank) is 20x cov(sweep, rank). Emitting bare flags would give** (1 connections) — `app/tests/test_factorstats.py`
- **Deliberately UNLIKE the confluence extractor: `setups.py` writes         `if con** (1 connections) — `app/tests/test_factorstats.py`
- **The sum IS the self-check: rank is the unweighted sum of these terms, so** (1 connections) — `app/tests/test_factorstats.py`

## Relationships

- [Confluence Extractor Tests](Confluence_Extractor_Tests.md) (5 shared connections)
- [Factor Stats Determinism Tests](Factor_Stats_Determinism_Tests.md) (1 shared connections)
- [Factor Redundancy Tests](Factor_Redundancy_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_factorstats.py`

## Audit Trail

- EXTRACTED: 29 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*