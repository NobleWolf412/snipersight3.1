# Chart Vendor Marker Rendering

> 74 nodes

## Key Concepts

- **BrokerOrder** (50 connections) — `app/engine/contracts.py`
- **ExecutionPlan** (41 connections) — `app/engine/contracts.py`
- **execution.py** (29 connections) — `app/engine/execution.py`
- **PhemexBroker** (29 connections) — `app/engine/phemex_private.py`
- **OrderKind** (27 connections) — `app/engine/contracts.py`
- **PhemexError** (24 connections) — `app/engine/phemex_private.py`
- **Broker** (18 connections) — `app/engine/execution.py`
- **BrokerExecution** (16 connections) — `app/engine/contracts.py`
- **AmbiguousSubmission** (15 connections) — `app/engine/phemex_private.py`
- **._request()** (15 connections) — `app/engine/phemex_private.py`
- **DispatchRejected** (14 connections) — `app/engine/execution.py`
- **.dispatch()** (14 connections) — `app/engine/execution.py`
- **Coordinator** (13 connections) — `app/engine/execution.py`
- **monitor_private()** (12 connections) — `app/engine/execution.py`
- **phemex_private.py** (12 connections) — `app/engine/phemex_private.py`
- **Decimal** (12 connections)
- **.submit()** (12 connections) — `app/engine/phemex_private.py`
- **._order()** (11 connections) — `app/engine/phemex_private.py`
- **.replace()** (11 connections) — `app/engine/phemex_private.py`
- **_plan_from_wire()** (10 connections) — `app/engine/execution.py`
- **.submit_protective_stop()** (9 connections) — `app/engine/phemex_private.py`
- **.submit_target()** (9 connections) — `app/engine/phemex_private.py`
- **enqueue()** (7 connections) — `app/engine/execution.py`
- **monitor_paper()** (7 connections) — `app/engine/execution.py`
- **.validate_plan()** (7 connections) — `app/engine/phemex_private.py`
- *... and 49 more nodes in this community*

## Relationships

- [Chart Vendor Series](Chart_Vendor_Series.md) (41 shared connections)
- [A/B Calibration Tests](A-B_Calibration_Tests.md) (18 shared connections)
- [Shared Pipeline Loop Tests](Shared_Pipeline_Loop_Tests.md) (17 shared connections)
- [Notification Delivery](Notification_Delivery.md) (9 shared connections)
- [Chart Vendor Renderer Base](Chart_Vendor_Renderer_Base.md) (7 shared connections)
- [Cycle Detection Engine](Cycle_Detection_Engine.md) (7 shared connections)
- [Market Data Importer](Market_Data_Importer.md) (4 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (4 shared connections)
- [execsim.py](execsim.py.md) (3 shared connections)
- [CustodyOverridesTheSimulatorsStory](CustodyOverridesTheSimulatorsStory.md) (3 shared connections)
- [One Source of Truth JS Tests](One_Source_of_Truth_JS_Tests.md) (2 shared connections)
- [test_phemex_private.py](test_phemex_private.py.md) (1 shared connections)

## Source Files

- `app/engine/contracts.py`
- `app/engine/execution.py`
- `app/engine/phemex_private.py`

## Audit Trail

- EXTRACTED: 417 (74%)
- INFERRED: 143 (26%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*