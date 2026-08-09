# volume.py

> 16 nodes

## Key Concepts

- **volume.py** (20 connections) — `app/engine/volume.py`
- **run()** (14 connections) — `app/engine/volume.py`
- **Decimal** (7 connections)
- **price_bin()** (4 connections) — `app/engine/volume.py`
- **bin_price()** (4 connections) — `app/engine/volume.py`
- **typical()** (4 connections) — `app/engine/volume.py`
- **rvol_state()** (4 connections) — `app/engine/volume.py`
- **point_of_control()** (4 connections) — `app/engine/volume.py`
- **session_start()** (3 connections) — `app/engine/volume.py`
- **Volume engine — relative volume, session VWAP, and where volume actually sat. al** (1 connections) — `app/engine/volume.py`
- **Index of the 4-significant-digit bin containing `p`.      Scale-free by construc** (1 connections) — `app/engine/volume.py`
- **The representative (lower-edge) price of a bin. Exact inverse of     `price_bin`** (1 connections) — `app/engine/volume.py`
- **(high + low + close) / 3 — the standard single-price proxy for where a     bar's** (1 connections) — `app/engine/volume.py`
- **UTC-midnight or Monday-midnight bucket start.      The weekly boundary is `aggre** (1 connections) — `app/engine/volume.py`
- **Schmitt-triggered relative-volume state. Enter at 2.0x/0.5x, leave at     1.5x/0** (1 connections) — `app/engine/volume.py`
- **(bin index, volume) of the heaviest bin.      The tie-break is explicit — highes** (1 connections) — `app/engine/volume.py`

## Relationships

- [ranges.py](ranges.py.md) (6 shared connections)
- [Indicator Engines](Indicator_Engines.md) (5 shared connections)
- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (5 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (1 shared connections)

## Source Files

- `app/engine/volume.py`

## Audit Trail

- EXTRACTED: 71 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*