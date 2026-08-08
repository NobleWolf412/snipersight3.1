# Venue Policy & Contract

> 21 nodes

## Key Concepts

- **ValueError** (16 connections)
- **venues.py** (11 connections) — `app/engine/venues.py`
- **venue_for()** (8 connections) — `app/engine/venues.py`
- **Decimal** (6 connections)
- **liquidation_price()** (5 connections) — `app/engine/venues.py`
- **Venue** (4 connections) — `app/engine/venues.py`
- **round_trip_cost_rate()** (4 connections) — `app/engine/venues.py`
- **stop_survives_liquidation()** (4 connections) — `app/engine/venues.py`
- **funding_cost_rate()** (4 connections) — `app/engine/venues.py`
- **validate_policy()** (3 connections) — `app/engine/bias.py`
- **by_key()** (3 connections) — `app/engine/venues.py`
- **max_leverage()** (3 connections) — `app/engine/venues.py`
- **allow_shorts()** (2 connections) — `app/engine/venues.py`
- **Reject a malformed policy at import time rather than at trade time.      Three** (1 connections) — `app/engine/bias.py`
- **.is_perp()** (1 connections) — `app/engine/venues.py`
- **Venue descriptors — the single place that knows what a market ALLOWS.  Before** (1 connections) — `app/engine/venues.py`
- **Which venue this symbol trades on. Raises on anything unrecognised —     guessi** (1 connections) — `app/engine/venues.py`
- **Fee rate paid on notional for one full round trip (maker in, taker out).** (1 connections) — `app/engine/venues.py`
- **Approximate liquidation price for a leveraged perp position, ISOLATED.      `(** (1 connections) — `app/engine/venues.py`
- **Would the stop trigger BEFORE liquidation?      Ported intent from the prior p** (1 connections) — `app/engine/venues.py`
- **Funding paid on notional over a holding period. Zero on spot.      Funding is** (1 connections) — `app/engine/venues.py`

## Relationships

- [Bias Ladder Engine](Bias_Ladder_Engine.md) (2 shared connections)
- [Cost Profiles](Cost_Profiles.md) (2 shared connections)
- [Bias, Trend & Setups](Bias%2C_Trend_%26_Setups.md) (1 shared connections)
- [Credential Vault](Credential_Vault.md) (1 shared connections)
- [Funding Rate Engine](Funding_Rate_Engine.md) (1 shared connections)
- [Market Data Importer](Market_Data_Importer.md) (1 shared connections)
- [Kraken Adapter](Kraken_Adapter.md) (1 shared connections)
- [Manual Trading Engine](Manual_Trading_Engine.md) (1 shared connections)
- [Phemex Adapter](Phemex_Adapter.md) (1 shared connections)
- [Engine Pipeline Runner](Engine_Pipeline_Runner.md) (1 shared connections)
- [Settings Engine](Settings_Engine.md) (1 shared connections)

## Source Files

- `app/engine/bias.py`
- `app/engine/venues.py`

## Audit Trail

- EXTRACTED: 62 (77%)
- INFERRED: 19 (23%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*