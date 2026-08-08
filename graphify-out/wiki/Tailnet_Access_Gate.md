# Tailnet Access Gate

> 9 nodes

## Key Concepts

- **_allowed_users()** (4 connections) — `app/server.py`
- **_gate()** (4 connections) — `app/server.py`
- **whoami()** (4 connections) — `app/server.py`
- **_refuse()** (3 connections) — `app/server.py`
- **Request** (1 connections)
- **Who may reach this app from another device on the tailnet.      One address pe** (1 connections) — `app/server.py`
- **Who is allowed in, and what a page they merely visited may make them do.** (1 connections) — `app/server.py`
- **A refusal the operator can act on, in the format the caller can read.      A p** (1 connections) — `app/server.py`
- **How the app sees the caller. Reaching this at all means it let you in.      Ex** (1 connections) — `app/server.py`

## Relationships

- [API Server Endpoints](API_Server_Endpoints.md) (4 shared connections)

## Source Files

- `app/server.py`

## Audit Trail

- EXTRACTED: 20 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*