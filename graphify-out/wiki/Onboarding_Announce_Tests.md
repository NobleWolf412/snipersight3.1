# Onboarding Announce Tests

> 13 nodes

## Key Concepts

- **AnnounceOnce** (9 connections) — `app/tests/test_onboard_announce.py`
- **._refresh_n()** (6 connections) — `app/tests/test_onboard_announce.py`
- **test_onboard_announce.py** (4 connections) — `app/tests/test_onboard_announce.py`
- **.test_it_is_still_onboarded_every_time()** (3 connections) — `app/tests/test_onboard_announce.py`
- **.test_the_scanner_never_spawns_a_process_to_announce()** (3 connections) — `app/tests/test_onboard_announce.py`
- **.test_a_permanently_warming_symbol_is_announced_once()** (2 connections) — `app/tests/test_onboard_announce.py`
- **.test_a_genuinely_new_symbol_is_announced()** (2 connections) — `app/tests/test_onboard_announce.py`
- **.test_an_unavailable_rank_source_announces_nothing()** (2 connections) — `app/tests/test_onboard_announce.py`
- **.setUp()** (1 connections) — `app/tests/test_onboard_announce.py`
- **.tearDown()** (1 connections) — `app/tests/test_onboard_announce.py`
- **A symbol is announced as new ONCE, not once per refresh.  `universe.refresh()` r** (1 connections) — `app/tests/test_onboard_announce.py`
- **Suppressing the ANNOUNCEMENT must not suppress the work — the symbol         sti** (1 connections) — `app/tests/test_onboard_announce.py`
- **The measured cause of 191 scanner deaths: each toast spawned a         PowerShel** (1 connections) — `app/tests/test_onboard_announce.py`

## Relationships

- [Live Scanner Loop](Live_Scanner_Loop.md) (1 shared connections)
- [Notification Delivery](Notification_Delivery.md) (1 shared connections)

## Source Files

- `app/tests/test_onboard_announce.py`

## Audit Trail

- EXTRACTED: 36 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*