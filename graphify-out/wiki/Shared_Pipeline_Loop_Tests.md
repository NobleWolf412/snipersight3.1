# Shared Pipeline Loop Tests

> 14 nodes

## Key Concepts

- **test_pipeline_gates.py** (7 connections) — `app/tests/test_pipeline_gates.py`
- **VocabularyCase** (6 connections) — `app/tests/test_pipeline_gates.py`
- **OneLoopCase** (4 connections) — `app/tests/test_pipeline_gates.py`
- **fake_engine()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.setUp()** (2 connections) — `app/tests/test_pipeline_gates.py`
- **.test_live_cycle_uses_the_shared_loop()** (1 connections) — `app/tests/test_pipeline_gates.py`
- **.test_ingest_uses_the_shared_loop()** (1 connections) — `app/tests/test_pipeline_gates.py`
- **.test_every_reason_setups_can_write_is_canonical()** (1 connections) — `app/tests/test_pipeline_gates.py`
- **.test_every_canonical_reason_has_a_funnel_sentence()** (1 connections) — `app/tests/test_pipeline_gates.py`
- **.test_every_gate_has_a_funnel_sentence()** (1 connections) — `app/tests/test_pipeline_gates.py`
- **.test_the_endpoint_marks_unlabelled_reasons()** (1 connections) — `app/tests/test_pipeline_gates.py`
- **The engine loop is one function, and absence has a name.  Two defects this file** (1 connections) — `app/tests/test_pipeline_gates.py`
- **Both runners must call THE loop — asserted on source, the same way the     roste** (1 connections) — `app/tests/test_pipeline_gates.py`
- **The cross-boundary drift guard. Reasons are minted in Python and given     sente** (1 connections) — `app/tests/test_pipeline_gates.py`

## Relationships

- [Pipeline Gate Tests](Pipeline_Gate_Tests.md) (2 shared connections)
- [Live Scanner Loop](Live_Scanner_Loop.md) (1 shared connections)
- [Engine Fault Row Tests](Engine_Fault_Row_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_pipeline_gates.py`

## Audit Trail

- EXTRACTED: 30 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*