# History Ingest & Repair

> 17 nodes

## Key Concepts

- **ingest.py** (9 connections) — `app/engine/ingest.py`
- **history_floor()** (5 connections) — `app/engine/ingest.py`
- **missing_history()** (5 connections) — `app/engine/ingest.py`
- **repair_history()** (5 connections) — `app/engine/ingest.py`
- **backfill_history()** (4 connections) — `app/engine/ingest.py`
- **onboard()** (4 connections) — `app/engine/ingest.py`
- **_native_first()** (3 connections) — `app/engine/ingest.py`
- **run_engines()** (3 connections) — `app/engine/ingest.py`
- **_native_count()** (2 connections) — `app/engine/ingest.py`
- **Per-symbol onboarding — backfill history, aggregate, run all fact engines.  Used** (1 connections) — `app/engine/ingest.py`
- **Earliest timestamp worth requesting for a symbol with NO candles yet.      Exist** (1 connections) — `app/engine/ingest.py`
- **Earliest NATIVE candle for a symbol, optionally within one timeframe.      `sour** (1 connections) — `app/engine/ingest.py`
- **Native timeframes whose stored history starts LATER than their floor.      The h** (1 connections) — `app/engine/ingest.py`
- **Re-request the floor window for timeframes onboarding left short.      Targeted** (1 connections) — `app/engine/ingest.py`
- **Import native candles + build aggregates for one symbol.      The per-timeframe** (1 connections) — `app/engine/ingest.py`
- **Run every per-symbol fact engine across all timeframes.      The loop itself liv** (1 connections) — `app/engine/ingest.py`
- **Full onboarding for a new symbol: history + engines.** (1 connections) — `app/engine/ingest.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/engine/ingest.py`

## Audit Trail

- EXTRACTED: 48 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*