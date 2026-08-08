# Bias Ladder Engine

> 17 nodes

## Key Concepts

- **Bias** (7 connections) — `app/engine/bias.py`
- **.check()** (6 connections) — `app/engine/bias.py`
- **alignment()** (5 connections) — `app/engine/bias.py`
- **.reading()** (5 connections) — `app/engine/bias.py`
- **.evidence()** (5 connections) — `app/engine/bias.py`
- **composite()** (4 connections) — `app/engine/bias.py`
- **verdict()** (4 connections) — `app/engine/bias.py`
- **_as_of()** (3 connections) — `app/engine/bias.py`
- **.__init__()** (1 connections) — `app/engine/bias.py`
- **The last reading CONFIRMED at or before `ts`, or None.      The as-of discipli** (1 connections) — `app/engine/bias.py`
- **Fold per-rung sides into one state. See the module docstring.      `sides` is** (1 connections) — `app/engine/bias.py`
- **Where a trade in `direction` stands against the composite.      WITH / AGAINST** (1 connections) — `app/engine/bias.py`
- **Pure: the reading plus a policy plus the evidence flag -> what to do.      Pur** (1 connections) — `app/engine/bias.py`
- **One symbol/timeframe's view up the ladder, loaded once, read many times.** (1 connections) — `app/engine/bias.py`
- **What every rung above was showing at `as_of`, and the composite.** (1 connections) — `app/engine/bias.py`
- **Did structure just break in this trade's favour, and how recently?          Th** (1 connections) — `app/engine/bias.py`
- **The whole block a setup fact should carry. The one call an engine makes.** (1 connections) — `app/engine/bias.py`

## Relationships

- [Bias, Trend & Setups](Bias%2C_Trend_%26_Setups.md) (6 shared connections)
- [Venue Policy & Contract](Venue_Policy_%26_Contract.md) (2 shared connections)
- [Factor Statistics Engine](Factor_Statistics_Engine.md) (1 shared connections)
- [Swings, Zones & Draft Bracket](Swings%2C_Zones_%26_Draft_Bracket.md) (1 shared connections)

## Source Files

- `app/engine/bias.py`

## Audit Trail

- EXTRACTED: 44 (92%)
- INFERRED: 4 (8%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*