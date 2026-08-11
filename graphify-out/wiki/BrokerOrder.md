# BrokerOrder

> God node · 50 connections · `app/engine/contracts.py`

**Community:** [Chart Vendor Marker Rendering](Chart_Vendor_Marker_Rendering.md)

## Connections by Relation

### calls
- order() `INFERRED`
- broker_order() `INFERRED`
- test_flat_partial_fill_cannot_close_while_entry_remainder_is_active() `INFERRED`
- test_accepted_submission_is_recovered_after_crash_without_resubmit() `INFERRED`
- .confirm_attached_protection() `INFERRED`
- .cancel() `INFERRED`
- .confirm_attached_protection() `INFERRED`
- .order_status() `INFERRED`
- .submit_protective_stop() `INFERRED`

### contains
- contracts.py `EXTRACTED`

### imports
- execution.py `EXTRACTED`
- lifecycle.py `EXTRACTED`
- phemex_private.py `EXTRACTED`

### references
- .submit() `EXTRACTED`
- ._order() `EXTRACTED`
- .replace() `EXTRACTED`
- record_order() `EXTRACTED`
- ensure_emergency() `EXTRACTED`
- .submit_protective_stop() `EXTRACTED`
- .submit_target() `EXTRACTED`
- ensure_stop() `EXTRACTED`
- ensure_target() `EXTRACTED`
- .open_orders() `EXTRACTED`
- .emergency_close() `EXTRACTED`
- .order_status() `EXTRACTED`
- .confirm_attached_protection() `EXTRACTED`
- .submit() `EXTRACTED`
- .cancel() `EXTRACTED`
- .cancel() `EXTRACTED`
- .open_orders() `EXTRACTED`

### uses
- Broker `INFERRED`
- PhemexBroker `INFERRED`
- PhemexError `INFERRED`
- _FakeCancelBroker `INFERRED`
- LifecycleBroker `INFERRED`
- Broker `INFERRED`
- StopAndLeverageValidation `INFERRED`
- AmbiguousSubmission `INFERRED`
- _RefusesPreWire `INFERRED`
- DispatchRejected `INFERRED`
- [CustodyOverridesTheSimulatorsStory](CustodyOverridesTheSimulatorsStory.md) `INFERRED`
- Coordinator `INFERRED`
- AccountWideBroker `INFERRED`
- DuplicateAndOrphanBroker `INFERRED`
- ExpiryCancelsTheVenueOrder `INFERRED`
- PreWireRefusalIsRetryableAndLoud `INFERRED`
- EveryDrillNamesItsEvidence `INFERRED`
- RestartNeedsARestart `INFERRED`
- LifecycleBlocked `INFERRED`
- [ProtectedBroker](ProtectedBroker.md) `INFERRED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*