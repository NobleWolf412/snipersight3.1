# A/B Calibration Tests

> 52 nodes

## Key Concepts

- **contracts.py** (49 connections) — `app/engine/contracts.py`
- **test_phemex_private.py** (13 connections) — `app/tests/test_phemex_private.py`
- **StrEnum** (10 connections) — `app/engine/contracts.py`
- **achievements.py** (7 connections) — `app/engine/achievements.py`
- **plan()** (7 connections) — `app/tests/test_phemex_private.py`
- **calculate()** (6 connections) — `app/engine/achievements.py`
- **market_context.py** (6 connections) — `app/engine/market_context.py`
- **snapshot()** (4 connections) — `app/engine/market_context.py`
- **test_autotrader.py** (4 connections) — `app/tests/test_autotrader.py`
- **test_broker_factory.py** (4 connections) — `app/tests/test_broker_factory.py`
- **_progress()** (3 connections) — `app/engine/achievements.py`
- **Decimal** (3 connections)
- **MarketContextSnapshot** (3 connections) — `app/engine/contracts.py`
- **AchievementProgress** (3 connections) — `app/engine/contracts.py`
- **ready()** (3 connections) — `app/tests/test_autotrader.py`
- **Enum** (2 connections)
- **OpportunityState** (2 connections) — `app/engine/contracts.py`
- **TopDownState** (2 connections) — `app/engine/contracts.py`
- **EvidenceStatus** (2 connections) — `app/engine/contracts.py`
- **_latest()** (2 connections) — `app/engine/market_context.py`
- **test_ready_candidate_becomes_decimal_isolated_one_way_plan()** (2 connections) — `app/tests/test_autotrader.py`
- **test_no_trade_or_risk_rejection_never_becomes_intent()** (2 connections) — `app/tests/test_autotrader.py`
- **test_testnet_order_uses_real_value_fields_one_way_and_attached_stop_only()** (2 connections) — `app/tests/test_phemex_private.py`
- **test_adapter_refuses_to_round_invalid_tick_or_lot_silently()** (2 connections) — `app/tests/test_phemex_private.py`
- **Discipline-only progression for the Tactical Cockpit.  Progress is derived from** (1 connections) — `app/engine/achievements.py`
- *... and 27 more nodes in this community*

## Relationships

- [Chart Vendor Marker Rendering](Chart_Vendor_Marker_Rendering.md) (17 shared connections)
- [Cycle Detection Engine](Cycle_Detection_Engine.md) (5 shared connections)
- [ProtectedBroker](ProtectedBroker.md) (3 shared connections)
- [Market Data Importer](Market_Data_Importer.md) (3 shared connections)
- [Shared Pipeline Loop Tests](Shared_Pipeline_Loop_Tests.md) (2 shared connections)
- [test_opportunities.py](test_opportunities.py.md) (1 shared connections)
- [Notification Delivery](Notification_Delivery.md) (1 shared connections)
- [One Source of Truth JS Tests](One_Source_of_Truth_JS_Tests.md) (1 shared connections)
- [test_autonomy_contracts.py](test_autonomy_contracts.py.md) (1 shared connections)
- [Volatility Engine](Volatility_Engine.md) (1 shared connections)
- [Chart Vendor Renderer Base](Chart_Vendor_Renderer_Base.md) (1 shared connections)
- [Chart Vendor Series](Chart_Vendor_Series.md) (1 shared connections)

## Source Files

- `app/engine/achievements.py`
- `app/engine/contracts.py`
- `app/engine/market_context.py`
- `app/tests/test_autotrader.py`
- `app/tests/test_broker_factory.py`
- `app/tests/test_phemex_private.py`

## Audit Trail

- EXTRACTED: 167 (98%)
- INFERRED: 4 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*