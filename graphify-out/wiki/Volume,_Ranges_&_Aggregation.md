# Volume, Ranges & Aggregation

> 32 nodes

## Key Concepts

- **volume.py** (20 connections) — `app/engine/volume.py`
- **ranges.py** (15 connections) — `app/engine/ranges.py`
- **run()** (14 connections) — `app/engine/volume.py`
- **break_tolerance()** (10 connections) — `app/engine/ranges.py`
- **run()** (10 connections) — `app/engine/ranges.py`
- **Decimal** (7 connections)
- **Decimal** (5 connections)
- **contained()** (5 connections) — `app/engine/ranges.py`
- **aggregator.py** (4 connections) — `app/engine/aggregator.py`
- **is_flat()** (4 connections) — `app/engine/ranges.py`
- **price_bin()** (4 connections) — `app/engine/volume.py`
- **bin_price()** (4 connections) — `app/engine/volume.py`
- **typical()** (4 connections) — `app/engine/volume.py`
- **rvol_state()** (4 connections) — `app/engine/volume.py`
- **point_of_control()** (4 connections) — `app/engine/volume.py`
- **boundaries()** (3 connections) — `app/engine/ranges.py`
- **session_start()** (3 connections) — `app/engine/volume.py`
- **_bucket_start()** (2 connections) — `app/engine/aggregator.py`
- **aggregate()** (2 connections) — `app/engine/aggregator.py`
- **Canonical higher-timeframe candle aggregator (§19).  4H is built from 1H (UTC-al** (1 connections) — `app/engine/aggregator.py`
- **Range engine — horizontal ranges, their boundaries, and their lifecycle. algo r** (1 connections) — `app/engine/ranges.py`
- **The house break tolerance: max(1 tick, 0.05*ATR).      structure.py, zones.py** (1 connections) — `app/engine/ranges.py`
- **(top, bottom, n_top, n_bottom) — the EXTREME of each cluster, not its mean.** (1 connections) — `app/engine/ranges.py`
- **Do the pivots CLUSTER at two levels rather than march in one direction?      S** (1 connections) — `app/engine/ranges.py`
- **Did every bar of the formation window close inside the band?      Closes only** (1 connections) — `app/engine/ranges.py`
- *... and 7 more nodes in this community*

## Relationships

- [Swings, Zones & Draft Bracket](Swings%2C_Zones_%26_Draft_Bracket.md) (12 shared connections)
- [Indicator Engines](Indicator_Engines.md) (8 shared connections)
- [Bias, Trend & Setups](Bias%2C_Trend_%26_Setups.md) (4 shared connections)
- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (2 shared connections)
- [Volume Engine Tests](Volume_Engine_Tests.md) (1 shared connections)

## Source Files

- `app/engine/aggregator.py`
- `app/engine/ranges.py`
- `app/engine/volume.py`

## Audit Trail

- EXTRACTED: 136 (99%)
- INFERRED: 1 (1%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*