# Data Quality Engine

> 25 nodes

## Key Concepts

- **quality.py** (17 connections) — `app/engine/quality.py`
- **audit()** (8 connections) — `app/engine/quality.py`
- **audit_market_inputs()** (7 connections) — `app/engine/quality.py`
- **cached_audit()** (6 connections) — `app/engine/quality.py`
- **_rung_for()** (4 connections) — `app/engine/quality.py`
- **_issue()** (4 connections) — `app/engine/quality.py`
- **_current_versions()** (3 connections) — `app/engine/quality.py`
- **_known_gap_buckets()** (3 connections) — `app/engine/quality.py`
- **DataQualityError** (3 connections) — `app/engine/quality.py`
- **_live_symbols()** (3 connections) — `app/engine/quality.py`
- **_db_key()** (3 connections) — `app/engine/quality.py`
- **_default_db_key()** (3 connections) — `app/engine/quality.py`
- **assert_market_ready()** (3 connections) — `app/engine/quality.py`
- **_stage_status()** (2 connections) — `app/engine/quality.py`
- **_stage_rung()** (2 connections) — `app/engine/quality.py`
- **_slot()** (2 connections) — `app/engine/quality.py`
- **last_persisted()** (2 connections) — `app/engine/quality.py`
- **Fail-closed A-to-Z pipeline quality and reconciliation audits.  The checks in** (1 connections) — `app/engine/quality.py`
- **Active engine chain. Generation-specific checks (SETUP/RISK/EXECUTION)     eval** (1 connections) — `app/engine/quality.py`
- **Gaps the importer acknowledged at import time (gap-honesty rule: gaps are     l** (1 connections) — `app/engine/quality.py`
- **Symbols currently in the scan universe.      Computed once per audit and passe** (1 connections) — `app/engine/quality.py`
- **Identify the store behind a connection, so a verdict cannot cross stores.** (1 connections) — `app/engine/quality.py`
- **Path of the production store, resolved the same way store.connect does.** (1 connections) — `app/engine/quality.py`
- **The most recent audit THE SCANNER RECORDED, or None before the first.      ONE** (1 connections) — `app/engine/quality.py`
- **The one verdict every surface reads, for THIS store.      A full audit was mea** (1 connections) — `app/engine/quality.py`

## Relationships

- [.Mt](Mt.md) (1 shared connections)

## Source Files

- `app/engine/quality.py`

## Audit Trail

- EXTRACTED: 83 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*