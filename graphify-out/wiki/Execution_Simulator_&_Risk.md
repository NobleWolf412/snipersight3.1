# Execution Simulator & Risk

> 19 nodes

## Key Concepts

- **risk.py** (21 connections) — `app/engine/risk.py`
- **run()** (11 connections) — `app/engine/risk.py`
- **Decimal** (5 connections)
- **_venue_max_leverage()** (5 connections) — `app/engine/risk.py`
- **size_order()** (5 connections) — `app/engine/risk.py`
- **gates_for_mode()** (4 connections) — `app/engine/risk.py`
- **_symbols()** (4 connections) — `app/engine/risk.py`
- **admitted_at()** (4 connections) — `app/engine/universe.py`
- **dispatch_scale()** (3 connections) — `app/engine/risk.py`
- **_venue_allows_shorts()** (3 connections) — `app/engine/risk.py`
- **_day()** (2 connections) — `app/engine/risk.py`
- **Risk Authority — §9: strategies request risk, this engine decides. Paper only.** (1 connections) — `app/engine/risk.py`
- **THE authority on the envelope. Every reader — the replay, the sizer,     the AP** (1 connections) — `app/engine/risk.py`
- **Quantity scale from the paper-sized risk fact to this mode's R.      The repla** (1 connections) — `app/engine/risk.py`
- **Venue capability. An unrecognised symbol falls back to the SPOT answer —     re** (1 connections) — `app/engine/risk.py`
- **Same conservative fallback: 1x when the venue is unknown.** (1 connections) — `app/engine/risk.py`
- **PURE sizing. No I/O, no facts, no clock — equity and a bracket in, a     decisi** (1 connections) — `app/engine/risk.py`
- **Every symbol with stored candles — portfolio scope spans the universe.** (1 connections) — `app/engine/risk.py`
- **Point-in-time eligibility used to prevent present-universe backtests.** (1 connections) — `app/engine/universe.py`

## Relationships

- [Shell Navigation & Near Levels](Shell_Navigation_%26_Near_Levels.md) (4 shared connections)
- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (4 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (2 shared connections)
- [A/B Test Engine](A-B_Test_Engine.md) (2 shared connections)
- [A/B Calibration Tests](A-B_Calibration_Tests.md) (1 shared connections)
- [Cycle Detection Engine](Cycle_Detection_Engine.md) (1 shared connections)
- [Copilot Pack Builder](Copilot_Pack_Builder.md) (1 shared connections)

## Source Files

- `app/engine/risk.py`
- `app/engine/universe.py`

## Audit Trail

- EXTRACTED: 75 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*