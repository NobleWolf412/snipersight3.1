# Setup Lifecycle Telemetry

> 12 nodes

## Key Concepts

- **telemetry.py** (8 connections) — `app/engine/telemetry.py`
- **_decimal()** (5 connections) — `app/engine/telemetry.py`
- **loss_autopsy()** (5 connections) — `app/engine/telemetry.py`
- **_median()** (4 connections) — `app/engine/telemetry.py`
- **classify_failure()** (3 connections) — `app/engine/telemetry.py`
- **build_record()** (2 connections) — `app/engine/telemetry.py`
- **summarize_diagnostics()** (2 connections) — `app/engine/telemetry.py`
- **Observational setup lifecycle telemetry.  This module never creates signals or** (1 connections) — `app/engine/telemetry.py`
- **Return one mutually-exclusive lifecycle state and diagnostic owner.** (1 connections) — `app/engine/telemetry.py`
- **Parse recorded numeric text without letting malformed evidence lie.** (1 connections) — `app/engine/telemetry.py`
- **Locate the weak lifecycle stage in the current funded paper book.      This is d** (1 connections) — `app/engine/telemetry.py`
- **Aggregate diagnostics without conflating trading outcomes and defects.** (1 connections) — `app/engine/telemetry.py`

## Relationships

- [Kraken Adapter](Kraken_Adapter.md) (4 shared connections)

## Source Files

- `app/engine/telemetry.py`

## Audit Trail

- EXTRACTED: 31 (91%)
- INFERRED: 3 (9%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*