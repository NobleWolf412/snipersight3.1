# TestNoLookahead

> 7 nodes

## Key Concepts

- **TestNoLookahead** (6 connections) — `app/tests/test_entrystats.py`
- **.test_walk_ignores_the_bar_that_would_have_won_before_confirmation()** (3 connections) — `app/tests/test_entrystats.py`
- **.test_a_bar_opening_before_available_at_is_refused_loudly()** (3 connections) — `app/tests/test_entrystats.py`
- **.test_report_walks_start_at_or_after_every_available_at()** (2 connections) — `app/tests/test_entrystats.py`
- **.test_first_bar_is_never_before_available_at()** (1 connections) — `app/tests/test_entrystats.py`
- **The bar BEFORE confirmation reaches the target. A walk that looked         back** (1 connections) — `app/tests/test_entrystats.py`
- **Belt and braces on the boundary: if the index selection is ever         changed** (1 connections) — `app/tests/test_entrystats.py`

## Relationships

- [Entry Stats Tests](Entry_Stats_Tests.md) (3 shared connections)
- [Kraken Adapter](Kraken_Adapter.md) (2 shared connections)

## Source Files

- `app/tests/test_entrystats.py`

## Audit Trail

- EXTRACTED: 15 (88%)
- INFERRED: 2 (12%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*