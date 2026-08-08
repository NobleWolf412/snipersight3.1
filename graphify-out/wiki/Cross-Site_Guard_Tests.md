# Cross-Site Guard Tests

> 14 nodes

## Key Concepts

- **CrossSiteGuardTests** (10 connections) — `app/tests/test_phone_front_door.py`
- **.test_same_site_is_refused_too()** (2 connections) — `app/tests/test_phone_front_door.py`
- **.test_non_browser_callers_are_untouched()** (2 connections) — `app/tests/test_phone_front_door.py`
- **.test_the_guard_does_not_cover_the_shell_or_its_assets()** (2 connections) — `app/tests/test_phone_front_door.py`
- **.test_every_writing_endpoint_sits_behind_the_guard()** (2 connections) — `app/tests/test_phone_front_door.py`
- **.setUp()** (1 connections) — `app/tests/test_phone_front_door.py`
- **.test_a_cross_site_request_to_the_api_is_refused()** (1 connections) — `app/tests/test_phone_front_door.py`
- **.test_the_app_itself_still_reaches_its_own_api()** (1 connections) — `app/tests/test_phone_front_door.py`
- **.test_a_typed_address_or_bookmark_still_works()** (1 connections) — `app/tests/test_phone_front_door.py`
- **`Sec-Fetch-Site` is set by the browser and page script cannot forge it.** (1 connections) — `app/tests/test_phone_front_door.py`
- **A sibling host on the tailnet is not this app.** (1 connections) — `app/tests/test_phone_front_door.py`
- **curl, the watchdog's health poll and this suite send no such header,         an** (1 connections) — `app/tests/test_phone_front_door.py`
- **Only /api/* is guarded. Following a link to the cockpit from         anywhere m** (1 connections) — `app/tests/test_phone_front_door.py`
- **The guard is path-prefix based, so this is really a check that no         write** (1 connections) — `app/tests/test_phone_front_door.py`

## Relationships

- [Baseline Reset Guard Tests](Baseline_Reset_Guard_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_phone_front_door.py`

## Audit Trail

- EXTRACTED: 27 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*