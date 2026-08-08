# Execution Simulator & Risk

> 30 nodes

## Key Concepts

- **runlog.py** (28 connections) — `app/engine/runlog.py`
- **execsim.py** (19 connections) — `app/engine/execsim.py`
- **risk.py** (17 connections) — `app/engine/risk.py`
- **run()** (10 connections) — `app/engine/risk.py`
- **run()** (8 connections) — `app/engine/execsim.py`
- **plan_versions()** (6 connections) — `app/engine/execsim.py`
- **_venue_max_leverage()** (5 connections) — `app/engine/risk.py`
- **settle()** (4 connections) — `app/engine/execsim.py`
- **simulate_entry()** (4 connections) — `app/engine/execsim.py`
- **Decimal** (4 connections)
- **size_order()** (4 connections) — `app/engine/risk.py`
- **_symbols()** (4 connections) — `app/engine/risk.py`
- **admitted_at()** (4 connections) — `app/engine/universe.py`
- **walk_exit()** (3 connections) — `app/engine/execsim.py`
- **cross_fill()** (3 connections) — `app/engine/execsim.py`
- **_venue_allows_shorts()** (3 connections) — `app/engine/risk.py`
- **_day()** (2 connections) — `app/engine/risk.py`
- **Execution simulator — paper-trades every VALIDATED setup. algo exec-v0.1-draft.** (1 connections) — `app/engine/execsim.py`
- **Walk forward from the fill bar to a terminal outcome.      Returns (outcome, e** (1 connections) — `app/engine/execsim.py`
- **The price a crossing market order actually gets, and the ONE definition.** (1 connections) — `app/engine/execsim.py`
- **Price one closed leg: slippage, fees, funding, and the R they leave.      THE** (1 connections) — `app/engine/execsim.py`
- **Turn a PLAN into the fill it actually got: which bar, what price, whose     fee** (1 connections) — `app/engine/execsim.py`
- **THE definition of what this book trades — the setup generations the     simulat** (1 connections) — `app/engine/execsim.py`
- **Risk Authority — §9: strategies request risk, this engine decides. Paper only.** (1 connections) — `app/engine/risk.py`
- **Venue capability. An unrecognised symbol falls back to the SPOT answer —     re** (1 connections) — `app/engine/risk.py`
- *... and 5 more nodes in this community*

## Relationships

- [Bias, Trend & Setups](Bias%2C_Trend_%26_Setups.md) (14 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (6 shared connections)
- [Swings, Zones & Draft Bracket](Swings%2C_Zones_%26_Draft_Bracket.md) (6 shared connections)
- [Indicator Engines](Indicator_Engines.md) (4 shared connections)
- [Manual Trading Engine](Manual_Trading_Engine.md) (2 shared connections)
- [Live Scanner Loop](Live_Scanner_Loop.md) (2 shared connections)
- [A/B Calibration Tests](A-B_Calibration_Tests.md) (2 shared connections)
- [Volume, Ranges & Aggregation](Volume%2C_Ranges_%26_Aggregation.md) (2 shared connections)
- [Edge Statistics Engine](Edge_Statistics_Engine.md) (1 shared connections)
- [Factor Statistics Engine](Factor_Statistics_Engine.md) (1 shared connections)
- [Funding Rate Engine](Funding_Rate_Engine.md) (1 shared connections)
- [Copilot Pack Builder](Copilot_Pack_Builder.md) (1 shared connections)

## Source Files

- `app/engine/execsim.py`
- `app/engine/risk.py`
- `app/engine/runlog.py`
- `app/engine/universe.py`

## Audit Trail

- EXTRACTED: 140 (99%)
- INFERRED: 1 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*