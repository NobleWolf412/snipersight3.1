# Swings, Zones & Draft Bracket

> 33 nodes

## Key Concepts

- **compute_atr()** (40 connections) — `app/engine/swings.py`
- **swings.py** (29 connections) — `app/engine/swings.py`
- **quote_ticks()** (20 connections) — `app/engine/swings.py`
- **zones.py** (13 connections) — `app/engine/zones.py`
- **liquidity.py** (10 connections) — `app/engine/liquidity.py`
- **draft.py** (9 connections) — `app/engine/draft.py`
- **alternate()** (7 connections) — `app/engine/swings.py`
- **run()** (7 connections) — `app/engine/swings.py`
- **run()** (7 connections) — `app/engine/zones.py`
- **for_symbol()** (6 connections) — `app/engine/draft.py`
- **bracket()** (4 connections) — `app/engine/draft.py`
- **run()** (4 connections) — `app/engine/liquidity.py`
- **_latest_by_id()** (3 connections) — `app/engine/draft.py`
- **Decimal** (3 connections)
- **detect_micro()** (3 connections) — `app/engine/swings.py`
- **promote_tier()** (3 connections) — `app/engine/swings.py`
- **formation_quality()** (3 connections) — `app/engine/zones.py`
- **freshness()** (3 connections) — `app/engine/zones.py`
- **strength()** (2 connections) — `app/engine/zones.py`
- **Structure-anchored DRAFT bracket for the order ticket. Writes nothing.  ## What** (1 connections) — `app/engine/draft.py`
- **Last recorded state per object. Facts are append-only, so a zone appears     onc** (1 connections) — `app/engine/draft.py`
- **Draft entry/stop/target from live structure, or None if there is none.      Retu** (1 connections) — `app/engine/draft.py`
- **Draft for one symbol/timeframe, read straight from the stored facts.** (1 connections) — `app/engine/draft.py`
- **Liquidity engine — equal highs/lows pools and sweeps. algo liq-v0.1-draft.  Dr** (1 connections) — `app/engine/liquidity.py`
- **Swing engine — micro and local swings per spec §20, algo swing-v0.1-draft.  Dr** (1 connections) — `app/engine/swings.py`
- *... and 8 more nodes in this community*

## Relationships

- [Bias, Trend & Setups](Bias%2C_Trend_%26_Setups.md) (32 shared connections)
- [Volume, Ranges & Aggregation](Volume%2C_Ranges_%26_Aggregation.md) (12 shared connections)
- [Indicator Engines](Indicator_Engines.md) (11 shared connections)
- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (6 shared connections)
- [Manual Trading Engine](Manual_Trading_Engine.md) (4 shared connections)
- [A/B Test Engine](A-B_Test_Engine.md) (3 shared connections)
- [Volatility Engine](Volatility_Engine.md) (3 shared connections)
- [Cross-Fill Honesty Tests](Cross-Fill_Honesty_Tests.md) (2 shared connections)
- [FVG & Volume Profile Tests](FVG_%26_Volume_Profile_Tests.md) (2 shared connections)
- [Zone Causality Tests](Zone_Causality_Tests.md) (2 shared connections)
- [Trend Engine Tests](Trend_Engine_Tests.md) (1 shared connections)
- [Bias Ladder Engine](Bias_Ladder_Engine.md) (1 shared connections)

## Source Files

- `app/engine/draft.py`
- `app/engine/liquidity.py`
- `app/engine/swings.py`
- `app/engine/zones.py`

## Audit Trail

- EXTRACTED: 185 (97%)
- INFERRED: 5 (3%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*