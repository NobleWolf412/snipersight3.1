# Pipeline Roster Tests

> 12 nodes

## Key Concepts

- **test_pipeline_roster.py** (6 connections) — `app/tests/test_pipeline_roster.py`
- **test_all_runners_share_one_roster()** (2 connections) — `app/tests/test_pipeline_roster.py`
- **test_cooldowns_is_scheduled()** (2 connections) — `app/tests/test_pipeline_roster.py`
- **test_every_engine_risk_consumes_is_scheduled()** (2 connections) — `app/tests/test_pipeline_roster.py`
- **test_names_disambiguate_repeats()** (2 connections) — `app/tests/test_pipeline_roster.py`
- **test_execsim_runs_after_setups_and_after_scalein()** (2 connections) — `app/tests/test_pipeline_roster.py`
- **The engine roster is one list, and everything `risk.py` consumes is on it.  Thre** (1 connections) — `app/tests/test_pipeline_roster.py`
- **live, ingest and backfill must walk the identical sequence.      Not "the same s** (1 connections) — `app/tests/test_pipeline_roster.py`
- **The specific regression. `risk.py` imports and consumes cooldowns.** (1 connections) — `app/tests/test_pipeline_roster.py`
- **Generalised: if `risk.py` reads an engine's facts, that engine runs.      A vers** (1 connections) — `app/tests/test_pipeline_roster.py`
- **`execsim` runs twice; the labels must say which pass.** (1 connections) — `app/tests/test_pipeline_roster.py`
- **Order is load-bearing: adds opened by scalein still need filling, and     cooldo** (1 connections) — `app/tests/test_pipeline_roster.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_pipeline_roster.py`

## Audit Trail

- EXTRACTED: 22 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*