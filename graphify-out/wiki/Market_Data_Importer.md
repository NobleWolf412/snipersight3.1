# Market Data Importer

> 10 nodes

## Key Concepts

- **importer.py** (8 connections) — `app/engine/importer.py`
- **backfill()** (6 connections) — `app/engine/importer.py`
- **_fetch_rows()** (4 connections) — `app/engine/importer.py`
- **_fetch()** (3 connections) — `app/engine/importer.py`
- **native_tfs()** (3 connections) — `app/engine/importer.py`
- **_iso()** (2 connections) — `app/engine/importer.py`
- **Market-data importer (public endpoints, no credentials — §16).  Multi-venue si** (1 connections) — `app/engine/importer.py`
- **Timeframes imported directly for THIS symbol.      Phemex *can* serve 4H nativ** (1 connections) — `app/engine/importer.py`
- **Normalised (open_ts, open, high, low, close, volume) for either venue.      Co** (1 connections) — `app/engine/importer.py`
- **Import [start_ts, end_ts) for a native timeframe. Returns import summary.** (1 connections) — `app/engine/importer.py`

## Relationships

- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (2 shared connections)
- [A/B Test Engine](A-B_Test_Engine.md) (1 shared connections)
- [Venue Policy & Contract](Venue_Policy_%26_Contract.md) (1 shared connections)

## Source Files

- `app/engine/importer.py`

## Audit Trail

- EXTRACTED: 29 (97%)
- INFERRED: 1 (3%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*