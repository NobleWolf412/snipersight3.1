# Universe & Rate Limiting

> 36 nodes

## Key Concepts

- **get_logger()** (23 connections) — `app/engine/runlog.py`
- **universe.py** (19 connections) — `app/engine/universe.py`
- **rank_by_volume()** (7 connections) — `app/engine/universe.py`
- **refresh()** (7 connections) — `app/engine/universe.py`
- **rank_all_venues()** (6 connections) — `app/engine/universe.py`
- **aggregator.py** (5 connections) — `app/engine/aggregator.py`
- **_RateLimiter** (5 connections) — `app/engine/universe.py`
- **shadow_candidates()** (5 connections) — `app/engine/universe.py`
- **_AuditFilter** (4 connections) — `app/engine/runlog.py`
- **_get()** (4 connections) — `app/engine/universe.py`
- **_base_asset()** (4 connections) — `app/engine/universe.py`
- **scan_symbols()** (4 connections) — `app/engine/universe.py`
- **aggregate()** (3 connections) — `app/engine/aggregator.py`
- **current_symbols()** (3 connections) — `app/engine/universe.py`
- **shadow_symbols()** (3 connections) — `app/engine/universe.py`
- **_bucket_start()** (2 connections) — `app/engine/aggregator.py`
- **_is_stable()** (2 connections) — `app/engine/universe.py`
- **.acquire()** (2 connections) — `app/engine/universe.py`
- **admitted_at()** (2 connections) — `app/engine/universe.py`
- **Canonical higher-timeframe candle aggregator (§19).  4H is built from 1H (UTC-al** (1 connections) — `app/engine/aggregator.py`
- **.filter()** (1 connections) — `app/engine/runlog.py`
- **Logger** (1 connections)
- **WARNING and above, plus operator write actions. Nothing else.** (1 connections) — `app/engine/runlog.py`
- **.__init__()** (1 connections) — `app/engine/universe.py`
- **Dynamic universe selection — top Coinbase USD pairs by live 24h volume.  Recon** (1 connections) — `app/engine/universe.py`
- *... and 11 more nodes in this community*

## Relationships

- [Onboarding Path Tests](Onboarding_Path_Tests.md) (7 shared connections)
- [Chart Vendor Marker Rendering](Chart_Vendor_Marker_Rendering.md) (4 shared connections)
- [binance.py](binance.py.md) (2 shared connections)
- [Scale-Out Settlement Tests](Scale-Out_Settlement_Tests.md) (2 shared connections)
- [_facts](_facts.md) (2 shared connections)
- [Chart Vendor Data Layer](Chart_Vendor_Data_Layer.md) (2 shared connections)
- [A/B Test Engine](A-B_Test_Engine.md) (2 shared connections)
- [volume.py](volume.py.md) (1 shared connections)
- [test_abtest.py](test_abtest.py.md) (1 shared connections)

## Source Files

- `app/engine/aggregator.py`
- `app/engine/runlog.py`
- `app/engine/universe.py`

## Audit Trail

- EXTRACTED: 124 (98%)
- INFERRED: 3 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*