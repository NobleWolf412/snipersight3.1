# Strategy Registry Tests

> 21 nodes

## Key Concepts

- **Shape** (6 connections) — `app/tests/test_registry.py`
- **MatchesTheEngine** (5 connections) — `app/tests/test_registry.py`
- **test_registry.py** (4 connections) — `app/tests/test_registry.py`
- **MatchesSettings** (3 connections) — `app/tests/test_registry.py`
- **.test_declared_regimes_are_regimes_the_engine_admits()** (2 connections) — `app/tests/test_registry.py`
- **.test_reversal_is_marked_as_needing_extra_evidence()** (2 connections) — `app/tests/test_registry.py`
- **.test_every_live_strategy_maps_to_a_real_behavioural_switch()** (2 connections) — `app/tests/test_registry.py`
- **.test_enabled_strategies_and_the_registry_agree()** (2 connections) — `app/tests/test_registry.py`
- **.test_every_horizon_is_one_the_cooldown_policy_knows()** (2 connections) — `app/tests/test_registry.py`
- **.test_every_live_strategy_is_one_playbook_actually_returns()** (1 connections) — `app/tests/test_registry.py`
- **.test_pullback_needs_no_extra_evidence()** (1 connections) — `app/tests/test_registry.py`
- **.test_planned_strategies_carry_a_measured_gap_and_no_record()** (1 connections) — `app/tests/test_registry.py`
- **.test_keys_are_unique_and_slug_shaped()** (1 connections) — `app/tests/test_registry.py`
- **.test_every_strategy_declares_the_public_evidence_contract()** (1 connections) — `app/tests/test_registry.py`
- **.test_lookup_by_engine_name_is_case_insensitive_and_total()** (1 connections) — `app/tests/test_registry.py`
- **The registry must describe the engine, not an intention.  Its whole reason to ex** (1 connections) — `app/tests/test_registry.py`
- **A registry naming a regime the playbook refuses would put a strategy         on** (1 connections) — `app/tests/test_registry.py`
- **The engine gates TRANSITION on composed evidence. If that ever stops         bei** (1 connections) — `app/tests/test_registry.py`
- **A toggle writing a setting `settings.py` has never heard of would 400         on** (1 connections) — `app/tests/test_registry.py`
- **`setups.enabled_strategies` reads the switches; the registry names         them.** (1 connections) — `app/tests/test_registry.py`
- **A horizon is a hold-time and cooldown policy. One the cooldown tables         do** (1 connections) — `app/tests/test_registry.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_registry.py`

## Audit Trail

- EXTRACTED: 40 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*