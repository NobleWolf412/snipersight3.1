# Bias Ladder Engine

> 12 nodes

## Key Concepts

- **bias.py** (14 connections) — `app/engine/bias.py`
- **load()** (5 connections) — `app/engine/bias.py`
- **rungs_above()** (4 connections) — `app/engine/bias.py`
- **blocked()** (3 connections) — `app/engine/bias.py`
- **inputs()** (3 connections) — `app/engine/bias.py`
- **validate_policy()** (2 connections) — `app/engine/bias.py`
- **Top-down bias — what the timeframes ABOVE this one are doing. algo bias-v0.1-dra** (1 connections) — `app/engine/bias.py`
- **Did this check refuse the trade? The one place that question is asked.      Tr** (1 connections) — `app/engine/bias.py`
- **Every timeframe above `tf`, nearest first. ("1H","4H","1D","1W") for 15m.** (1 connections) — `app/engine/bias.py`
- **Reject a malformed policy at import time rather than at trade time.      Three** (1 connections) — `app/engine/bias.py`
- **Read every rung's regime series and this timeframe's breaks, once.** (1 connections) — `app/engine/bias.py`
- **What a strategy manifest should record about this layer's own inputs.** (1 connections) — `app/engine/bias.py`

## Relationships

- [.ja](ja.md) (6 shared connections)
- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (6 shared connections)
- [Ladder](Ladder.md) (1 shared connections)

## Source Files

- `app/engine/bias.py`

## Audit Trail

- EXTRACTED: 37 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*