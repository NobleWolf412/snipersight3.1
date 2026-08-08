# Scale-Out Settlement Tests

> 10 nodes

## Key Concepts

- **.scale_bars()** (7 connections) — `app/tests/test_manual.py`
- **.test_half_off_at_a_level_blends_two_settlements()** (6 connections) — `app/tests/test_manual.py`
- **.test_the_blend_is_reproducible_from_the_recorded_legs_alone()** (6 connections) — `app/tests/test_manual.py`
- **.test_each_leg_pays_funding_for_its_own_holding_period()** (6 connections) — `app/tests/test_manual.py`
- **.test_every_settled_trade_in_the_book_reproduces_its_own_headline()** (5 connections) — `app/tests/test_manual.py`
- **Fill at 100, rung at 104 on bar 1, target 110 on bar 2.** (1 connections) — `app/tests/test_manual.py`
- **The headline case: half off at +2R, the rest rides to the target.          Han** (1 connections) — `app/tests/test_manual.py`
- **The house rule, as a property rather than a promise.          `blend_r` is the** (1 connections) — `app/tests/test_manual.py`
- **The same property, swept over a book of mixed shapes.          One passing exa** (1 connections) — `app/tests/test_manual.py`
- **A rung taken at bar 1 did not hold the position to bar 2.          Charging th** (1 connections) — `app/tests/test_manual.py`

## Relationships

- [Manual Settlement Tests](Manual_Settlement_Tests.md) (8 shared connections)
- [Manual Arm Validation Tests](Manual_Arm_Validation_Tests.md) (5 shared connections)
- [Manual Book Tests](Manual_Book_Tests.md) (4 shared connections)

## Source Files

- `app/tests/test_manual.py`

## Audit Trail

- EXTRACTED: 35 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*