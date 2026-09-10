# t

> 37 nodes

## Key Concepts

- **compute_atr()** (32 connections) — `app/engine/swings.py`
- **swings.py** (24 connections) — `app/engine/swings.py`
- **quote_ticks()** (16 connections) — `app/engine/swings.py`
- **zones.py** (12 connections) — `app/engine/zones.py`
- **structure.py** (10 connections) — `app/engine/structure.py`
- **draft.py** (9 connections) — `app/engine/draft.py`
- **liquidity.py** (9 connections) — `app/engine/liquidity.py`
- **alternate()** (7 connections) — `app/engine/swings.py`
- **run()** (7 connections) — `app/engine/zones.py`
- **for_symbol()** (6 connections) — `app/engine/draft.py`
- **run()** (5 connections) — `app/engine/swings.py`
- **run()** (5 connections) — `app/engine/structure.py`
- **bracket()** (4 connections) — `app/engine/draft.py`
- **run()** (4 connections) — `app/engine/liquidity.py`
- **detect_micro()** (3 connections) — `app/engine/swings.py`
- **promote_tier()** (3 connections) — `app/engine/swings.py`
- **_latest_by_id()** (3 connections) — `app/engine/draft.py`
- **Decimal** (3 connections)
- **formation_quality()** (3 connections) — `app/engine/zones.py`
- **freshness()** (3 connections) — `app/engine/zones.py`
- **_tier_swings()** (2 connections) — `app/engine/structure.py`
- **strength()** (2 connections) — `app/engine/zones.py`
- **Swing engine — micro and local swings per spec §20, algo swing-v0.1-draft.  Dr** (1 connections) — `app/engine/swings.py`
- **ATR14 per bar index; None until enough history exists.** (1 connections) — `app/engine/swings.py`
- **Per-bar minimum price increment, read off the venue's own quoting.      "1 tic** (1 connections) — `app/engine/swings.py`
- *... and 12 more nodes in this community*

## Relationships

- [Onboarding Path Tests](Onboarding_Path_Tests.md) (10 shared connections)
- [Chart Vendor Chart API](Chart_Vendor_Chart_API.md) (7 shared connections)
- [Confound Guard Tests](Confound_Guard_Tests.md) (7 shared connections)
- [Indicator Engines](Indicator_Engines.md) (6 shared connections)
- [zt](zt.md) (5 shared connections)
- [volume.py](volume.py.md) (5 shared connections)
- [_facts](_facts.md) (4 shared connections)
- [A/B Test Engine](A-B_Test_Engine.md) (3 shared connections)
- [volatility.py](volatility.py.md) (3 shared connections)
- [Cross-Fill Honesty Tests](Cross-Fill_Honesty_Tests.md) (2 shared connections)
- [FVG & Volume Profile Tests](FVG_%26_Volume_Profile_Tests.md) (2 shared connections)
- [Zone Causality Tests](Zone_Causality_Tests.md) (2 shared connections)

## Source Files

- `app/engine/draft.py`
- `app/engine/liquidity.py`
- `app/engine/structure.py`
- `app/engine/swings.py`
- `app/engine/zones.py`

## Audit Trail

- EXTRACTED: 183 (98%)
- INFERRED: 4 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*