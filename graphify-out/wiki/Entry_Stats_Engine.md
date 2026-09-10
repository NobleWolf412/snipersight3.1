# Entry Stats Engine

> 30 nodes

## Key Concepts

- **entrystats.py** (30 connections) — `app/engine/entrystats.py`
- **report()** (11 connections) — `app/engine/entrystats.py`
- **format_report()** (6 connections) — `app/engine/entrystats.py`
- **_summary()** (5 connections) — `app/engine/entrystats.py`
- **adverse_selection()** (5 connections) — `app/engine/entrystats.py`
- **fill_rate()** (4 connections) — `app/engine/entrystats.py`
- **rr_distortion()** (4 connections) — `app/engine/entrystats.py`
- **same_bar_resolution()** (4 connections) — `app/engine/entrystats.py`
- **book_counterfactual()** (4 connections) — `app/engine/entrystats.py`
- **main()** (4 connections) — `app/engine/entrystats.py`
- **_tf_sort_key()** (3 connections) — `app/engine/entrystats.py`
- **_adverse_verdict()** (3 connections) — `app/engine/entrystats.py`
- **entry_probe()** (3 connections) — `app/engine/entrystats.py`
- **_wrap()** (3 connections) — `app/engine/entrystats.py`
- **_pearson()** (2 connections) — `app/engine/entrystats.py`
- **_pct()** (2 connections) — `app/engine/entrystats.py`
- **_num()** (2 connections) — `app/engine/entrystats.py`
- **Entry statistics — was the resting limit at the zone edge ADVERSELY SELECTED? R** (1 connections) — `app/engine/entrystats.py`
- **Pearson r, or None when it is undefined (n<2, or either side constant).      A** (1 connections) — `app/engine/entrystats.py`
- **Mean/median/min/max of an R series. None on an empty series — not zero.** (1 connections) — `app/engine/entrystats.py`
- **1. filled / (filled + MISSED), overall and per timeframe.      CEILING, not an** (1 connections) — `app/engine/entrystats.py`
- **2. Were the limits that FILLED the ones about to lose?      A missed order has** (1 connections) — `app/engine/entrystats.py`
- **The one-line answer, phrased so a counterfactual can never be mistaken for** (1 connections) — `app/engine/entrystats.py`
- **3. Planned R:R against the R:R the ACTUAL fill implies, on the same SL/TP.** (1 connections) — `app/engine/entrystats.py`
- **4. Does anything visible at entry correlate with realised R?      Judged again** (1 connections) — `app/engine/entrystats.py`
- *... and 5 more nodes in this community*

## Relationships

- [Manual Order Idempotency Tests](Manual_Order_Idempotency_Tests.md) (13 shared connections)
- [Telemetry API Tests](Telemetry_API_Tests.md) (2 shared connections)
- [Kraken Adapter](Kraken_Adapter.md) (1 shared connections)

## Source Files

- `app/engine/entrystats.py`

## Audit Trail

- EXTRACTED: 104 (96%)
- INFERRED: 4 (4%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*