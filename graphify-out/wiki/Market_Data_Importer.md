# Market Data Importer

> 28 nodes

## Key Concepts

- **positions.py** (23 connections) — `app/engine/positions.py`
- **apply_fill()** (9 connections) — `app/engine/positions.py`
- **ProtectionFailed** (8 connections) — `app/engine/positions.py`
- **_ensure()** (8 connections) — `app/engine/positions.py`
- **reconcile()** (8 connections) — `app/engine/positions.py`
- **ControlOwner** (7 connections) — `app/engine/contracts.py`
- **Decimal** (7 connections)
- **monitor_closures()** (7 connections) — `app/engine/positions.py`
- **ReconciliationBlocked** (6 connections) — `app/engine/positions.py`
- **_event()** (5 connections) — `app/engine/positions.py`
- **_signed_broker_quantity()** (5 connections) — `app/engine/positions.py`
- **manual_override()** (5 connections) — `app/engine/positions.py`
- **return_control()** (5 connections) — `app/engine/positions.py`
- **_execution_event_once()** (4 connections) — `app/engine/positions.py`
- **_position_quantity()** (4 connections) — `app/engine/positions.py`
- **private_environments_with_exposure()** (3 connections) — `app/engine/positions.py`
- **require_reconciled()** (3 connections) — `app/engine/positions.py`
- **RuntimeError** (2 connections)
- **_known_order_clients()** (2 connections) — `app/engine/positions.py`
- **managed()** (2 connections) — `app/engine/positions.py`
- **Reconciled position custody and mandatory protection.  No new TESTNET/LIVE entry** (1 connections) — `app/engine/positions.py`
- **Record one operational finding per stable payload, not per poll.** (1 connections) — `app/engine/positions.py`
- **Private environments that still require custody, regardless of mode.** (1 connections) — `app/engine/positions.py`
- **Compare broker truth to durable local custody and record the verdict.** (1 connections) — `app/engine/positions.py`
- **Confirm venue-flat custody twice before closing a durable position.      Attache** (1 connections) — `app/engine/positions.py`
- *... and 3 more nodes in this community*

## Relationships

- [Chart Vendor Marker Rendering](Chart_Vendor_Marker_Rendering.md) (6 shared connections)
- [Shared Pipeline Loop Tests](Shared_Pipeline_Loop_Tests.md) (4 shared connections)
- [A/B Calibration Tests](A-B_Calibration_Tests.md) (3 shared connections)
- [Notification Delivery](Notification_Delivery.md) (2 shared connections)

## Source Files

- `app/engine/contracts.py`
- `app/engine/positions.py`

## Audit Trail

- EXTRACTED: 122 (93%)
- INFERRED: 9 (7%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*