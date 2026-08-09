# Retired Symbol Staleness Tests

> 7 nodes

## Key Concepts

- **test_abtest.py** (9 connections) — `app/tests/test_abtest.py`
- **Summary** (3 connections) — `app/tests/test_abtest.py`
- **Determinism** (2 connections) — `app/tests/test_abtest.py`
- **.test_same_inputs_produce_identical_results()** (2 connections) — `app/tests/test_abtest.py`
- **.test_missed_orders_are_counted_but_never_scored_as_zero()** (1 connections) — `app/tests/test_abtest.py`
- **.test_empty_book_refuses_rather_than_reporting_zero()** (1 connections) — `app/tests/test_abtest.py`
- **2x2 replay harness — the properties that make its verdict believable.  The har** (1 connections) — `app/tests/test_abtest.py`

## Relationships

- [Simulator Convention Tests](Simulator_Convention_Tests.md) (3 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (1 shared connections)
- [CalibrationAgainstTheLiveStore](CalibrationAgainstTheLiveStore.md) (1 shared connections)
- [momentum.py](momentum.py.md) (1 shared connections)
- [test_orientation_and_axes.js](test_orientation_and_axes.js.md) (1 shared connections)

## Source Files

- `app/tests/test_abtest.py`

## Audit Trail

- EXTRACTED: 19 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*