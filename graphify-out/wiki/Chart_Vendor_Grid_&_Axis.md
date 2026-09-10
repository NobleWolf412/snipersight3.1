# Chart Vendor Grid & Axis

> 19 nodes

## Key Concepts

- **operations_read_model()** (8 connections) — `app/server.py`
- **_next_action()** (6 connections) — `app/server.py`
- **command_read_model()** (6 connections) — `app/server.py`
- **_quality_cause()** (5 connections) — `app/server.py`
- **_quality_headline()** (5 connections) — `app/server.py`
- **_annotate_quality()** (5 connections) — `app/server.py`
- **_citadel_status()** (4 connections) — `app/server.py`
- **_quality_plain()** (4 connections) — `app/server.py`
- **_scanner_status()** (3 connections) — `app/server.py`
- **pipeline_health()** (3 connections) — `app/server.py`
- **Small, read-only recovery status; Citadel credentials never reach UI.** (1 connections) — `app/server.py`
- **Plain words for one finding code; REFERENCE_ demotions wrap their base.      T** (1 connections) — `app/server.py`
- **The dominant finding group, in plain words, with its affected markets.      On** (1 connections) — `app/server.py`
- **One sentence for the whole verdict — what it means, then the counts.** (1 connections) — `app/server.py`
- **Serve-time translation of a verdict; the persisted report is untouched.      A** (1 connections) — `app/server.py`
- **Server-owned operator directive; the browser only routes and formats.** (1 connections) — `app/server.py`
- **Fast first paint: what needs the operator, before the full book loads.** (1 connections) — `app/server.py`
- **Compact command-layer state shared by every cockpit destination.** (1 connections) — `app/server.py`
- **Read-only A-to-Z contract audit used to qualify performance.      Serves the v** (1 connections) — `app/server.py`

## Relationships

- [API Server Endpoints](API_Server_Endpoints.md) (10 shared connections)
- [wire](wire.md) (2 shared connections)
- [yn](yn.md) (1 shared connections)
- [Portfolio & Position Endpoints](Portfolio_%26_Position_Endpoints.md) (1 shared connections)

## Source Files

- `app/server.py`

## Audit Trail

- EXTRACTED: 57 (98%)
- INFERRED: 1 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*