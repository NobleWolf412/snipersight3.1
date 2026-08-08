# Small Sample Refusal Tests

> 7 nodes

## Key Concepts

- **TempStore** (10 connections) — `app/tests/test_edgestats.py`
- **TestSmallSampleRefusal** (5 connections) — `app/tests/test_edgestats.py`
- **.test_thin_timeframe_is_refused_without_poisoning_the_book()** (3 connections) — `app/tests/test_edgestats.py`
- **.test_short_book_refuses_instead_of_returning_a_confident_zero()** (2 connections) — `app/tests/test_edgestats.py`
- **.setUp()** (1 connections) — `app/tests/test_edgestats.py`
- **.tearDown()** (1 connections) — `app/tests/test_edgestats.py`
- **.test_empty_book_refuses_rather_than_reporting_zero_expectancy()** (1 connections) — `app/tests/test_edgestats.py`

## Relationships

- [Edge Stats Determinism Tests](Edge_Stats_Determinism_Tests.md) (6 shared connections)
- [Breakeven Fee Tests](Breakeven_Fee_Tests.md) (3 shared connections)
- [Filtered Book Refusal Tests](Filtered_Book_Refusal_Tests.md) (1 shared connections)
- [Forward vs Historical Book Tests](Forward_vs_Historical_Book_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_edgestats.py`

## Audit Trail

- EXTRACTED: 23 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*