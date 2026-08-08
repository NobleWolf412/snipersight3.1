# A/B Calibration Tests

> 14 nodes

## Key Concepts

- **CalibrationAgainstTheLiveStore** (10 connections) — `app/tests/test_abtest.py`
- **all_tracked_symbols()** (9 connections) — `app/engine/universe.py`
- **._cal()** (5 connections) — `app/tests/test_abtest.py`
- **.test_the_scale_in_adds_are_actually_graded_somewhere()** (4 connections) — `app/tests/test_abtest.py`
- **.test_the_book_still_exercises_the_crossing_leg()** (3 connections) — `app/tests/test_abtest.py`
- **.setUpClass()** (2 connections) — `app/tests/test_abtest.py`
- **.test_every_recorded_trade_is_reproduced_to_the_cent()** (2 connections) — `app/tests/test_abtest.py`
- **.test_the_replay_and_the_record_hold_the_same_trades()** (2 connections) — `app/tests/test_abtest.py`
- **.test_the_harness_says_it_is_trustworthy()** (2 connections) — `app/tests/test_abtest.py`
- **Every symbol with stored candles — the deterministic reprocessing set.** (1 connections) — `app/engine/universe.py`
- **.tearDownClass()** (1 connections) — `app/tests/test_abtest.py`
- **THE pin: the harness reproduces the book production actually wrote,     trade b** (1 connections) — `app/tests/test_abtest.py`
- **calibrate() sets the adds aside on the promise that they are graded         by** (1 connections) — `app/tests/test_abtest.py`
- **Coverage, asserted rather than assumed. The maker fills agreed all         alon** (1 connections) — `app/tests/test_abtest.py`

## Relationships

- [A/B Test Engine](A-B_Test_Engine.md) (2 shared connections)
- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (2 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (1 shared connections)
- [Simulator Convention Tests](Simulator_Convention_Tests.md) (1 shared connections)

## Source Files

- `app/engine/universe.py`
- `app/tests/test_abtest.py`

## Audit Trail

- EXTRACTED: 38 (86%)
- INFERRED: 6 (14%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*