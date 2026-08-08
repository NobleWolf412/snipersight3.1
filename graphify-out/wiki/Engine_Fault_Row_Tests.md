# Engine Fault Row Tests

> 8 nodes

## Key Concepts

- **FaultCase** (8 connections) — `app/tests/test_pipeline_gates.py`
- **.faults()** (4 connections) — `app/tests/test_pipeline_gates.py`
- **.test_a_throwing_engine_becomes_a_row()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.test_recurrence_counts_and_first_seen_survives()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.test_a_clean_run_clears_the_row()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.setUp()** (1 connections) — `app/tests/test_pipeline_gates.py`
- **.tearDown()** (1 connections) — `app/tests/test_pipeline_gates.py`
- **Engine exceptions become current state, not archaeology.      The one loop alrea** (1 connections) — `app/tests/test_pipeline_gates.py`

## Relationships

- [Shared Pipeline Loop Tests](Shared_Pipeline_Loop_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_pipeline_gates.py`

## Audit Trail

- EXTRACTED: 21 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*