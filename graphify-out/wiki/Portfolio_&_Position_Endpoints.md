# Portfolio & Position Endpoints

> 26 nodes

## Key Concepts

- **portfolio()** (14 connections) — `app/server.py`
- **status()** (7 connections) — `app/server.py`
- **_performance_dimensions()** (4 connections) — `app/server.py`
- **manual_open()** (4 connections) — `app/server.py`
- **copilot_chat()** (4 connections) — `app/server.py`
- **_journal_performance_summary()** (3 connections) — `app/server.py`
- **_envelope_config()** (3 connections) — `app/server.py`
- **credentials_status()** (3 connections) — `app/server.py`
- **credentials_store()** (3 connections) — `app/server.py`
- **stocks_status()** (3 connections) — `app/server.py`
- **close_position()** (3 connections) — `app/server.py`
- **adopt_position()** (3 connections) — `app/server.py`
- **macro_calendar_snapshot()** (3 connections) — `app/server.py`
- **One server-owned scoreboard for the current funded forward book.** (1 connections) — `app/server.py`
- **Comparable funded-book cuts; unknown metadata stays explicitly unknown.** (1 connections) — `app/server.py`
- **The envelope of the book being DISPLAYED — the paper book — plus the     dispat** (1 connections) — `app/server.py`
- **Paper account state from risk-authority facts (§9/§13 dashboard).** (1 connections) — `app/server.py`
- **Funded forward-book results by operator comparison dimension.** (1 connections) — `app/server.py`
- **What credentials EXIST — never their values. There is deliberately no     route** (1 connections) — `app/server.py`
- **Encrypt and store one credential field.      The value is never logged, never** (1 connections) — `app/server.py`
- **Stock-workspace readiness without decrypting or probing credentials.** (1 connections) — `app/server.py`
- **Operator closes an ENGINE position early, at the last closed bar.      Records** (1 connections) — `app/server.py`
- **Operator takes custody of an engine position with their own levels.      The e** (1 connections) — `app/server.py`
- **Live state of the operator's open trades on one chart.      Resolves first, th** (1 connections) — `app/server.py`
- **Cached official calendar reads only; no store or trading writes.** (1 connections) — `app/server.py`
- *... and 1 more nodes in this community*

## Relationships

- [API Server Endpoints](API_Server_Endpoints.md) (13 shared connections)
- [wire](wire.md) (3 shared connections)
- [Performance & Playbook Endpoints](Performance_%26_Playbook_Endpoints.md) (1 shared connections)
- [Chart Vendor Grid & Axis](Chart_Vendor_Grid_%26_Axis.md) (1 shared connections)

## Source Files

- `app/server.py`

## Audit Trail

- EXTRACTED: 70 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*