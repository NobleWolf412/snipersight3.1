# Breakeven Fee Tests

> 15 nodes

## Key Concepts

- **execsim.py** (15 connections) — `app/engine/execsim.py`
- **plan_versions()** (5 connections) — `app/engine/execsim.py`
- **run()** (5 connections) — `app/engine/execsim.py`
- **settle()** (4 connections) — `app/engine/execsim.py`
- **simulate_entry()** (4 connections) — `app/engine/execsim.py`
- **walk_exit()** (3 connections) — `app/engine/execsim.py`
- **cross_fill()** (3 connections) — `app/engine/execsim.py`
- **unresolved()** (2 connections) — `app/engine/execsim.py`
- **Execution simulator — paper-trades every VALIDATED setup. algo exec-v0.1-draft.** (1 connections) — `app/engine/execsim.py`
- **Current simulator orders that still need market data to become terminal.** (1 connections) — `app/engine/execsim.py`
- **Walk forward from the fill bar to a terminal outcome.      Returns (outcome, e** (1 connections) — `app/engine/execsim.py`
- **The price a crossing market order actually gets, and the ONE definition.** (1 connections) — `app/engine/execsim.py`
- **Price one closed leg: slippage, fees, funding, and the R they leave.      THE** (1 connections) — `app/engine/execsim.py`
- **Turn a PLAN into the fill it actually got: which bar, what price, whose     fee** (1 connections) — `app/engine/execsim.py`
- **THE definition of what this book trades — the setup generations the     simulat** (1 connections) — `app/engine/execsim.py`

## Relationships

- [deck](deck.md) (4 shared connections)
- [Chart Vendor Chart API](Chart_Vendor_Chart_API.md) (2 shared connections)
- [Kraken Adapter](Kraken_Adapter.md) (1 shared connections)
- [Volume, Ranges & Aggregation](Volume%2C_Ranges_%26_Aggregation.md) (1 shared connections)
- [funding.py](funding.py.md) (1 shared connections)
- [_facts](_facts.md) (1 shared connections)

## Source Files

- `app/engine/execsim.py`

## Audit Trail

- EXTRACTED: 48 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*