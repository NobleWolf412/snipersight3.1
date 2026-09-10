# Cold Start Live Loop Tests

> 11 nodes

## Key Concepts

- **test_cold_start.py** (9 connections) — `app/tests/test_cold_start.py`
- **OnboardingPathIsCallable** (4 connections) — `app/tests/test_cold_start.py`
- **LiveLoopUsesIt** (3 connections) — `app/tests/test_cold_start.py`
- **.test_a_warm_symbol_still_resumes_incrementally()** (2 connections) — `app/tests/test_cold_start.py`
- **.test_onboarding_and_the_live_loop_share_one_floor()** (2 connections) — `app/tests/test_cold_start.py`
- **.test_the_live_loop_no_longer_defaults_to_zero()** (1 connections) — `app/tests/test_cold_start.py`
- **.test_run_engines_resolves_every_name_it_uses()** (1 connections) — `app/tests/test_cold_start.py`
- **Cold-start import floor — the 1970 bug.  `live.cycle` computed its incremental s** (1 connections) — `app/tests/test_cold_start.py`
- **The fix must not turn every cycle into a full re-import — the whole         loop** (1 connections) — `app/tests/test_cold_start.py`
- **`run_engines` is the recovery path this whole file is about. It spent a     wind** (1 connections) — `app/tests/test_cold_start.py`
- **If they disagreed, a symbol would import different history depending         on** (1 connections) — `app/tests/test_cold_start.py`

## Relationships

- [Missing History Tests](Missing_History_Tests.md) (2 shared connections)
- [History Floor Tests](History_Floor_Tests.md) (1 shared connections)
- [Mission Rail & Radar UI](Mission_Rail_%26_Radar_UI.md) (1 shared connections)
- [Refresh Repair Tests](Refresh_Repair_Tests.md) (1 shared connections)
- [History Repair Tests](History_Repair_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_cold_start.py`

## Audit Trail

- EXTRACTED: 26 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*