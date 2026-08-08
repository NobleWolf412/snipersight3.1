# Bias Policy Validation Tests

> 8 nodes

## Key Concepts

- **PolicyValidation** (6 connections) — `app/tests/test_bias.py`
- **.test_unknown_may_never_be_anything_but_allow()** (2 connections) — `app/tests/test_bias.py`
- **.test_a_policy_silent_on_an_alignment_is_rejected()** (2 connections) — `app/tests/test_bias.py`
- **.test_a_complete_policy_validates_and_is_returned()** (1 connections) — `app/tests/test_bias.py`
- **.test_an_unknown_action_is_a_programming_error()** (1 connections) — `app/tests/test_bias.py`
- **.test_a_typo_in_an_alignment_name_is_caught()** (1 connections) — `app/tests/test_bias.py`
- **THE rule. `setups.py` scored a missing HTF reading identically to a         con** (1 connections) — `app/tests/test_bias.py`
- **A playbook that has not thought about MIXED has not declared a         policy,** (1 connections) — `app/tests/test_bias.py`

## Relationships

- [Bias Alignment Tests](Bias_Alignment_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_bias.py`

## Audit Trail

- EXTRACTED: 15 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*