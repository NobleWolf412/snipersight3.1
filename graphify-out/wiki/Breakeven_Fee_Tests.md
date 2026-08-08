# Breakeven Fee Tests

> 10 nodes

## Key Concepts

- **add_trade()** (12 connections) — `app/tests/test_edgestats.py`
- **TestBreakevenFee** (5 connections) — `app/tests/test_edgestats.py`
- **TestFeeScenarios** (4 connections) — `app/tests/test_edgestats.py`
- **.test_recorded_r_is_not_re_netted_and_venue_rates_re_price_it()** (3 connections) — `app/tests/test_edgestats.py`
- **.test_filters_narrow_the_book()** (3 connections) — `app/tests/test_edgestats.py`
- **.test_breakeven_per_side_fee_is_mean_fee_free_r_over_mean_leg_r()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_breakeven_is_compared_against_the_venue_not_a_hard_coded_rate()** (2 connections) — `app/tests/test_edgestats.py`
- **.test_a_book_that_loses_before_fees_reports_no_fee_rescues_it()** (2 connections) — `app/tests/test_edgestats.py`
- **Insert the setup+exec fact pair for one filled paper trade.** (1 connections) — `app/tests/test_edgestats.py`
- **The caveat that inverts on the port: r_multiple already has fees in.** (1 connections) — `app/tests/test_edgestats.py`

## Relationships

- [Edge Stats Determinism Tests](Edge_Stats_Determinism_Tests.md) (5 shared connections)
- [Small Sample Refusal Tests](Small_Sample_Refusal_Tests.md) (3 shared connections)
- [Filtered Book Refusal Tests](Filtered_Book_Refusal_Tests.md) (2 shared connections)
- [Forward vs Historical Book Tests](Forward_vs_Historical_Book_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_edgestats.py`

## Audit Trail

- EXTRACTED: 35 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*