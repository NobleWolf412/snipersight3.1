# Shared Pipeline Loop Tests

> 36 nodes

## Key Concepts

- **Broker** (34 connections) — `app/tests/test_position_safety.py`
- **Fill** (26 connections) — `app/engine/contracts.py`
- **test_position_safety.py** (22 connections) — `app/tests/test_position_safety.py`
- **memory()** (16 connections) — `app/tests/test_position_safety.py`
- **plan()** (16 connections) — `app/tests/test_position_safety.py`
- **AccountWideBroker** (13 connections) — `app/tests/test_position_safety.py`
- **DuplicateAndOrphanBroker** (13 connections) — `app/tests/test_position_safety.py`
- **order()** (11 connections) — `app/tests/test_position_safety.py`
- **test_lingering_stop_from_closed_position_blocks_reconciliation()** (6 connections) — `app/tests/test_position_safety.py`
- **test_flat_partial_fill_cannot_close_while_entry_remainder_is_active()** (6 connections) — `app/tests/test_position_safety.py`
- **test_first_and_partial_fills_resize_confirmed_protection()** (5 connections) — `app/tests/test_position_safety.py`
- **test_failed_protection_emergency_closes_and_halts_new_entries()** (5 connections) — `app/tests/test_position_safety.py`
- **test_manual_override_keeps_stop_and_requires_explicit_return()** (5 connections) — `app/tests/test_position_safety.py`
- **test_emergency_close_failure_halts_and_records_unknown_exposure()** (5 connections) — `app/tests/test_position_safety.py`
- **test_reconciliation_rejects_equal_size_opposite_direction()** (5 connections) — `app/tests/test_position_safety.py`
- **test_own_protective_order_is_known_and_partial_fill_amends_it()** (5 connections) — `app/tests/test_position_safety.py`
- **test_managed_read_model_exposes_server_custody_fields()** (5 connections) — `app/tests/test_position_safety.py`
- **test_unprotected_exposure_remains_in_private_custody_and_reconciliation()** (5 connections) — `app/tests/test_position_safety.py`
- **test_two_distinct_venue_flat_snapshots_close_custody_without_lifecycle_credit()** (5 connections) — `app/tests/test_position_safety.py`
- **test_startup_reconciliation_is_required_and_unknown_state_blocks()** (3 connections) — `app/tests/test_position_safety.py`
- **test_account_wide_reconciliation_finds_untracked_foreign_order()** (3 connections) — `app/tests/test_position_safety.py`
- **test_reconciliation_emits_deduplicated_promotion_failures()** (3 connections) — `app/tests/test_position_safety.py`
- **test_stale_reconciliation_does_not_authorize_dispatch()** (3 connections) — `app/tests/test_position_safety.py`
- **.open_orders()** (2 connections) — `app/tests/test_position_safety.py`
- **.confirm_attached_protection()** (2 connections) — `app/tests/test_position_safety.py`
- *... and 11 more nodes in this community*

## Relationships

- [Chart Vendor Line Renderers](Chart_Vendor_Line_Renderers.md) (20 shared connections)
- [A/B Calibration Tests](A-B_Calibration_Tests.md) (6 shared connections)
- [Chart Vendor Marker Rendering](Chart_Vendor_Marker_Rendering.md) (5 shared connections)
- [Market Data Importer](Market_Data_Importer.md) (4 shared connections)
- [Cycle Detection Engine](Cycle_Detection_Engine.md) (3 shared connections)
- [Chart Vendor Renderer Base](Chart_Vendor_Renderer_Base.md) (2 shared connections)
- [One Source of Truth JS Tests](One_Source_of_Truth_JS_Tests.md) (1 shared connections)

## Source Files

- `app/engine/contracts.py`
- `app/tests/test_position_safety.py`

## Audit Trail

- EXTRACTED: 178 (74%)
- INFERRED: 63 (26%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*