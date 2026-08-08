# Credential Vault

> 16 nodes

## Key Concepts

- **credentials.py** (12 connections) — `app/engine/credentials.py`
- **store_secret()** (7 connections) — `app/engine/credentials.py`
- **_load()** (5 connections) — `app/engine/credentials.py`
- **_Blob** (4 connections) — `app/engine/credentials.py`
- **_out_bytes()** (4 connections) — `app/engine/credentials.py`
- **_protect()** (4 connections) — `app/engine/credentials.py`
- **_unprotect()** (4 connections) — `app/engine/credentials.py`
- **read_secret()** (4 connections) — `app/engine/credentials.py`
- **_save()** (3 connections) — `app/engine/credentials.py`
- **clear()** (3 connections) — `app/engine/credentials.py`
- **status()** (3 connections) — `app/engine/credentials.py`
- **available()** (2 connections) — `app/engine/credentials.py`
- **API credential storage — Windows DPAPI, write-only from the app's view.  Desig** (1 connections) — `app/engine/credentials.py`
- **Encrypt and persist one credential field. The value is never logged.** (1 connections) — `app/engine/credentials.py`
- **What EXISTS, never what it is. This is the only shape the API may return.** (1 connections) — `app/engine/credentials.py`
- **Decrypt for in-process use only.      Deliberately NOT reachable from any HTTP** (1 connections) — `app/engine/credentials.py`

## Relationships

- [Venue Policy & Contract](Venue_Policy_%26_Contract.md) (1 shared connections)

## Source Files

- `app/engine/credentials.py`

## Audit Trail

- EXTRACTED: 58 (98%)
- INFERRED: 1 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*