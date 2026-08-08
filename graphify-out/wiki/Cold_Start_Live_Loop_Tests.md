# Cold Start Live Loop Tests

> 6 nodes

## Key Concepts

- **test_cold_start.py** (8 connections) — `app/tests/test_cold_start.py`
- **LiveLoopUsesIt** (3 connections) — `app/tests/test_cold_start.py`
- **.test_a_warm_symbol_still_resumes_incrementally()** (2 connections) — `app/tests/test_cold_start.py`
- **.test_the_live_loop_no_longer_defaults_to_zero()** (1 connections) — `app/tests/test_cold_start.py`
- **Cold-start import floor — the 1970 bug.  `live.cycle` computed its incremental s** (1 connections) — `app/tests/test_cold_start.py`
- **The fix must not turn every cycle into a full re-import — the whole         loop** (1 connections) — `app/tests/test_cold_start.py`

## Relationships

- [Missing History Tests](Missing_History_Tests.md) (2 shared connections)
- [History Floor Tests](History_Floor_Tests.md) (1 shared connections)
- [Onboarding Path Tests](Onboarding_Path_Tests.md) (1 shared connections)
- [Refresh Repair Tests](Refresh_Repair_Tests.md) (1 shared connections)
- [History Repair Tests](History_Repair_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_cold_start.py`

## Audit Trail

- EXTRACTED: 16 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*