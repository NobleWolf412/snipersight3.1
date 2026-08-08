# Volatility Engine

> 12 nodes

## Key Concepts

- **volatility.py** (15 connections) — `app/engine/volatility.py`
- **run()** (9 connections) — `app/engine/volatility.py`
- **Decimal** (6 connections)
- **keltner()** (6 connections) — `app/engine/volatility.py`
- **bollinger()** (5 connections) — `app/engine/volatility.py`
- **atr_regime()** (4 connections) — `app/engine/volatility.py`
- **atr_percentiles()** (4 connections) — `app/engine/volatility.py`
- **Volatility engine — ATR percentile, Bollinger width, and the squeeze. algo vola** (1 connections) — `app/engine/volatility.py`
- **(middle, upper, lower) per bar index; None inside the warmup.      POPULATION** (1 connections) — `app/engine/volatility.py`
- **(middle, upper, lower) per bar index, EMA-centred and ATR-scaled.      ATR is** (1 connections) — `app/engine/volatility.py`
- **Schmitt-triggered percentile bucket. Enter at 20/80, leave at 30/70.** (1 connections) — `app/engine/volatility.py`
- **Rank of each ATR within the trailing `window` values, as a percentage.      MI** (1 connections) — `app/engine/volatility.py`

## Relationships

- [Indicator Engines](Indicator_Engines.md) (8 shared connections)
- [Swings, Zones & Draft Bracket](Swings%2C_Zones_%26_Draft_Bracket.md) (3 shared connections)
- [Bias, Trend & Setups](Bias%2C_Trend_%26_Setups.md) (2 shared connections)
- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (1 shared connections)

## Source Files

- `app/engine/volatility.py`

## Audit Trail

- EXTRACTED: 54 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*