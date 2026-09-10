# deck

> 17 nodes

## Key Concepts

- **risk.py** (15 connections) — `app/engine/risk.py`
- **run()** (9 connections) — `app/engine/risk.py`
- **Decimal** (5 connections)
- **_venue_max_leverage()** (5 connections) — `app/engine/risk.py`
- **size_order()** (5 connections) — `app/engine/risk.py`
- **gates_for_mode()** (4 connections) — `app/engine/risk.py`
- **dispatch_scale()** (3 connections) — `app/engine/risk.py`
- **_venue_allows_shorts()** (3 connections) — `app/engine/risk.py`
- **_symbols()** (3 connections) — `app/engine/risk.py`
- **_day()** (2 connections) — `app/engine/risk.py`
- **Risk Authority — §9: strategies request risk, this engine decides. Paper only.** (1 connections) — `app/engine/risk.py`
- **THE authority on the envelope. Every reader — the replay, the sizer,     the AP** (1 connections) — `app/engine/risk.py`
- **Quantity scale from the paper-sized risk fact to this mode's R.      The repla** (1 connections) — `app/engine/risk.py`
- **Venue capability. An unrecognised symbol falls back to the SPOT answer —     re** (1 connections) — `app/engine/risk.py`
- **Same conservative fallback: 1x when the venue is unknown.** (1 connections) — `app/engine/risk.py`
- **PURE sizing. No I/O, no facts, no clock — equity and a bracket in, a     decisi** (1 connections) — `app/engine/risk.py`
- **Every symbol with stored candles — portfolio scope spans the universe.** (1 connections) — `app/engine/risk.py`

## Relationships

- [Breakeven Fee Tests](Breakeven_Fee_Tests.md) (4 shared connections)
- [Copilot Pack Builder](Copilot_Pack_Builder.md) (1 shared connections)
- [Chart Vendor Chart API](Chart_Vendor_Chart_API.md) (1 shared connections)
- [Chart Vendor Price Scale Formatting](Chart_Vendor_Price_Scale_Formatting.md) (1 shared connections)

## Source Files

- `app/engine/risk.py`

## Audit Trail

- EXTRACTED: 61 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*