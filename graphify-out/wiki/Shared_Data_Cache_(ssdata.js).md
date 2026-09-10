# Shared Data Cache (ssdata.js)

> 24 nodes

## Key Concepts

- **regimeread.py** (12 connections) — `app/engine/regimeread.py`
- **Reading** (6 connections) — `app/engine/regimeread.py`
- **annotate()** (6 connections) — `app/engine/regimeread.py`
- **.at()** (5 connections) — `app/engine/regimeread.py`
- **grade()** (5 connections) — `app/engine/regimeread.py`
- **_as_of()** (3 connections) — `app/engine/regimeread.py`
- **phase_of()** (3 connections) — `app/engine/regimeread.py`
- **phase_side()** (3 connections) — `app/engine/regimeread.py`
- **._bar_closed_by()** (3 connections) — `app/engine/regimeread.py`
- **load()** (3 connections) — `app/engine/regimeread.py`
- **factor_extractors()** (3 connections) — `app/engine/regimeread.py`
- **_tf_seconds()** (2 connections) — `app/engine/regimeread.py`
- **main()** (2 connections) — `app/engine/regimeread.py`
- **.__init__()** (1 connections) — `app/engine/regimeread.py`
- **Regime reading — what the market is doing NOW, not what label it last earned. A** (1 connections) — `app/engine/regimeread.py`
- **Last (confirmed_at, ...) row confirmed at or before ts, or None.     The lookahe** (1 connections) — `app/engine/regimeread.py`
- **The one word. Pure, so a test can pin every branch without a store.** (1 connections) — `app/engine/regimeread.py`
- **UP / DOWN carried by a phase, or None (RANGE, UNKNOWN).** (1 connections) — `app/engine/regimeread.py`
- **One symbol/timeframe, loaded once, read many times as-of any moment.** (1 connections) — `app/engine/regimeread.py`
- **Index of the last candle CLOSED at as_of, or None.** (1 connections) — `app/engine/regimeread.py`
- **Read the four series once. `candles` may be passed by a caller that     already** (1 connections) — `app/engine/regimeread.py`
- **Stamp the reading as-of each setup's confirmed_at onto its payload.      driftfa** (1 connections) — `app/engine/regimeread.py`
- **0/1 flags for outcome_split. Absent when unannotated (MISSING stays honest).** (1 connections) — `app/engine/regimeread.py`
- **Load, annotate, split. Every cell is a fact; no cell is a verdict.** (1 connections) — `app/engine/regimeread.py`

## Relationships

- [Kraken Adapter](Kraken_Adapter.md) (1 shared connections)

## Source Files

- `app/engine/regimeread.py`

## Audit Trail

- EXTRACTED: 65 (97%)
- INFERRED: 2 (3%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*