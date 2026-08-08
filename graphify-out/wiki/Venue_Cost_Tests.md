# Venue Cost Tests

> 45 nodes

## Key Concepts

- **ExecSimVenueCostTest** (10 connections) — `app/tests/test_venue_costs.py`
- **test_venue_costs.py** (8 connections) — `app/tests/test_venue_costs.py`
- **._run_perp_trade()** (8 connections) — `app/tests/test_venue_costs.py`
- **ProfileResolutionTest** (6 connections) — `app/tests/test_venue_costs.py`
- **TempStore** (5 connections) — `app/tests/test_venue_costs.py`
- **ImmutabilityTest** (5 connections) — `app/tests/test_venue_costs.py`
- **EconomicGateTest** (5 connections) — `app/tests/test_venue_costs.py`
- **AppendOnlyVersionTest** (5 connections) — `app/tests/test_venue_costs.py`
- **candle()** (3 connections) — `app/tests/test_venue_costs.py`
- **.test_spot_trade_still_charged_coinbase_rates()** (3 connections) — `app/tests/test_venue_costs.py`
- **.test_execution_manifest_is_symbol_invariant()** (3 connections) — `app/tests/test_venue_costs.py`
- **.test_profile_matches_the_venue_it_claims_to_price()** (2 connections) — `app/tests/test_venue_costs.py`
- **.test_unknown_symbol_raises_rather_than_charging_a_default()** (2 connections) — `app/tests/test_venue_costs.py`
- **.test_coinbase_profile_hash_is_unchanged()** (2 connections) — `app/tests/test_venue_costs.py`
- **.test_drift_between_profile_and_venue_is_caught()** (2 connections) — `app/tests/test_venue_costs.py`
- **.test_round_trip_cost_requires_an_explicit_profile()** (2 connections) — `app/tests/test_venue_costs.py`
- **.test_setup_economic_on_its_own_venue_was_rejected_on_coinbase_costs()** (2 connections) — `app/tests/test_venue_costs.py`
- **.test_setups_no_longer_exports_a_global_profile()** (2 connections) — `app/tests/test_venue_costs.py`
- **.test_perp_trade_is_charged_phemex_rates()** (2 connections) — `app/tests/test_venue_costs.py`
- **.test_perp_fee_is_far_below_what_the_old_global_charged()** (2 connections) — `app/tests/test_venue_costs.py`
- **.test_fields_edgestats_depends_on_survive()** (2 connections) — `app/tests/test_venue_costs.py`
- **.test_each_venue_records_its_own_cost_manifest()** (2 connections) — `app/tests/test_venue_costs.py`
- **.test_exec_version_bumped_away_from_the_overcharged_book()** (2 connections) — `app/tests/test_venue_costs.py`
- **.test_old_facts_are_not_rewritten_by_a_new_run()** (2 connections) — `app/tests/test_venue_costs.py`
- **.setUp()** (1 connections) — `app/tests/test_venue_costs.py`
- *... and 20 more nodes in this community*

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_venue_costs.py`

## Audit Trail

- EXTRACTED: 108 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*