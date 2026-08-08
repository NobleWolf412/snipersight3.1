# Universe & Rate Limiting

> 27 nodes

## Key Concepts

- **get_logger()** (26 connections) — `app/engine/runlog.py`
- **universe.py** (19 connections) — `app/engine/universe.py`
- **rank_by_volume()** (7 connections) — `app/engine/universe.py`
- **refresh()** (7 connections) — `app/engine/universe.py`
- **rank_all_venues()** (6 connections) — `app/engine/universe.py`
- **_RateLimiter** (5 connections) — `app/engine/universe.py`
- **shadow_candidates()** (5 connections) — `app/engine/universe.py`
- **_get()** (4 connections) — `app/engine/universe.py`
- **_base_asset()** (4 connections) — `app/engine/universe.py`
- **scan_symbols()** (4 connections) — `app/engine/universe.py`
- **current_symbols()** (3 connections) — `app/engine/universe.py`
- **shadow_symbols()** (3 connections) — `app/engine/universe.py`
- **_is_stable()** (2 connections) — `app/engine/universe.py`
- **.acquire()** (2 connections) — `app/engine/universe.py`
- **Logger** (1 connections)
- **.__init__()** (1 connections) — `app/engine/universe.py`
- **Dynamic universe selection — top Coinbase USD pairs by live 24h volume.  Recon** (1 connections) — `app/engine/universe.py`
- **Thread-safe minimum spacing between requests, shared by all rank workers.** (1 connections) — `app/engine/universe.py`
- **Throttled GET with backoff on rate limits and transient server errors.      Re** (1 connections) — `app/engine/universe.py`
- **Live: all online USD spot pairs, ranked by 24h USD volume. Fail-soft.      `pr** (1 connections) — `app/engine/universe.py`
- **The underlying, so the same coin on two venues is one candidate.** (1 connections) — `app/engine/universe.py`
- **Merged ranking across enabled venues, deduped by underlying asset.      Where** (1 connections) — `app/engine/universe.py`
- **Kraken perps carried for DATA ONLY, alongside the traded universe.      Delibe** (1 connections) — `app/engine/universe.py`
- **Admitted + warm symbols from the latest universe fact. Falls back to     whatev** (1 connections) — `app/engine/universe.py`
- **Symbols carried for data only — imported and derived, never traded.** (1 connections) — `app/engine/universe.py`
- *... and 2 more nodes in this community*

## Relationships

- [Execution Simulator & Risk](Execution_Simulator_%26_Risk.md) (6 shared connections)
- [Bias, Trend & Setups](Bias%2C_Trend_%26_Setups.md) (6 shared connections)
- [Portfolio & Position Endpoints](Portfolio_%26_Position_Endpoints.md) (3 shared connections)
- [API Server Endpoints](API_Server_Endpoints.md) (3 shared connections)
- [Market Data Importer](Market_Data_Importer.md) (2 shared connections)
- [Kraken Adapter](Kraken_Adapter.md) (2 shared connections)
- [Manual Trading Engine](Manual_Trading_Engine.md) (2 shared connections)
- [Live Scanner Loop](Live_Scanner_Loop.md) (1 shared connections)
- [Fact Query & Scan Endpoints](Fact_Query_%26_Scan_Endpoints.md) (1 shared connections)
- [A/B Calibration Tests](A-B_Calibration_Tests.md) (1 shared connections)
- [Simulator Convention Tests](Simulator_Convention_Tests.md) (1 shared connections)

## Source Files

- `app/engine/runlog.py`
- `app/engine/universe.py`

## Audit Trail

- EXTRACTED: 101 (92%)
- INFERRED: 9 (8%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*