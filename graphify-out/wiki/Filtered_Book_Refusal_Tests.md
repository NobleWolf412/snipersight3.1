# Filtered Book Refusal Tests

> 13 nodes

## Key Concepts

- **TestFilteredBookRefusal** (11 connections) — `app/tests/test_edgestats.py`
- **._shadow()** (6 connections) — `app/tests/test_edgestats.py`
- **._traded()** (4 connections) — `app/tests/test_edgestats.py`
- **.test_a_handful_of_tradeable_trades_is_refused_not_solved_for_a_fee()** (4 connections) — `app/tests/test_edgestats.py`
- **.test_the_traded_half_is_still_graded_when_it_clears_the_floor()** (4 connections) — `app/tests/test_edgestats.py`
- **.test_the_refusal_still_reports_what_the_filter_removed()** (3 connections) — `app/tests/test_edgestats.py`
- **.test_an_all_shadow_book_refuses_rather_than_dividing_by_zero()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_breakeven_fee_on_an_empty_book_is_not_computable()** (2 connections) — `app/tests/test_edgestats.py`
- **The floor has to be measured on the book being GRADED, not on the one     `load** (1 connections) — `app/tests/test_edgestats.py`
- **A filtered report that cannot say what it left out is worse than no         rep** (1 connections) — `app/tests/test_edgestats.py`
- **Quieter than the crash and worse: below the floor but above zero,         the o** (1 connections) — `app/tests/test_edgestats.py`
- **The gate must only refuse — it must not narrow a book that qualifies.         `** (1 connections) — `app/tests/test_edgestats.py`
- **Defence in depth. `report`'s floor is the real gate, but this is a         modu** (1 connections) — `app/tests/test_edgestats.py`

## Relationships

- [Breakeven Fee Tests](Breakeven_Fee_Tests.md) (2 shared connections)
- [Edge Stats Determinism Tests](Edge_Stats_Determinism_Tests.md) (1 shared connections)
- [Small Sample Refusal Tests](Small_Sample_Refusal_Tests.md) (1 shared connections)
- [Forward vs Historical Book Tests](Forward_vs_Historical_Book_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_edgestats.py`

## Audit Trail

- EXTRACTED: 41 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*