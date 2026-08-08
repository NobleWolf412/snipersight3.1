# Forward vs Historical Book Tests

> 12 nodes

## Key Concepts

- **TestForwardVsHistorical** (10 connections) — `app/tests/test_edgestats.py`
- **._book()** (6 connections) — `app/tests/test_edgestats.py`
- **.setUp()** (3 connections) — `app/tests/test_edgestats.py`
- **.test_a_filtered_report_still_says_what_it_left_out()** (3 connections) — `app/tests/test_edgestats.py`
- **.test_a_single_window_does_not_warn()** (3 connections) — `app/tests/test_edgestats.py`
- **.setUp()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_the_two_halves_are_separable()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_the_combined_book_warns_that_it_is_combined()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_the_window_is_recorded_on_the_report()** (2 connections) — `app/tests/test_edgestats.py`
- **A backfilled trade is not a track record, and adding the two together     produ** (1 connections) — `app/tests/test_edgestats.py`
- **Same rule as venue_state: counts carry BOTH halves whichever is         selecte** (1 connections) — `app/tests/test_edgestats.py`
- **The warning exists to stop an unlabelled mix being read as a track         reco** (1 connections) — `app/tests/test_edgestats.py`

## Relationships

- [Filtered Book Refusal Tests](Filtered_Book_Refusal_Tests.md) (1 shared connections)
- [Edge Stats Determinism Tests](Edge_Stats_Determinism_Tests.md) (1 shared connections)
- [Small Sample Refusal Tests](Small_Sample_Refusal_Tests.md) (1 shared connections)
- [Breakeven Fee Tests](Breakeven_Fee_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_edgestats.py`

## Audit Trail

- EXTRACTED: 36 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*