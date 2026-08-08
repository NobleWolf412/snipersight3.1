# Fact Query & Scan Endpoints

> 9 nodes

## Key Concepts

- **Response** (4 connections)
- **analyse_symbol()** (4 connections) — `app/server.py`
- **facts()** (3 connections) — `app/server.py`
- **scan_now()** (3 connections) — `app/server.py`
- **apex_action()** (3 connections) — `app/server.py`
- **Generic as_of-cursored fact query — the same contract for every engine.      `** (1 connections) — `app/server.py`
- **Run the engine chain over ONE symbol, on demand.      48 of the symbols in the** (1 connections) — `app/server.py`
- **Run one real scan cycle on demand — the same code path the live loop     runs,** (1 connections) — `app/server.py`
- **ApexShell action verbs. Allow-listed and non-destructive: `audit` re-runs     t** (1 connections) — `app/server.py`

## Relationships

- [API Server Endpoints](API_Server_Endpoints.md) (4 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (1 shared connections)

## Source Files

- `app/server.py`

## Audit Trail

- EXTRACTED: 20 (95%)
- INFERRED: 1 (5%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*