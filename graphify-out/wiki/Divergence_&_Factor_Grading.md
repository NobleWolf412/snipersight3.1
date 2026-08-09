# Divergence & Factor Grading

> 34 nodes

## Key Concepts

- **divstats.py** (12 connections) — `app/engine/divstats.py`
- **factorgrade.py** (12 connections) — `app/engine/factorgrade.py`
- **annotate()** (6 connections) — `app/engine/divstats.py`
- **grade()** (6 connections) — `app/engine/divstats.py`
- **annotate()** (6 connections) — `app/engine/factorgrade.py`
- **latest_before()** (5 connections) — `app/engine/divstats.py`
- **grade()** (5 connections) — `app/engine/factorgrade.py`
- **_series()** (4 connections) — `app/engine/factorgrade.py`
- **_divergences()** (3 connections) — `app/engine/divstats.py`
- **stance()** (3 connections) — `app/engine/divstats.py`
- **factor_extractors()** (3 connections) — `app/engine/divstats.py`
- **_clear()** (3 connections) — `app/engine/divstats.py`
- **main()** (3 connections) — `app/engine/divstats.py`
- **_fvg_series()** (3 connections) — `app/engine/factorgrade.py`
- **main()** (3 connections) — `app/engine/factorgrade.py`
- **_fmt()** (2 connections) — `app/engine/divstats.py`
- **_version()** (2 connections) — `app/engine/factorgrade.py`
- **_clear()** (2 connections) — `app/engine/factorgrade.py`
- **calibrated_grade()** (2 connections) — `app/engine/factorgrade.py`
- **_fmt()** (2 connections) — `app/engine/factorgrade.py`
- **Did momentum divergence predict anything? READ-ONLY audition.  `momentum.py` h** (1 connections) — `app/engine/divstats.py`
- **(confirmed_at, direction) for one symbol/timeframe, in confirmation     order.** (1 connections) — `app/engine/divstats.py`
- **The most recent divergence direction known at `ts` and no older than     `max_a** (1 connections) — `app/engine/divstats.py`
- **AGREES / OPPOSES, or None when there is nothing to compare.** (1 connections) — `app/engine/divstats.py`
- **Stamp `div_stance` onto candidates whose window holds a divergence.      Mutat** (1 connections) — `app/engine/divstats.py`
- *... and 9 more nodes in this community*

## Relationships

- [Indicator Engines](Indicator_Engines.md) (1 shared connections)

## Source Files

- `app/engine/divstats.py`
- `app/engine/factorgrade.py`

## Audit Trail

- EXTRACTED: 99 (98%)
- INFERRED: 2 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*