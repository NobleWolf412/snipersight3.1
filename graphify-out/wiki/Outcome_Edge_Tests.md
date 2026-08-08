# Outcome Edge Tests

> 10 nodes

## Key Concepts

- **TestOutcomeEdge** (7 connections) — `app/tests/test_factorstats.py`
- **.test_small_sample_refuses_to_report_a_correlation()** (4 connections) — `app/tests/test_factorstats.py`
- **.test_weak_correlation_under_the_noise_floor_is_not_credited()** (3 connections) — `app/tests/test_factorstats.py`
- **.test_factor_that_scores_high_on_losers_reports_negative_r()** (3 connections) — `app/tests/test_factorstats.py`
- **._rows()** (2 connections) — `app/tests/test_factorstats.py`
- **.test_genuine_predictor_clears_the_floor_and_is_credited()** (2 connections) — `app/tests/test_factorstats.py`
- **.test_noise_floor_matches_the_published_formula()** (1 connections) — `app/tests/test_factorstats.py`
- **Loud fallback: below MIN_TRADES the honest output is 'unknown'. The prior** (1 connections) — `app/tests/test_factorstats.py`
- **r != 0 is not edge. At n=120 the floor is ±0.18; a factor sitting under it** (1 connections) — `app/tests/test_factorstats.py`
- **A negative r is a finding, not a bug: the factor is actively steering the** (1 connections) — `app/tests/test_factorstats.py`

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