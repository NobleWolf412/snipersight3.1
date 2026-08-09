# Credential Vault Tests

> 16 nodes

## Key Concepts

- **VaultTest** (10 connections) — `app/tests/test_credentials.py`
- **test_credentials.py** (3 connections) — `app/tests/test_credentials.py`
- **.test_unknown_venue_or_field_refused()** (2 connections) — `app/tests/test_credentials.py`
- **NoReadRouteTest** (2 connections) — `app/tests/test_credentials.py`
- **.test_no_http_route_calls_the_secret_reader()** (2 connections) — `app/tests/test_credentials.py`
- **.setUp()** (1 connections) — `app/tests/test_credentials.py`
- **.tearDown()** (1 connections) — `app/tests/test_credentials.py`
- **.test_plaintext_never_reaches_disk()** (1 connections) — `app/tests/test_credentials.py`
- **.test_roundtrip_in_process_only()** (1 connections) — `app/tests/test_credentials.py`
- **.test_status_reports_existence_not_values()** (1 connections) — `app/tests/test_credentials.py`
- **.test_clear_removes_the_secret()** (1 connections) — `app/tests/test_credentials.py`
- **.test_testnet_and_mainnet_credentials_are_isolated()** (1 connections) — `app/tests/test_credentials.py`
- **.test_empty_value_refused()** (1 connections) — `app/tests/test_credentials.py`
- **Credential vault: encrypted at rest, and unreadable through the API.  The secu** (1 connections) — `app/tests/test_credentials.py`
- **An open-ended store invites secrets nobody audits.** (1 connections) — `app/tests/test_credentials.py`
- **`read_secret` must not be INVOKED anywhere the web layer can reach.          C** (1 connections) — `app/tests/test_credentials.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_credentials.py`

## Audit Trail

- EXTRACTED: 30 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*