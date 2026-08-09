# Notification Tests

> 55 nodes

## Key Concepts

- **_Log** (10 connections) — `app/tests/test_notifications.py`
- **test_notifications.py** (9 connections) — `app/tests/test_notifications.py`
- **TestAnnounceRecency** (9 connections) — `app/tests/test_notifications.py`
- **TestOnlyTradedEnginesAnnounce** (9 connections) — `app/tests/test_notifications.py`
- **TestDriftStaleness** (9 connections) — `app/tests/test_notifications.py`
- **TestPriceRoutingByVenue** (8 connections) — `app/tests/test_notifications.py`
- **._fired()** (7 connections) — `app/tests/test_notifications.py`
- **TempStore** (6 connections) — `app/tests/test_notifications.py`
- **._setup_fact()** (6 connections) — `app/tests/test_notifications.py`
- **.test_suppression_is_audible()** (5 connections) — `app/tests/test_notifications.py`
- **._candle()** (5 connections) — `app/tests/test_notifications.py`
- **.test_blindness_is_reported_not_swallowed()** (5 connections) — `app/tests/test_notifications.py`
- **.saw()** (4 connections) — `app/tests/test_notifications.py`
- **.test_lateness_is_measured_in_the_setups_own_timeframe()** (4 connections) — `app/tests/test_notifications.py`
- **._fact()** (4 connections) — `app/tests/test_notifications.py`
- **.test_the_traded_playbooks_still_announce()** (4 connections) — `app/tests/test_notifications.py`
- **.test_stale_reference_is_muted_and_says_why()** (4 connections) — `app/tests/test_notifications.py`
- **TestPhemexLastPrices** (4 connections) — `app/tests/test_notifications.py`
- **.test_backfilled_history_is_not_announced()** (3 connections) — `app/tests/test_notifications.py`
- **.test_pre_baseline_setup_is_not_announced()** (3 connections) — `app/tests/test_notifications.py`
- **.test_current_setup_is_announced()** (3 connections) — `app/tests/test_notifications.py`
- **.test_the_not_enabled_playbooks_never_announce()** (3 connections) — `app/tests/test_notifications.py`
- **.test_mute_is_logged_once_per_bucket_not_once_per_poll()** (3 connections) — `app/tests/test_notifications.py`
- **.test_fresh_reference_still_alerts()** (3 connections) — `app/tests/test_notifications.py`
- **._fired()** (2 connections) — `app/tests/test_notifications.py`
- *... and 30 more nodes in this community*

## Relationships

- [Live Scanner Loop](Live_Scanner_Loop.md) (1 shared connections)

## Source Files

- `app/tests/test_notifications.py`

## Audit Trail

- EXTRACTED: 165 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*