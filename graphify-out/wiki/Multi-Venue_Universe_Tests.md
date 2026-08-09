# Multi-Venue Universe Tests

> 16 nodes

## Key Concepts

- **MultiVenueUniverseTest** (11 connections) — `app/tests/test_venues.py`
- **.setUp()** (2 connections) — `app/tests/test_venues.py`
- **.test_perp_wins_when_a_coin_trades_on_both()** (2 connections) — `app/tests/test_venues.py`
- **.test_kraken_wins_over_phemex_for_the_same_underlying()** (2 connections) — `app/tests/test_venues.py`
- **.test_shadow_only_leaves_the_traded_universe_untouched()** (2 connections) — `app/tests/test_venues.py`
- **.test_xbt_and_btc_are_one_underlying_not_two()** (2 connections) — `app/tests/test_venues.py`
- **.test_a_kraken_outage_says_the_universe_may_be_inaccessible()** (2 connections) — `app/tests/test_venues.py`
- **.test_base_asset_extraction()** (1 connections) — `app/tests/test_venues.py`
- **.test_perp_ranking_failure_degrades_to_spot_only()** (1 connections) — `app/tests/test_venues.py`
- **.test_perps_can_be_disabled()** (1 connections) — `app/tests/test_venues.py`
- **Merged ranking must never expose the same underlying twice.** (1 connections) — `app/tests/test_venues.py`
- **Not a preference: 0.07% round-trip vs 1.00% flips a 0.1%-stop trade         fro** (1 connections) — `app/tests/test_venues.py`
- **Operator ruling 2026-07-30. This deliberately OVERRIDES volume —         Phemex** (1 connections) — `app/tests/test_venues.py`
- **The bug this separation exists to prevent, pinned.          With Kraken merged** (1 connections) — `app/tests/test_venues.py`
- **Kraken writes Bitcoin as XBT. Without the alias the dedupe sees two         coi** (1 connections) — `app/tests/test_venues.py`
- **Degrading to Phemex-only is not neutral once the operator has ruled         for** (1 connections) — `app/tests/test_venues.py`

## Relationships

- [test_venues.py](test_venues.py.md) (1 shared connections)
- [Universe Coverage Tests](Universe_Coverage_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_venues.py`

## Audit Trail

- EXTRACTED: 31 (97%)
- INFERRED: 1 (3%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*