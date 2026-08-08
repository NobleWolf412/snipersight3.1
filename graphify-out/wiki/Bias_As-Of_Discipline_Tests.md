# Bias As-Of Discipline Tests

> 13 nodes

## Key Concepts

- **AsOfDiscipline** (10 connections) — `app/tests/test_bias.py`
- **.test_evidence_never_sees_the_future()** (2 connections) — `app/tests/test_bias.py`
- **.test_evidence_must_be_recent()** (2 connections) — `app/tests/test_bias.py`
- **.test_check_only_looks_for_evidence_when_the_policy_asks()** (2 connections) — `app/tests/test_bias.py`
- **.setUp()** (1 connections) — `app/tests/test_bias.py`
- **.test_a_reading_never_sees_the_future()** (1 connections) — `app/tests/test_bias.py`
- **.test_a_rung_with_nothing_confirmed_yet_reads_none()** (1 connections) — `app/tests/test_bias.py`
- **.test_disagreeing_rungs_surface_as_mixed()** (1 connections) — `app/tests/test_bias.py`
- **.test_evidence_must_be_in_the_trades_direction()** (1 connections) — `app/tests/test_bias.py`
- **`confirmed_at` is when the engine could have known. Reading past it is     look** (1 connections) — `app/tests/test_bias.py`
- **The 400 break must be invisible at as_of=350 even though it is in         the s** (1 connections) — `app/tests/test_bias.py`
- **A break twenty bars back is the prevailing structure, not a change         in i** (1 connections) — `app/tests/test_bias.py`
- **A fact must never claim a test was run that was not.** (1 connections) — `app/tests/test_bias.py`

## Relationships

- [Bias Alignment Tests](Bias_Alignment_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_bias.py`

## Audit Trail

- EXTRACTED: 25 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*