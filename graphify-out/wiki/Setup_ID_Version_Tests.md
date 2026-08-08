# Setup ID Version Tests

> 34 nodes

## Key Concepts

- **OverrideOutlivesTheVersion** (10 connections) — `app/tests/test_override_survives_version_bump.py`
- **SetupZoneKey** (7 connections) — `app/tests/test_override_survives_version_bump.py`
- **._portfolio()** (6 connections) — `app/tests/test_override_survives_version_bump.py`
- **test_override_survives_version_bump.py** (5 connections) — `app/tests/test_override_survives_version_bump.py`
- **._store()** (4 connections) — `app/tests/test_override_survives_version_bump.py`
- **TheReadSetCannotStrandTheBook** (4 connections) — `app/tests/test_override_survives_version_bump.py`
- **.test_without_an_override_the_position_is_reported()** (3 connections) — `app/tests/test_override_survives_version_bump.py`
- **.test_an_override_under_an_older_version_still_suppresses()** (3 connections) — `app/tests/test_override_survives_version_bump.py`
- **.test_the_close_is_still_reported_with_the_id_it_was_written_under()** (3 connections) — `app/tests/test_override_survives_version_bump.py`
- **.test_the_same_version_case_still_works()** (3 connections) — `app/tests/test_override_survives_version_bump.py`
- **.test_an_override_on_a_different_zone_suppresses_nothing()** (3 connections) — `app/tests/test_override_survives_version_bump.py`
- **.test_two_closes_on_one_zone_are_both_reported()** (3 connections) — `app/tests/test_override_survives_version_bump.py`
- **.test_two_generations_of_one_zone_agree_on_the_key()** (2 connections) — `app/tests/test_override_survives_version_bump.py`
- **.test_every_engine_that_mints_a_setup_id_is_covered()** (2 connections) — `app/tests/test_override_survives_version_bump.py`
- **.test_an_id_with_no_version_is_left_exactly_as_it_is()** (2 connections) — `app/tests/test_override_survives_version_bump.py`
- **.test_a_trailing_component_that_is_not_a_version_is_not_eaten()** (2 connections) — `app/tests/test_override_survives_version_bump.py`
- **.test_the_suppression_set_comes_from_the_reported_map()** (2 connections) — `app/tests/test_override_survives_version_bump.py`
- **.test_the_engine_version_is_stripped_and_the_zone_survives()** (1 connections) — `app/tests/test_override_survives_version_bump.py`
- **.test_overrides_are_read_under_every_manual_version_ever_written()** (1 connections) — `app/tests/test_override_survives_version_bump.py`
- **An operator's close must outlive the engine version it was written under.  THE** (1 connections) — `app/tests/test_override_survives_version_bump.py`
- **The stripping rule itself. Cheap to state, expensive to get wrong.** (1 connections) — `app/tests/test_override_survives_version_bump.py`
- **The property in one line — this is the whole fix.** (1 connections) — `app/tests/test_override_survives_version_bump.py`
- **setups, breakout and trend all end their ids with their own version         tag** (1 connections) — `app/tests/test_override_survives_version_bump.py`
- **Ids minted before the version was added have no tail to strip         (setups.p** (1 connections) — `app/tests/test_override_survives_version_bump.py`
- **Blind rpartition would swallow the zone timestamp on a legacy id and         me** (1 connections) — `app/tests/test_override_survives_version_bump.py`
- *... and 9 more nodes in this community*

## Relationships

- [API Server Endpoints](API_Server_Endpoints.md) (1 shared connections)

## Source Files

- `app/tests/test_override_survives_version_bump.py`

## Audit Trail

- EXTRACTED: 81 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*