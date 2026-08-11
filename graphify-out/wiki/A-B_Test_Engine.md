# A/B Test Engine

> 27 nodes

## Key Concepts

- **abtest.py** (18 connections) — `app/engine/abtest.py`
- **run_variant()** (9 connections) — `app/engine/abtest.py`
- **all_tracked_symbols()** (9 connections) — `app/engine/universe.py`
- **report()** (7 connections) — `app/engine/abtest.py`
- **_simulate()** (6 connections) — `app/engine/abtest.py`
- **calibrate()** (6 connections) — `app/engine/abtest.py`
- **_Pos** (5 connections) — `app/engine/abtest.py`
- **by_strategy()** (5 connections) — `app/engine/abtest.py`
- **_leg_r()** (3 connections) — `app/engine/abtest.py`
- **_cluster_bootstrap()** (3 connections) — `app/engine/abtest.py`
- **summarise()** (3 connections) — `app/engine/abtest.py`
- **_verdict()** (3 connections) — `app/engine/abtest.py`
- **.r_at()** (2 connections) — `app/engine/abtest.py`
- **_load_setups()** (2 connections) — `app/engine/abtest.py`
- **_bisect_fill()** (2 connections) — `app/engine/abtest.py`
- **main()** (2 connections) — `app/engine/abtest.py`
- **.__init__()** (1 connections) — `app/engine/abtest.py`
- **2x2 replay harness — the gate on setup-v0.7. READ-ONLY, writes no facts.  `doc** (1 connections) — `app/engine/abtest.py`
- **Open position state. Exists because a managed exit cannot be expressed     as a** (1 connections) — `app/engine/abtest.py`
- **NET R of one closed leg, priced by execsim.settle — THE costing.      This rep** (1 connections) — `app/engine/abtest.py`
- **Walk bars from the fill and return one outcome dict, or None if the data     ru** (1 connections) — `app/engine/abtest.py`
- **One cell of the 2x2. Returns per-trade results, never aggregates alone.      `** (1 connections) — `app/engine/abtest.py`
- **Bootstrap the mean by resampling SYMBOLS, not trades.      The IID bootstrap i** (1 connections) — `app/engine/abtest.py`
- **Replay the live book and split it by PLAYBOOK, with intervals.      The aggreg** (1 connections) — `app/engine/abtest.py`
- **Reproduce the RECORDED book TRADE BY TRADE, and say plainly whether we     mana** (1 connections) — `app/engine/abtest.py`
- *... and 2 more nodes in this community*

## Relationships

- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (3 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (2 shared connections)
- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (2 shared connections)
- [TestPointInTimeUniverse](TestPointInTimeUniverse.md) (2 shared connections)
- [CalibrationAgainstTheLiveStore](CalibrationAgainstTheLiveStore.md) (1 shared connections)

## Source Files

- `app/engine/abtest.py`
- `app/engine/universe.py`

## Audit Trail

- EXTRACTED: 95 (99%)
- INFERRED: 1 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*