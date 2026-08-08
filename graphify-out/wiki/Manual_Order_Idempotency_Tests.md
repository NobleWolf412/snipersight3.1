# Manual Order Idempotency Tests

> 12 nodes

## Key Concepts

- **._rows()** (7 connections) — `app/tests/test_manual.py`
- **.test_a_settled_order_id_is_not_answered_as_still_armed()** (7 connections) — `app/tests/test_manual.py`
- **.test_a_refused_arm_writes_nothing_at_all()** (5 connections) — `app/tests/test_manual.py`
- **.test_the_same_order_arriving_twice_is_a_receipt_not_a_refusal()** (5 connections) — `app/tests/test_manual.py`
- **.test_a_changed_plan_is_not_the_same_order()** (5 connections) — `app/tests/test_manual.py`
- **.test_two_plans_cannot_share_one_order_id()** (5 connections) — `app/tests/test_manual.py`
- **Every fact and every manifest — the whole of what a write is.** (1 connections) — `app/tests/test_manual.py`
- **Not "no second intent" — NOTHING. The guard sits ahead of the cost         mani** (1 connections) — `app/tests/test_manual.py`
- **THE REPORTED BUG. `created_at` is chosen by the caller so a retry         rebui** (1 connections) — `app/tests/test_manual.py`
- **Same second, different levels — a nudge between two taps. That is         not t** (1 connections) — `app/tests/test_manual.py`
- **The receipt is only a receipt while the order is still on the book.         Rep** (1 connections) — `app/tests/test_manual.py`
- **A LONG and a SHORT armed on one chart within the same second is a         legit** (1 connections) — `app/tests/test_manual.py`

## Relationships

- [Manual Book Tests](Manual_Book_Tests.md) (10 shared connections)
- [Manual Arm Validation Tests](Manual_Arm_Validation_Tests.md) (6 shared connections)
- [Manual Settlement Tests](Manual_Settlement_Tests.md) (2 shared connections)

## Source Files

- `app/tests/test_manual.py`

## Audit Trail

- EXTRACTED: 40 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*