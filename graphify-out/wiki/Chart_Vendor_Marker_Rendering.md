# Chart Vendor Marker Rendering

> 49 nodes

## Key Concepts

- **ExecutionPlan** (41 connections) — `app/engine/contracts.py`
- **execution.py** (29 connections) — `app/engine/execution.py`
- **OrderKind** (27 connections) — `app/engine/contracts.py`
- **OrderIntent** (26 connections) — `app/engine/contracts.py`
- **RiskDecision** (25 connections) — `app/engine/contracts.py`
- **PhemexError** (24 connections) — `app/engine/phemex_private.py`
- **to_wire()** (18 connections) — `app/engine/contracts.py`
- **Broker** (18 connections) — `app/engine/execution.py`
- **BrokerExecution** (16 connections) — `app/engine/contracts.py`
- **AmbiguousSubmission** (15 connections) — `app/engine/phemex_private.py`
- **DispatchRejected** (14 connections) — `app/engine/execution.py`
- **.dispatch()** (14 connections) — `app/engine/execution.py`
- **Coordinator** (13 connections) — `app/engine/execution.py`
- **autotrader.py** (12 connections) — `app/engine/autotrader.py`
- **monitor_private()** (12 connections) — `app/engine/execution.py`
- **phemex_private.py** (12 connections) — `app/engine/phemex_private.py`
- **build_plan()** (10 connections) — `app/engine/autotrader.py`
- **_plan_from_wire()** (10 connections) — `app/engine/execution.py`
- **enqueue()** (7 connections) — `app/engine/execution.py`
- **monitor_paper()** (7 connections) — `app/engine/execution.py`
- **_ensure()** (5 connections) — `app/engine/execution.py`
- **_audit_event()** (5 connections) — `app/engine/execution.py`
- **_decision_hash()** (5 connections) — `app/engine/execution.py`
- **_complete_shadow_comparison()** (5 connections) — `app/engine/execution.py`
- **.submit()** (4 connections) — `app/engine/execution.py`
- *... and 24 more nodes in this community*

## Relationships

- [ProtectedBroker](ProtectedBroker.md) (36 shared connections)
- [Chart Vendor Series](Chart_Vendor_Series.md) (31 shared connections)
- [A/B Calibration Tests](A-B_Calibration_Tests.md) (22 shared connections)
- [Shared Pipeline Loop Tests](Shared_Pipeline_Loop_Tests.md) (20 shared connections)
- [Chart Vendor Renderer Base](Chart_Vendor_Renderer_Base.md) (9 shared connections)
- [Cycle Detection Engine](Cycle_Detection_Engine.md) (8 shared connections)
- [Market Data Importer](Market_Data_Importer.md) (6 shared connections)
- [Notification Delivery](Notification_Delivery.md) (5 shared connections)
- [CustodyOverridesTheSimulatorsStory](CustodyOverridesTheSimulatorsStory.md) (4 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (4 shared connections)
- [One Source of Truth JS Tests](One_Source_of_Truth_JS_Tests.md) (3 shared connections)
- [test_phemex_private.py](test_phemex_private.py.md) (3 shared connections)

## Source Files

- `app/engine/autotrader.py`
- `app/engine/contracts.py`
- `app/engine/execution.py`
- `app/engine/phemex_private.py`

## Audit Trail

- EXTRACTED: 266 (64%)
- INFERRED: 149 (36%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*