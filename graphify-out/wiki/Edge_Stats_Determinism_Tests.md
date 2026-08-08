# Edge Stats Determinism Tests

> 15 nodes

## Key Concepts

- **build()** (13 connections) — `app/tests/test_edgestats.py`
- **test_edgestats.py** (12 connections) — `app/tests/test_edgestats.py`
- **TestDeterminism** (6 connections) — `app/tests/test_edgestats.py`
- **TestKnownBooks** (6 connections) — `app/tests/test_edgestats.py`
- **add_missed()** (3 connections) — `app/tests/test_edgestats.py`
- **.test_unfilled_orders_never_reach_the_statistics()** (3 connections) — `app/tests/test_edgestats.py`
- **.test_two_runs_over_the_same_store_are_identical()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_two_independently_built_stores_agree_byte_for_byte()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_report_writes_no_facts()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_positive_book_has_a_ci_entirely_above_zero()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_negative_book_has_a_ci_entirely_below_zero()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_longest_losing_streak_is_counted_in_confirmation_order()** (2 connections) — `app/tests/test_edgestats.py`
- **An order that never filled. Not a trade — must not reach the statistics.** (1 connections) — `app/tests/test_edgestats.py`
- **A book of `wins` winners then `losses` losers, interleaved by time.** (1 connections) — `app/tests/test_edgestats.py`
- **A recorded result that changes between runs is not a result (§4).** (1 connections) — `app/tests/test_edgestats.py`

## Relationships

- [Small Sample Refusal Tests](Small_Sample_Refusal_Tests.md) (6 shared connections)
- [Breakeven Fee Tests](Breakeven_Fee_Tests.md) (5 shared connections)
- [Confound Guard Tests](Confound_Guard_Tests.md) (1 shared connections)
- [Filtered Book Refusal Tests](Filtered_Book_Refusal_Tests.md) (1 shared connections)
- [Forward vs Historical Book Tests](Forward_vs_Historical_Book_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_edgestats.py`

## Audit Trail

- EXTRACTED: 58 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*