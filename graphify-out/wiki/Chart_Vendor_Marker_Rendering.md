# Chart Vendor Marker Rendering

> 46 nodes

## Key Concepts

- **BrokerOrder** (50 connections) — `app/engine/contracts.py`
- **PhemexBroker** (29 connections) — `app/engine/phemex_private.py`
- **PhemexError** (24 connections) — `app/engine/phemex_private.py`
- **._request()** (15 connections) — `app/engine/phemex_private.py`
- **phemex_private.py** (12 connections) — `app/engine/phemex_private.py`
- **Decimal** (12 connections)
- **.submit()** (12 connections) — `app/engine/phemex_private.py`
- **._order()** (11 connections) — `app/engine/phemex_private.py`
- **.replace()** (11 connections) — `app/engine/phemex_private.py`
- **.submit_protective_stop()** (9 connections) — `app/engine/phemex_private.py`
- **.submit_target()** (9 connections) — `app/engine/phemex_private.py`
- **.validate_plan()** (7 connections) — `app/engine/phemex_private.py`
- **.open_orders()** (7 connections) — `app/engine/phemex_private.py`
- **._product()** (6 connections) — `app/engine/phemex_private.py`
- **._multiple()** (6 connections) — `app/engine/phemex_private.py`
- **.order_status()** (6 connections) — `app/engine/phemex_private.py`
- **.executions()** (6 connections) — `app/engine/phemex_private.py`
- **.emergency_close()** (6 connections) — `app/engine/phemex_private.py`
- **.confirm_attached_protection()** (5 connections) — `app/engine/phemex_private.py`
- **ProtectedBroker** (5 connections) — `app/tests/test_position_api.py`
- **._client_id()** (4 connections) — `app/engine/phemex_private.py`
- **.cancel()** (4 connections) — `app/engine/phemex_private.py`
- **.set_leverage()** (4 connections) — `app/engine/phemex_private.py`
- **_urllib_transport()** (3 connections) — `app/engine/phemex_private.py`
- **.refresh_products()** (3 connections) — `app/engine/phemex_private.py`
- *... and 21 more nodes in this community*

## Relationships

- [Chart Vendor Line Renderers](Chart_Vendor_Line_Renderers.md) (34 shared connections)
- [Chart Vendor Series](Chart_Vendor_Series.md) (11 shared connections)
- [Notification Delivery](Notification_Delivery.md) (6 shared connections)
- [Shared Pipeline Loop Tests](Shared_Pipeline_Loop_Tests.md) (5 shared connections)
- [A/B Calibration Tests](A-B_Calibration_Tests.md) (2 shared connections)
- [Chart Vendor Renderer Base](Chart_Vendor_Renderer_Base.md) (2 shared connections)
- [One Source of Truth JS Tests](One_Source_of_Truth_JS_Tests.md) (1 shared connections)
- [CustodyOverridesTheSimulatorsStory](CustodyOverridesTheSimulatorsStory.md) (1 shared connections)
- [Cycle Detection Engine](Cycle_Detection_Engine.md) (1 shared connections)
- [API Server Endpoints](API_Server_Endpoints.md) (1 shared connections)

## Source Files

- `app/engine/contracts.py`
- `app/engine/execution.py`
- `app/engine/phemex_private.py`
- `app/tests/test_position_api.py`

## Audit Trail

- EXTRACTED: 256 (85%)
- INFERRED: 46 (15%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*