# Cooldown Engine

> 17 nodes

## Key Concepts

- **cooldowns.py** (12 connections) — `app/engine/cooldowns.py`
- **record()** (6 connections) — `app/engine/cooldowns.py`
- **key()** (4 connections) — `app/engine/cooldowns.py`
- **run()** (4 connections) — `app/engine/cooldowns.py`
- **horizon_for()** (3 connections) — `app/engine/cooldowns.py`
- **duration_hours()** (3 connections) — `app/engine/cooldowns.py`
- **blocked_at()** (3 connections) — `app/engine/cooldowns.py`
- **blocked()** (3 connections) — `app/engine/cooldowns.py`
- **load()** (2 connections) — `app/engine/cooldowns.py`
- **active_at()** (2 connections) — `app/engine/cooldowns.py`
- **Re-entry control — how long a symbol+direction is locked out after an exit.  N** (1 connections) — `app/engine/cooldowns.py`
- **Emit a cooldown fact for one closed trade. Idempotent by content hash.      `c** (1 connections) — `app/engine/cooldowns.py`
- **Every cooldown fact once, ordered. The caller then evaluates any number of** (1 connections) — `app/engine/cooldowns.py`
- **The cooldown blocking this entry at `as_of`, or None.      Point-in-time by co** (1 connections) — `app/engine/cooldowns.py`
- **Cooldowns in force at `as_of`, keyed by symbol|direction.      Point-in-time b** (1 connections) — `app/engine/cooldowns.py`
- **The cooldown blocking this entry, or None. Returns the FACT so a caller     can** (1 connections) — `app/engine/cooldowns.py`
- **Engine-contract entry point: derive cooldowns from recorded exits.      Delibe** (1 connections) — `app/engine/cooldowns.py`

## Relationships

- [Bias, Trend & Setups](Bias%2C_Trend_%26_Setups.md) (2 shared connections)
- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (1 shared connections)

## Source Files

- `app/engine/cooldowns.py`

## Audit Trail

- EXTRACTED: 49 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*