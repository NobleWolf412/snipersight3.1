# Setup Trace Tests

> 23 nodes

## Key Concepts

- **_seed()** (9 connections) — `app/tests/test_setup_trace.py`
- **.trace()** (9 connections) — `app/tests/test_setup_trace.py`
- **test_setup_trace.py** (8 connections) — `app/tests/test_setup_trace.py`
- **_TraceCase** (6 connections) — `app/tests/test_setup_trace.py`
- **TestSetupTraceOrdering** (5 connections) — `app/tests/test_setup_trace.py`
- **TestSetupTraceHonestyFlags** (5 connections) — `app/tests/test_setup_trace.py`
- **.test_every_stage_carries_the_value_it_compared()** (4 connections) — `app/tests/test_setup_trace.py`
- **.test_stages_with_no_facts_are_skipped_not_failed()** (4 connections) — `app/tests/test_setup_trace.py`
- **TestSetupTraceRiskRejection** (4 connections) — `app/tests/test_setup_trace.py`
- **.test_superseded_engine_version_is_named_not_hidden()** (4 connections) — `app/tests/test_setup_trace.py`
- **.test_known_id_returns_every_stage_in_pipeline_order()** (3 connections) — `app/tests/test_setup_trace.py`
- **.test_risk_rejected_setup_surfaces_its_reasons()** (3 connections) — `app/tests/test_setup_trace.py`
- **.test_reduced_is_a_warning_not_a_failure()** (3 connections) — `app/tests/test_setup_trace.py`
- **TestSetupTraceUnknownId** (3 connections) — `app/tests/test_setup_trace.py`
- **.test_pre_baseline_setup_is_returned_but_flagged()** (3 connections) — `app/tests/test_setup_trace.py`
- **.test_unknown_id_is_a_404_not_an_empty_drawer()** (2 connections) — `app/tests/test_setup_trace.py`
- **.test_state_history_is_ordered_oldest_first()** (2 connections) — `app/tests/test_setup_trace.py`
- **/api/setup-trace — the per-setup "why didn't THIS one fire?" journey.  The funne** (1 connections) — `app/tests/test_setup_trace.py`
- **Write one setup's fact chain. Only the kinds passed are recorded, so a     test** (1 connections) — `app/tests/test_setup_trace.py`
- **A tick alone says the gate ran, not what it decided on.** (1 connections) — `app/tests/test_setup_trace.py`
- **No order fact means the pipeline stopped, not that the order failed.         Ren** (1 connections) — `app/tests/test_setup_trace.py`
- **History is not absence. The trace resolves, and says which it is.** (1 connections) — `app/tests/test_setup_trace.py`
- **A trace pinned to the current version would 404 on a setup the         operator** (1 connections) — `app/tests/test_setup_trace.py`

## Relationships

- [API Server Endpoints](API_Server_Endpoints.md) (1 shared connections)

## Source Files

- `app/tests/test_setup_trace.py`

## Audit Trail

- EXTRACTED: 83 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*