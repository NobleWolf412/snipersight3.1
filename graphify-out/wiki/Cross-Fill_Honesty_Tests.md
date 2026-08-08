# Cross-Fill Honesty Tests

> 11 nodes

## Key Concepts

- **RecordedFillsLieWithinTheirBar** (5 connections) — `app/tests/test_cross_fill_honesty.py`
- **test_cross_fill_honesty.py** (4 connections) — `app/tests/test_cross_fill_honesty.py`
- **CrossFillHonesty** (3 connections) — `app/tests/test_cross_fill_honesty.py`
- **.test_cross_fills_at_the_crossing_bar_not_the_plan()** (2 connections) — `app/tests/test_cross_fill_honesty.py`
- **.test_no_fill_is_priced_outside_its_own_bar()** (2 connections) — `app/tests/test_cross_fill_honesty.py`
- **.setUpClass()** (1 connections) — `app/tests/test_cross_fill_honesty.py`
- **.tearDownClass()** (1 connections) — `app/tests/test_cross_fill_honesty.py`
- **A simulated fill must be a price the bar actually traded.  The MAKER_THEN_MARK** (1 connections) — `app/tests/test_cross_fill_honesty.py`
- **Unit-level: the crossing branch must price off the crossing bar.** (1 connections) — `app/tests/test_cross_fill_honesty.py`
- **A cross is a market order. It fills at the market, on THIS bar.          Const** (1 connections) — `app/tests/test_cross_fill_honesty.py`
- **Store-level: no recorded fill may sit outside the bar it filled on.      The g** (1 connections) — `app/tests/test_cross_fill_honesty.py`

## Relationships

- [Swings, Zones & Draft Bracket](Swings%2C_Zones_%26_Draft_Bracket.md) (2 shared connections)

## Source Files

- `app/tests/test_cross_fill_honesty.py`

## Audit Trail

- EXTRACTED: 21 (95%)
- INFERRED: 1 (5%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*