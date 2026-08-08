# A/B Test Engine

> 15 nodes

## Key Concepts

- **abtest.py** (17 connections) — `app/engine/abtest.py`
- **run_variant()** (9 connections) — `app/engine/abtest.py`
- **report()** (7 connections) — `app/engine/abtest.py`
- **calibrate()** (6 connections) — `app/engine/abtest.py`
- **by_strategy()** (4 connections) — `app/engine/abtest.py`
- **summarise()** (3 connections) — `app/engine/abtest.py`
- **_verdict()** (3 connections) — `app/engine/abtest.py`
- **_load_setups()** (2 connections) — `app/engine/abtest.py`
- **_bisect_fill()** (2 connections) — `app/engine/abtest.py`
- **main()** (2 connections) — `app/engine/abtest.py`
- **2x2 replay harness — the gate on setup-v0.7. READ-ONLY, writes no facts.  `doc** (1 connections) — `app/engine/abtest.py`
- **One cell of the 2x2. Returns per-trade results, never aggregates alone.      `** (1 connections) — `app/engine/abtest.py`
- **Replay the live book and split it by PLAYBOOK, with intervals.      The aggreg** (1 connections) — `app/engine/abtest.py`
- **Reproduce the RECORDED book TRADE BY TRADE, and say plainly whether we     mana** (1 connections) — `app/engine/abtest.py`
- **State which change earned the result — including 'neither'.** (1 connections) — `app/engine/abtest.py`

## Relationships

- [A/B Position Simulation](A-B_Position_Simulation.md) (4 shared connections)
- [Swings, Zones & Draft Bracket](Swings%2C_Zones_%26_Draft_Bracket.md) (3 shared connections)
- [A/B Calibration Tests](A-B_Calibration_Tests.md) (2 shared connections)
- [Market Data Importer](Market_Data_Importer.md) (1 shared connections)

## Source Files

- `app/engine/abtest.py`

## Audit Trail

- EXTRACTED: 60 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*