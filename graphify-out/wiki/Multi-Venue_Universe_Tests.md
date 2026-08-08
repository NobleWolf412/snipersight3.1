# Multi-Venue Universe Tests

> 20 nodes

## Key Concepts

- **RuntimeError** (13 connections)
- **MultiVenueUniverseTest** (11 connections) — `app/tests/test_venues.py`
- **.test_onboarding_still_raises_on_a_blocked_symbol()** (3 connections) — `app/tests/test_pipeline_gates.py`
- **.test_a_kraken_outage_says_the_universe_may_be_inaccessible()** (3 connections) — `app/tests/test_venues.py`
- **.test_the_scope_survives_an_engine_raising()** (2 connections) — `app/tests/test_candle_cache.py`
- **.setUp()** (2 connections) — `app/tests/test_venues.py`
- **.test_perp_wins_when_a_coin_trades_on_both()** (2 connections) — `app/tests/test_venues.py`
- **.test_kraken_wins_over_phemex_for_the_same_underlying()** (2 connections) — `app/tests/test_venues.py`
- **.test_shadow_only_leaves_the_traded_universe_untouched()** (2 connections) — `app/tests/test_venues.py`
- **.test_xbt_and_btc_are_one_underlying_not_two()** (2 connections) — `app/tests/test_venues.py`
- **.test_perp_ranking_failure_degrades_to_spot_only()** (2 connections) — `app/tests/test_venues.py`
- **The loop is shared; the POLICY is not. Onboarding a symbol whose         market** (1 connections) — `app/tests/test_pipeline_gates.py`
- **.test_base_asset_extraction()** (1 connections) — `app/tests/test_venues.py`
- **.test_perps_can_be_disabled()** (1 connections) — `app/tests/test_venues.py`
- **Merged ranking must never expose the same underlying twice.** (1 connections) — `app/tests/test_venues.py`
- **Not a preference: 0.07% round-trip vs 1.00% flips a 0.1%-stop trade         fro** (1 connections) — `app/tests/test_venues.py`
- **Operator ruling 2026-07-30. This deliberately OVERRIDES volume —         Phemex** (1 connections) — `app/tests/test_venues.py`
- **The bug this separation exists to prevent, pinned.          With Kraken merged** (1 connections) — `app/tests/test_venues.py`
- **Kraken writes Bitcoin as XBT. Without the alias the dedupe sees two         coi** (1 connections) — `app/tests/test_venues.py`
- **Degrading to Phemex-only is not neutral once the operator has ruled         for** (1 connections) — `app/tests/test_venues.py`

## Relationships

- [Pipeline Gate Tests](Pipeline_Gate_Tests.md) (3 shared connections)
- [Copilot Pack Builder](Copilot_Pack_Builder.md) (1 shared connections)
- [History Ingest & Repair](History_Ingest_%26_Repair.md) (1 shared connections)
- [Data Quality Engine](Data_Quality_Engine.md) (1 shared connections)
- [Store Snapshots](Store_Snapshots.md) (1 shared connections)
- [Notification Tests](Notification_Tests.md) (1 shared connections)
- [Retired Symbol Staleness Tests](Retired_Symbol_Staleness_Tests.md) (1 shared connections)
- [Watchdog Audit Cadence Tests](Watchdog_Audit_Cadence_Tests.md) (1 shared connections)
- [Candle Cache Tests](Candle_Cache_Tests.md) (1 shared connections)
- [Venue Resolution Tests](Venue_Resolution_Tests.md) (1 shared connections)
- [Universe Coverage Tests](Universe_Coverage_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_candle_cache.py`
- `app/tests/test_pipeline_gates.py`
- `app/tests/test_venues.py`

## Audit Trail

- EXTRACTED: 36 (68%)
- INFERRED: 17 (32%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*