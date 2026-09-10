# ProtectedBroker

> 7 nodes

## Key Concepts

- **TestWalkForward** (7 connections) — `app/tests/test_entrystats.py`
- **._c()** (5 connections) — `app/tests/test_entrystats.py`
- **.test_a_bar_reaching_both_counts_as_a_stop()** (4 connections) — `app/tests/test_entrystats.py`
- **.test_timeout_and_unresolved_are_different_answers()** (3 connections) — `app/tests/test_entrystats.py`
- **.test_short_direction_mirrors_the_levels()** (3 connections) — `app/tests/test_entrystats.py`
- **.test_open_already_through_the_stop_is_unopenable_not_a_minus_one()** (3 connections) — `app/tests/test_entrystats.py`
- **Mirrors execsim's STOP_FIRST rule. A counterfactual that resolved         ambigu** (1 connections) — `app/tests/test_entrystats.py`

## Relationships

- [Kraken Adapter](Kraken_Adapter.md) (4 shared connections)
- [Entry Stats Tests](Entry_Stats_Tests.md) (2 shared connections)

## Source Files

- `app/tests/test_entrystats.py`

## Audit Trail

- EXTRACTED: 22 (85%)
- INFERRED: 4 (15%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*