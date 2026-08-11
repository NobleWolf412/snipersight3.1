# Notification Delivery

> 25 nodes

## Key Concepts

- **lifecycle.py** (22 connections) — `app/engine/lifecycle.py`
- **monitor()** (12 connections) — `app/engine/lifecycle.py`
- **record_order()** (10 connections) — `app/engine/lifecycle.py`
- **LifecycleBlocked** (9 connections) — `app/engine/lifecycle.py`
- **ensure_emergency()** (9 connections) — `app/engine/lifecycle.py`
- **Decimal** (8 connections)
- **ensure_stop()** (8 connections) — `app/engine/lifecycle.py`
- **ensure_target()** (8 connections) — `app/engine/lifecycle.py`
- **_status()** (7 connections) — `app/engine/lifecycle.py`
- **_ensure()** (7 connections) — `app/engine/lifecycle.py`
- **recover_child_orders()** (7 connections) — `app/engine/lifecycle.py`
- **_persist_executions()** (4 connections) — `app/engine/lifecycle.py`
- **_weighted()** (4 connections) — `app/engine/lifecycle.py`
- **_cancel_and_confirm()** (3 connections) — `app/engine/lifecycle.py`
- **_position_event()** (2 connections) — `app/engine/lifecycle.py`
- **_entry_identity()** (2 connections) — `app/engine/lifecycle.py`
- **_flat_count()** (2 connections) — `app/engine/lifecycle.py`
- **RuntimeError** (1 connections)
- **Promotion-grade private lifecycle evidence.  Flatness proves custody ended; it d** (1 connections) — `app/engine/lifecycle.py`
- **Record the venue identity of an already accepted child order.** (1 connections) — `app/engine/lifecycle.py`
- **Create or resize the deterministic standalone stop before relying on it.** (1 connections) — `app/engine/lifecycle.py`
- **Create or resize one deterministic reduce-only target, restart-safely.** (1 connections) — `app/engine/lifecycle.py`
- **Submit one restart-recoverable reduce-only emergency close.** (1 connections) — `app/engine/lifecycle.py`
- **Resolve pre-acceptance crash windows by deterministic client identity.** (1 connections) — `app/engine/lifecycle.py`
- **Qualify exact bot-owned TESTNET exits; everything uncertain stays open.** (1 connections) — `app/engine/lifecycle.py`

## Relationships

- [Chart Vendor Marker Rendering](Chart_Vendor_Marker_Rendering.md) (6 shared connections)
- [Chart Vendor Line Renderers](Chart_Vendor_Line_Renderers.md) (5 shared connections)
- [Market Data Importer](Market_Data_Importer.md) (2 shared connections)
- [A/B Calibration Tests](A-B_Calibration_Tests.md) (1 shared connections)

## Source Files

- `app/engine/lifecycle.py`

## Audit Trail

- EXTRACTED: 129 (98%)
- INFERRED: 3 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*