# Engine Pipeline Runner

> 7 nodes

## Key Concepts

- **pipeline.py** (4 connections) — `app/engine/pipeline.py`
- **names()** (2 connections) — `app/engine/pipeline.py`
- **run_symbol()** (2 connections) — `app/engine/pipeline.py`
- **_record_gate()** (1 connections) — `app/engine/pipeline.py`
- **The per-symbol engine sequence — declared ONCE, imported by every runner.  Thr** (1 connections) — `app/engine/pipeline.py`
- **Engine names in run order, for logging and for the roster test.      A module** (1 connections) — `app/engine/pipeline.py`
- **Run every per-symbol engine, gates first. THE loop — both runners call it.** (1 connections) — `app/engine/pipeline.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/engine/pipeline.py`

## Audit Trail

- EXTRACTED: 12 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*