# Bias Ladder Engine

> 29 nodes

## Key Concepts

- **bias.py** (14 connections) — `app/engine/bias.py`
- **Bias** (7 connections) — `app/engine/bias.py`
- **.check()** (7 connections) — `app/engine/bias.py`
- **.reading()** (5 connections) — `app/engine/bias.py`
- **load()** (5 connections) — `app/engine/bias.py`
- **rungs_above()** (4 connections) — `app/engine/bias.py`
- **composite()** (4 connections) — `app/engine/bias.py`
- **alignment()** (4 connections) — `app/engine/bias.py`
- **verdict()** (4 connections) — `app/engine/bias.py`
- **.evidence()** (4 connections) — `app/engine/bias.py`
- **blocked()** (3 connections) — `app/engine/bias.py`
- **_as_of()** (3 connections) — `app/engine/bias.py`
- **inputs()** (3 connections) — `app/engine/bias.py`
- **validate_policy()** (2 connections) — `app/engine/bias.py`
- **.__init__()** (1 connections) — `app/engine/bias.py`
- **Top-down bias — what the timeframes ABOVE this one are doing. algo bias-v0.1-dra** (1 connections) — `app/engine/bias.py`
- **Did this check refuse the trade? The one place that question is asked.      Tr** (1 connections) — `app/engine/bias.py`
- **Every timeframe above `tf`, nearest first. ("1H","4H","1D","1W") for 15m.** (1 connections) — `app/engine/bias.py`
- **The last reading CONFIRMED at or before `ts`, or None.      The as-of discipli** (1 connections) — `app/engine/bias.py`
- **Fold per-rung sides into one state. See the module docstring.      `sides` is** (1 connections) — `app/engine/bias.py`
- **Where a trade in `direction` stands against the composite.      WITH / AGAINST** (1 connections) — `app/engine/bias.py`
- **Reject a malformed policy at import time rather than at trade time.      Three** (1 connections) — `app/engine/bias.py`
- **Pure: the reading plus a policy plus the evidence flag -> what to do.      Pur** (1 connections) — `app/engine/bias.py`
- **One symbol/timeframe's view up the ladder, loaded once, read many times.** (1 connections) — `app/engine/bias.py`
- **What every rung above was showing at `as_of`, and the composite.** (1 connections) — `app/engine/bias.py`
- *... and 4 more nodes in this community*

## Relationships

- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (7 shared connections)
- [Bias Ladder Tests](Bias_Ladder_Tests.md) (1 shared connections)
- [Funding Rate Engine](Funding_Rate_Engine.md) (1 shared connections)
- [Cycle Detection Engine](Cycle_Detection_Engine.md) (1 shared connections)

## Source Files

- `app/engine/bias.py`

## Audit Trail

- EXTRACTED: 81 (96%)
- INFERRED: 3 (4%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*