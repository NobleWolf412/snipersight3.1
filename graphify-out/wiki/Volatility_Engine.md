# Volatility Engine

> 24 nodes

## Key Concepts

- **TempStore** (8 connections) — `app/tests/test_mode_sizing.py`
- **test_mode_sizing.py** (7 connections) — `app/tests/test_mode_sizing.py`
- **ReplayIsPaperAlways** (6 connections) — `app/tests/test_mode_sizing.py`
- **DispatchCarriesTheModeR** (6 connections) — `app/tests/test_mode_sizing.py`
- **.test_the_replay_sizes_at_paper_r_and_says_so_on_the_fact()** (5 connections) — `app/tests/test_mode_sizing.py`
- **.test_a_zero_r_add_is_rejected_inside_the_replay_too()** (5 connections) — `app/tests/test_mode_sizing.py`
- **.test_no_decision_ever_books_approved_at_zero_risk()** (5 connections) — `app/tests/test_mode_sizing.py`
- **candle()** (4 connections) — `app/tests/test_mode_sizing.py`
- **.validated_setup()** (4 connections) — `app/tests/test_mode_sizing.py`
- **.decisions()** (4 connections) — `app/tests/test_mode_sizing.py`
- **ArmingIsPaperAlways** (4 connections) — `app/tests/test_mode_sizing.py`
- **.test_forming_facts_are_sized_at_paper_r()** (2 connections) — `app/tests/test_mode_sizing.py`
- **.test_plan_and_intent_quantity_stay_consistent()** (2 connections) — `app/tests/test_mode_sizing.py`
- **.setUp()** (1 connections) — `app/tests/test_mode_sizing.py`
- **.tearDown()** (1 connections) — `app/tests/test_mode_sizing.py`
- **.test_testnet_quantity_is_the_paper_quantity_at_the_r_ratio()** (1 connections) — `app/tests/test_mode_sizing.py`
- **.test_paper_and_shadow_quantities_are_untouched()** (1 connections) — `app/tests/test_mode_sizing.py`
- **Mode-aware R sizing — the properties that make paper a rehearsal for live.  The** (1 connections) — `app/tests/test_mode_sizing.py`
- **A DECISION fact explains itself: it records the pct it was sized         with an** (1 connections) — `app/tests/test_mode_sizing.py`
- **size_order() refusing 0R is not enough — run() computes `intended`         itsel** (1 connections) — `app/tests/test_mode_sizing.py`
- **The belt-and-braces guard, exercised end to end: whatever path a         decisio** (1 connections) — `app/tests/test_mode_sizing.py`
- **The armed order bakes its size in at arming; that size is paper's         2% of** (1 connections) — `app/tests/test_mode_sizing.py`
- **The one place testnet/live R binds: quantity scaling at plan build.** (1 connections) — `app/tests/test_mode_sizing.py`
- **execution.dispatch requires plan/intent quantity equality; the         scale mus** (1 connections) — `app/tests/test_mode_sizing.py`

## Relationships

- [Cycle Detection Engine](Cycle_Detection_Engine.md) (4 shared connections)
- [A/B Calibration Tests](A-B_Calibration_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_mode_sizing.py`

## Audit Trail

- EXTRACTED: 69 (95%)
- INFERRED: 4 (5%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*