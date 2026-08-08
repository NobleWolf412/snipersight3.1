# Factor Stats Determinism Tests

> 14 nodes

## Key Concepts

- **test_factorstats.py** (15 connections) — `app/tests/test_factorstats.py`
- **TempStore** (5 connections) — `app/tests/test_factorstats.py`
- **TestDeterminism** (5 connections) — `app/tests/test_factorstats.py`
- **TestStoreJoin** (5 connections) — `app/tests/test_factorstats.py`
- **.test_identical_input_gives_byte_identical_output()** (2 connections) — `app/tests/test_factorstats.py`
- **.test_report_over_a_real_store_is_stable_and_writes_nothing()** (2 connections) — `app/tests/test_factorstats.py`
- **._seed()** (2 connections) — `app/tests/test_factorstats.py`
- **.test_outcome_confirmed_before_its_setup_is_refused_not_used()** (2 connections) — `app/tests/test_factorstats.py`
- **.setUp()** (1 connections) — `app/tests/test_factorstats.py`
- **.tearDown()** (1 connections) — `app/tests/test_factorstats.py`
- **.test_missed_orders_are_excluded_from_the_outcome_axis()** (1 connections) — `app/tests/test_factorstats.py`
- **.test_empty_store_says_so_rather_than_reporting_zeros()** (1 connections) — `app/tests/test_factorstats.py`
- **Factor-grading diagnostics. The properties tested here are the ones that would h** (1 connections) — `app/tests/test_factorstats.py`
- **Causality (house convention 2). An exec fact that predates its setup means** (1 connections) — `app/tests/test_factorstats.py`

## Relationships

- [Factor Redundancy Tests](Factor_Redundancy_Tests.md) (5 shared connections)
- [Confluence Extractor Tests](Confluence_Extractor_Tests.md) (2 shared connections)
- [Default Factor Extractor Tests](Default_Factor_Extractor_Tests.md) (1 shared connections)
- [Outcome Edge Tests](Outcome_Edge_Tests.md) (1 shared connections)
- [Outcome Split Tests](Outcome_Split_Tests.md) (1 shared connections)
- [Per-Factor Noise Floor Tests](Per-Factor_Noise_Floor_Tests.md) (1 shared connections)
- [Rank Decomposition Tests](Rank_Decomposition_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_factorstats.py`

## Audit Trail

- EXTRACTED: 44 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*