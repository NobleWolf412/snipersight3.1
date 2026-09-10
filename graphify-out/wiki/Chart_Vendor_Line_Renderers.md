# Chart Vendor Line Renderers

> 17 nodes

## Key Concepts

- **regimefresh.py** (9 connections) — `app/engine/regimefresh.py`
- **grade()** (6 connections) — `app/engine/regimefresh.py`
- **_regime_series()** (5 connections) — `app/engine/regimefresh.py`
- **annotate()** (5 connections) — `app/engine/regimefresh.py`
- **verify()** (5 connections) — `app/engine/regimefresh.py`
- **label_asof()** (4 connections) — `app/engine/regimefresh.py`
- **trigger_at()** (3 connections) — `app/engine/regimefresh.py`
- **factor_extractors()** (3 connections) — `app/engine/regimefresh.py`
- **main()** (2 connections) — `app/engine/regimefresh.py`
- **Regime freshness — how stale was the label this trade was gated on? READ-ONLY.** (1 connections) — `app/engine/regimefresh.py`
- **The market event that defined this label, or None when unrecorded.      regime** (1 connections) — `app/engine/regimefresh.py`
- **(confirmed_at, regime, trigger_at) for one market, in confirmation order.** (1 connections) — `app/engine/regimefresh.py`
- **The governing label at `ts`, and whether a newer one had already landed.** (1 connections) — `app/engine/regimefresh.py`
- **Stamp regime-freshness fields onto candidate payloads, in place.      Mutates** (1 connections) — `app/engine/regimefresh.py`
- **Prove the reconstruction against the engine's own recorded regime.      The ga** (1 connections) — `app/engine/regimefresh.py`
- **0/1 flags for outcome_split. Absent when unannotated, so MISSING stays     hone** (1 connections) — `app/engine/regimefresh.py`
- **The whole audition: load, annotate, split, and say what held.** (1 connections) — `app/engine/regimefresh.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/engine/regimefresh.py`

## Audit Trail

- EXTRACTED: 48 (96%)
- INFERRED: 2 (4%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*