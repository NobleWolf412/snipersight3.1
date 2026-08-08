# Baseline Reset Guard Tests

> 11 nodes

## Key Concepts

- **test_phone_front_door.py** (8 connections) — `app/tests/test_phone_front_door.py`
- **BaselineResetTests** (5 connections) — `app/tests/test_phone_front_door.py`
- **.test_a_form_post_cannot_reach_the_handler()** (2 connections) — `app/tests/test_phone_front_door.py`
- **OnePollForOnePayloadTests** (2 connections) — `app/tests/test_phone_front_door.py`
- **.test_setup_telemetry_is_asked_for_one_way_only()** (2 connections) — `app/tests/test_phone_front_door.py`
- **.setUp()** (1 connections) — `app/tests/test_phone_front_door.py`
- **.test_a_json_body_without_confirmation_is_refused()** (1 connections) — `app/tests/test_phone_front_door.py`
- **What has to stay true for the cockpit to be safe on a phone.  The app became r** (1 connections) — `app/tests/test_phone_front_door.py`
- **The one endpoint whose effect cannot be undone from the app.      Nothing here** (1 connections) — `app/tests/test_phone_front_door.py`
- **The second lock, behind the guard: a plain HTML form cannot produce         a b** (1 connections) — `app/tests/test_phone_front_door.py`
- **shell.js asked limit=200 and funnel.js limit=500. There are far         fewer t** (1 connections) — `app/tests/test_phone_front_door.py`

## Relationships

- [API Server Endpoints](API_Server_Endpoints.md) (1 shared connections)
- [Cross-Site Guard Tests](Cross-Site_Guard_Tests.md) (1 shared connections)
- [Facts Window Tests](Facts_Window_Tests.md) (1 shared connections)
- [PWA Installability Tests](PWA_Installability_Tests.md) (1 shared connections)
- [Tailnet Access Tests](Tailnet_Access_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_phone_front_door.py`

## Audit Trail

- EXTRACTED: 25 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*