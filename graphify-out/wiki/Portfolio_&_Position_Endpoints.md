# Portfolio & Position Endpoints

> 17 nodes

## Key Concepts

- **portfolio()** (8 connections) — `app/server.py`
- **status()** (4 connections) — `app/server.py`
- **credentials_store()** (4 connections) — `app/server.py`
- **close_position()** (4 connections) — `app/server.py`
- **adopt_position()** (4 connections) — `app/server.py`
- **manual_open()** (4 connections) — `app/server.py`
- **live_gate()** (3 connections) — `app/server.py`
- **credentials_status()** (3 connections) — `app/server.py`
- **copilot_chat()** (3 connections) — `app/server.py`
- **Paper account state from risk-authority facts (§9/§13 dashboard).** (1 connections) — `app/server.py`
- **The four criteria that stand between the paper book and real money.      Read-** (1 connections) — `app/server.py`
- **What credentials EXIST — never their values. There is deliberately no     route** (1 connections) — `app/server.py`
- **Encrypt and store one credential field.      The value is never logged, never** (1 connections) — `app/server.py`
- **Operator closes an ENGINE position early, at the last closed bar.      Records** (1 connections) — `app/server.py`
- **Operator takes custody of an engine position with their own levels.      The e** (1 connections) — `app/server.py`
- **Live state of the operator's open trades on one chart.      Resolves first, th** (1 connections) — `app/server.py`
- **One copilot turn. Observer only: returns prose, writes no facts.      Runs on** (1 connections) — `app/server.py`

## Relationships

- [API Server Endpoints](API_Server_Endpoints.md) (9 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (3 shared connections)
- [Performance & Playbook Endpoints](Performance_%26_Playbook_Endpoints.md) (1 shared connections)

## Source Files

- `app/server.py`

## Audit Trail

- EXTRACTED: 42 (93%)
- INFERRED: 3 (7%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*