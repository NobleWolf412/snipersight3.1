# Manual Version Migration Tests

> 14 nodes

## Key Concepts

- **.write_v01()** (8 connections) — `app/tests/test_manual.py`
- **.test_an_old_trade_that_already_settled_is_not_settled_again()** (8 connections) — `app/tests/test_manual.py`
- **.test_an_intent_still_open_under_the_old_tag_is_not_stranded()** (7 connections) — `app/tests/test_manual.py`
- **.test_an_old_intent_settles_under_the_version_that_settled_it()** (7 connections) — `app/tests/test_manual.py`
- **.test_the_old_tag_is_isolated_from_every_strategy_query_too()** (7 connections) — `app/tests/test_manual.py`
- **.v01_intent()** (6 connections) — `app/tests/test_manual.py`
- **.test_an_old_open_order_can_still_be_cancelled()** (5 connections) — `app/tests/test_manual.py`
- **.test_the_settled_book_does_not_blank_itself_when_the_tag_moves()** (3 connections) — `app/tests/test_manual.py`
- **A fact under the RETIRED tag, written the way the old code wrote it.** (1 connections) — `app/tests/test_manual.py`
- **The defect the bump would otherwise have shipped.          The resolver finds** (1 connections) — `app/tests/test_manual.py`
- **The exit fact names the code that PRODUCED it, which after the bump         is** (1 connections) — `app/tests/test_manual.py`
- **`done` reads across versions too. Without that, every trade the v0.1         bo** (1 connections) — `app/tests/test_manual.py`
- **An operator's record is their record across a version bump. A book         that** (1 connections) — `app/tests/test_manual.py`
- **The isolation rule is what the separate book is FOR, and it has to         hold** (1 connections) — `app/tests/test_manual.py`

## Relationships

- [Manual Book Tests](Manual_Book_Tests.md) (10 shared connections)
- [Manual Arm Validation Tests](Manual_Arm_Validation_Tests.md) (8 shared connections)
- [Manual Settlement Tests](Manual_Settlement_Tests.md) (5 shared connections)

## Source Files

- `app/tests/test_manual.py`

## Audit Trail

- EXTRACTED: 57 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*