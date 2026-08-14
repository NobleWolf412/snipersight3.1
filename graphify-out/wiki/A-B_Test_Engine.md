# A/B Test Engine

> 37 nodes

## Key Concepts

- **abtest.py** (19 connections) — `app/engine/abtest.py`
- **run_variant()** (9 connections) — `app/engine/abtest.py`
- **all_tracked_symbols()** (9 connections) — `app/engine/universe.py`
- **strategygrade.py** (8 connections) — `app/engine/strategygrade.py`
- **report()** (7 connections) — `app/engine/abtest.py`
- **_simulate()** (6 connections) — `app/engine/abtest.py`
- **by_strategy()** (6 connections) — `app/engine/abtest.py`
- **calibrate()** (6 connections) — `app/engine/abtest.py`
- **_Pos** (5 connections) — `app/engine/abtest.py`
- **grade()** (5 connections) — `app/engine/strategygrade.py`
- **recorded_entry_model()** (4 connections) — `app/engine/abtest.py`
- **_leg_r()** (3 connections) — `app/engine/abtest.py`
- **_load_setups()** (3 connections) — `app/engine/abtest.py`
- **_cluster_bootstrap()** (3 connections) — `app/engine/abtest.py`
- **summarise()** (3 connections) — `app/engine/abtest.py`
- **_verdict()** (3 connections) — `app/engine/abtest.py`
- **_holm()** (3 connections) — `app/engine/strategygrade.py`
- **main()** (3 connections) — `app/engine/strategygrade.py`
- **.r_at()** (2 connections) — `app/engine/abtest.py`
- **_bisect_fill()** (2 connections) — `app/engine/abtest.py`
- **main()** (2 connections) — `app/engine/abtest.py`
- **_render()** (2 connections) — `app/engine/strategygrade.py`
- **.__init__()** (1 connections) — `app/engine/abtest.py`
- **2x2 replay harness — the gate on setup-v0.7. READ-ONLY, writes no facts.  `doc** (1 connections) — `app/engine/abtest.py`
- **Open position state. Exists because a managed exit cannot be expressed     as a** (1 connections) — `app/engine/abtest.py`
- *... and 12 more nodes in this community*

## Relationships

- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (4 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (3 shared connections)
- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (2 shared connections)
- [T](T.md) (1 shared connections)

## Source Files

- `app/engine/abtest.py`
- `app/engine/strategygrade.py`
- `app/engine/universe.py`

## Audit Trail

- EXTRACTED: 127 (99%)
- INFERRED: 1 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*