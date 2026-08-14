# Chart Vendor Renderer Base

> 29 nodes

## Key Concepts

- **LifecycleBroker** (21 connections) — `app/tests/test_testnet_lifecycle.py`
- **test_testnet_lifecycle.py** (19 connections) — `app/tests/test_testnet_lifecycle.py`
- **prepared()** (11 connections) — `app/tests/test_testnet_lifecycle.py`
- **broker_order()** (10 connections) — `app/tests/test_testnet_lifecycle.py`
- **plan()** (6 connections) — `app/tests/test_testnet_lifecycle.py`
- **.__init__()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **.confirm_attached_protection()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **.submit_protective_stop()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **.submit_target()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **.replace()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **.order_status()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **.cancel()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **.executions()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **test_fill_handoff_records_standalone_stop_and_target_identities()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **test_known_exit_receipt_cleanup_and_two_flat_polls_earn_one_lifecycle()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **test_flat_without_known_exit_receipt_never_qualifies()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **test_legacy_flat_only_event_does_not_block_later_qualification()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **test_manual_override_exit_closes_no_autonomous_evidence()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **test_ambiguous_target_submit_recovers_by_client_id_without_resubmit()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **test_mixed_exit_roles_halt_and_never_qualify()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **test_matching_client_with_wrong_broker_order_id_never_qualifies()** (2 connections) — `app/tests/test_testnet_lifecycle.py`
- **.positions()** (1 connections) — `app/tests/test_testnet_lifecycle.py`
- **.open_orders()** (1 connections) — `app/tests/test_testnet_lifecycle.py`
- **test_duplicate_or_incomplete_events_do_not_inflate_promotion()** (1 connections) — `app/tests/test_testnet_lifecycle.py`
- **test_partial_fill_resizes_one_target_identity_in_place()** (1 connections) — `app/tests/test_testnet_lifecycle.py`
- *... and 4 more nodes in this community*

## Relationships

- [Chart Vendor Marker Rendering](Chart_Vendor_Marker_Rendering.md) (9 shared connections)
- [A/B Calibration Tests](A-B_Calibration_Tests.md) (3 shared connections)
- [ProtectedBroker](ProtectedBroker.md) (2 shared connections)
- [Shared Pipeline Loop Tests](Shared_Pipeline_Loop_Tests.md) (2 shared connections)
- [Cycle Detection Engine](Cycle_Detection_Engine.md) (1 shared connections)

## Source Files

- `app/tests/test_testnet_lifecycle.py`

## Audit Trail

- EXTRACTED: 91 (85%)
- INFERRED: 16 (15%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*