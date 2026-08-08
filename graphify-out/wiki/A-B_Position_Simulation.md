# A/B Position Simulation

> 8 nodes

## Key Concepts

- **_simulate()** (6 connections) — `app/engine/abtest.py`
- **_Pos** (5 connections) — `app/engine/abtest.py`
- **_leg_r()** (3 connections) — `app/engine/abtest.py`
- **.r_at()** (2 connections) — `app/engine/abtest.py`
- **.__init__()** (1 connections) — `app/engine/abtest.py`
- **Open position state. Exists because a managed exit cannot be expressed     as a** (1 connections) — `app/engine/abtest.py`
- **NET R of one closed leg, priced by execsim.settle — THE costing.      This rep** (1 connections) — `app/engine/abtest.py`
- **Walk bars from the fill and return one outcome dict, or None if the data     ru** (1 connections) — `app/engine/abtest.py`

## Relationships

- [A/B Test Engine](A-B_Test_Engine.md) (4 shared connections)

## Source Files

- `app/engine/abtest.py`

## Audit Trail

- EXTRACTED: 20 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*