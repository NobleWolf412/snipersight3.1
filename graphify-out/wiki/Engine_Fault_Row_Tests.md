# Engine Fault Row Tests

> 4 nodes

## Key Concepts

- **test_abtest.py** (11 connections) — `app/tests/test_abtest.py`
- **Determinism** (2 connections) — `app/tests/test_abtest.py`
- **.test_same_inputs_produce_identical_results()** (2 connections) — `app/tests/test_abtest.py`
- **2x2 replay harness — the properties that make its verdict believable.  The har** (1 connections) — `app/tests/test_abtest.py`

## Relationships

- [CalibrationAgainstTheLiveStore](CalibrationAgainstTheLiveStore.md) (3 shared connections)
- [T](T.md) (2 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (1 shared connections)
- [EntryModelAuthority](EntryModelAuthority.md) (1 shared connections)
- [Next Wake Math Tests](Next_Wake_Math_Tests.md) (1 shared connections)
- [Chart Vendor Hit Testing](Chart_Vendor_Hit_Testing.md) (1 shared connections)
- [.ol](ol.md) (1 shared connections)

## Source Files

- `app/tests/test_abtest.py`

## Audit Trail

- EXTRACTED: 16 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*