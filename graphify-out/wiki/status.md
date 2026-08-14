# status

> 9 nodes

## Key Concepts

- **status()** (6 connections) — `app/server.py`
- **manual_open()** (4 connections) — `app/server.py`
- **credentials_status()** (3 connections) — `app/server.py`
- **credentials_store()** (3 connections) — `app/server.py`
- **stocks_status()** (3 connections) — `app/server.py`
- **What credentials EXIST — never their values. There is deliberately no     route** (1 connections) — `app/server.py`
- **Encrypt and store one credential field.      The value is never logged, never** (1 connections) — `app/server.py`
- **Stock-workspace readiness without decrypting or probing credentials.** (1 connections) — `app/server.py`
- **Live state of the operator's open trades on one chart.      Resolves first, th** (1 connections) — `app/server.py`

## Relationships

- [API Server Endpoints](API_Server_Endpoints.md) (5 shared connections)
- [Portfolio & Position Endpoints](Portfolio_%26_Position_Endpoints.md) (2 shared connections)

## Source Files

- `app/server.py`

## Audit Trail

- EXTRACTED: 23 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*