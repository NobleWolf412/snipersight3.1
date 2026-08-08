# No-Cache Static Serving

> 4 nodes

## Key Concepts

- **_NoCacheStatic** (4 connections) — `app/server.py`
- **StaticFiles** (1 connections)
- **.get_response()** (1 connections) — `app/server.py`
- **Serve UI assets without browser caching.      Rationale (S22b): renaming a DOM** (1 connections) — `app/server.py`

## Relationships

- [API Server Endpoints](API_Server_Endpoints.md) (1 shared connections)

## Source Files

- `app/server.py`

## Audit Trail

- EXTRACTED: 7 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*