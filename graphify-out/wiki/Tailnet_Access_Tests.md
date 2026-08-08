# Tailnet Access Tests

> 23 nodes

## Key Concepts

- **TailnetIdentityTests** (16 connections) — `app/tests/test_phone_front_door.py`
- **._proxied()** (11 connections) — `app/tests/test_phone_front_door.py`
- **.test_a_proxied_request_with_no_identity_is_refused()** (3 connections) — `app/tests/test_phone_front_door.py`
- **.test_the_gate_covers_the_page_not_only_the_api()** (3 connections) — `app/tests/test_phone_front_door.py`
- **.test_revoking_access_needs_no_restart()** (3 connections) — `app/tests/test_phone_front_door.py`
- **.test_whoami_reports_which_path_the_caller_came_in_on()** (3 connections) — `app/tests/test_phone_front_door.py`
- **.test_this_machine_is_not_gated()** (2 connections) — `app/tests/test_phone_front_door.py`
- **.test_a_permitted_tailnet_user_is_let_in()** (2 connections) — `app/tests/test_phone_front_door.py`
- **.test_the_match_ignores_case()** (2 connections) — `app/tests/test_phone_front_door.py`
- **.test_an_unknown_tailnet_user_is_refused()** (2 connections) — `app/tests/test_phone_front_door.py`
- **.test_an_empty_allowlist_refuses_every_remote_device()** (2 connections) — `app/tests/test_phone_front_door.py`
- **.test_an_empty_allowlist_still_leaves_this_machine_working()** (2 connections) — `app/tests/test_phone_front_door.py`
- **.test_a_refusal_to_the_api_stays_json()** (2 connections) — `app/tests/test_phone_front_door.py`
- **.setUp()** (1 connections) — `app/tests/test_phone_front_door.py`
- **.tearDown()** (1 connections) — `app/tests/test_phone_front_door.py`
- **The login. There is no password, and that is the stronger choice.      `tailsc** (1 connections) — `app/tests/test_phone_front_door.py`
- **What `tailscale serve` puts on a request it forwards.** (1 connections) — `app/tests/test_phone_front_door.py`
- **No proxy headers means nothing forwarded it, so it came from here.         The** (1 connections) — `app/tests/test_phone_front_door.py`
- **This is what a Tailscale *Funnel* request looks like — the public         inter** (1 connections) — `app/tests/test_phone_front_door.py`
- **The failure mode has to be 'the phone stops', never 'the desk         stops' —** (1 connections) — `app/tests/test_phone_front_door.py`
- **Letting an unlisted device load the shell and then 403 every panel         rend** (1 connections) — `app/tests/test_phone_front_door.py`
- **Read per request, deliberately: access should end when the operator         sav** (1 connections) — `app/tests/test_phone_front_door.py`
- **A gate whose output nobody can see is a gate nobody notices has         stopped** (1 connections) — `app/tests/test_phone_front_door.py`

## Relationships

- [Baseline Reset Guard Tests](Baseline_Reset_Guard_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_phone_front_door.py`

## Audit Trail

- EXTRACTED: 63 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*