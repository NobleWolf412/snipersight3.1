# Trailing Stop Tests

> 11 nodes

## Key Concepts

- **.trail_intent()** (8 connections) — `app/tests/test_manual.py`
- **.test_the_ratchet_cannot_act_on_its_own_bar()** (6 connections) — `app/tests/test_manual.py`
- **.test_without_trailing_nothing_changed()** (6 connections) — `app/tests/test_manual.py`
- **.test_the_trail_never_loosens()** (5 connections) — `app/tests/test_manual.py`
- **.test_status_reports_the_ratcheted_stop_for_the_chart()** (4 connections) — `app/tests/test_manual.py`
- **.test_book_counts_a_profitable_trail_as_a_win()** (4 connections) — `app/tests/test_manual.py`
- **.test_a_hair_trigger_trail_is_refused()** (2 connections) — `app/tests/test_manual.py`
- **A bar that makes the new high AND falls through the stop that high         impl** (1 connections) — `app/tests/test_manual.py`
- **An adverse bar moves nothing: the stop only ratchets toward price.** (1 connections) — `app/tests/test_manual.py`
- **The gold SL line draws `current_stop` — showing the original stop on         a** (1 connections) — `app/tests/test_manual.py`
- **trail_r=None must resolve byte-identically to the pre-trailing         resolver** (1 connections) — `app/tests/test_manual.py`

## Relationships

- [Manual Arm Validation Tests](Manual_Arm_Validation_Tests.md) (7 shared connections)
- [Manual Settlement Tests](Manual_Settlement_Tests.md) (7 shared connections)
- [Manual Book Tests](Manual_Book_Tests.md) (5 shared connections)

## Source Files

- `app/tests/test_manual.py`

## Audit Trail

- EXTRACTED: 39 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*