# Cycle Detection Engine

> 28 nodes

## Key Concepts

- **AutomationMode** (40 connections) — `app/engine/contracts.py`
- **automation.py** (18 connections) — `app/engine/automation.py`
- **transition()** (9 connections) — `app/engine/automation.py`
- **ModeConflict** (7 connections) — `app/engine/automation.py`
- **ModeRejected** (7 connections) — `app/engine/automation.py`
- **current()** (7 connections) — `app/engine/automation.py`
- **status()** (6 connections) — `app/engine/automation.py`
- **start_safety_drill()** (6 connections) — `app/engine/automation.py`
- **AutomationStatus** (6 connections) — `app/engine/contracts.py`
- **_ensure()** (5 connections) — `app/engine/automation.py`
- **broker_factory.py** (5 connections) — `app/engine/broker_factory.py`
- **promotion_summary()** (4 connections) — `app/engine/automation.py`
- **observe_safety_event()** (4 connections) — `app/engine/automation.py`
- **BrokerConfigurationError** (4 connections) — `app/engine/broker_factory.py`
- **phemex_for_mode()** (4 connections) — `app/engine/broker_factory.py`
- **_criterion()** (2 connections) — `app/engine/automation.py`
- **safety_drills()** (2 connections) — `app/engine/automation.py`
- **operational_evidence()** (2 connections) — `app/engine/automation.py`
- **RuntimeError** (1 connections)
- **ValueError** (1 connections)
- **history()** (1 connections) — `app/engine/automation.py`
- **Persistent automation mode and promotion-gate authority.  Mode is operational st** (1 connections) — `app/engine/automation.py`
- **Read mode without creating state during a GET request.** (1 connections) — `app/engine/automation.py`
- **Stage one real TESTNET fault drill; this never performs the fault.** (1 connections) — `app/engine/automation.py`
- **Complete only the staged drill whose real code path was observed.** (1 connections) — `app/engine/automation.py`
- *... and 3 more nodes in this community*

## Relationships

- [A/B Calibration Tests](A-B_Calibration_Tests.md) (9 shared connections)
- [Chart Vendor Line Renderers](Chart_Vendor_Line_Renderers.md) (8 shared connections)
- [Chart Vendor Series](Chart_Vendor_Series.md) (7 shared connections)
- [Volatility Engine](Volatility_Engine.md) (4 shared connections)
- [Shared Pipeline Loop Tests](Shared_Pipeline_Loop_Tests.md) (3 shared connections)
- [Diagnostics Engine](Diagnostics_Engine.md) (2 shared connections)
- [test_autonomy_contracts.py](test_autonomy_contracts.py.md) (2 shared connections)
- [cycles.py](cycles.py.md) (1 shared connections)
- [.ja](ja.md) (1 shared connections)
- [Chart Vendor Marker Rendering](Chart_Vendor_Marker_Rendering.md) (1 shared connections)
- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (1 shared connections)
- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (1 shared connections)

## Source Files

- `app/engine/automation.py`
- `app/engine/broker_factory.py`
- `app/engine/contracts.py`

## Audit Trail

- EXTRACTED: 112 (76%)
- INFERRED: 36 (24%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*