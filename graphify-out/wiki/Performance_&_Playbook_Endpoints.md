# Performance & Playbook Endpoints

> 14 nodes

## Key Concepts

- **playbooks()** (6 connections) — `app/server.py`
- **_baseline_setup_ids()** (5 connections) — `app/server.py`
- **performance()** (4 connections) — `app/server.py`
- **_reversal_rule_words()** (4 connections) — `app/server.py`
- **_entry_rules()** (3 connections) — `app/server.py`
- **_rejection_regime_share()** (3 connections) — `app/server.py`
- **overview()** (3 connections) — `app/server.py`
- **Single source of truth for facts visible in the active paper window.** (1 connections) — `app/server.py`
- **Per-symbol / per-strategy paper performance, PARTITIONED BY WHETHER THE     ACC** (1 connections) — `app/server.py`
- **CONFIRMS / STOP GOES text, read from whichever entry model is loaded.      set** (1 connections) — `app/server.py`
- **How the candidates the scanner turned down split by market condition.      Thi** (1 connections) — `app/server.py`
- **Every strategy: what it hunts, how it works, and its live record.      The rec** (1 connections) — `app/server.py`
- **The REVERSAL gate in words, derived from the engine's own constants.      Rest** (1 connections) — `app/server.py`
- **One call for the cockpit rails: watchlist, setup feed, engine health.** (1 connections) — `app/server.py`

## Relationships

- [API Server Endpoints](API_Server_Endpoints.md) (7 shared connections)
- [Portfolio & Position Endpoints](Portfolio_%26_Position_Endpoints.md) (1 shared connections)
- [Server Narrative Phrasing](Server_Narrative_Phrasing.md) (1 shared connections)

## Source Files

- `app/server.py`

## Audit Trail

- EXTRACTED: 35 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*