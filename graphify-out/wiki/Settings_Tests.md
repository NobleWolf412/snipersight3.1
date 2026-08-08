# Settings Tests

> 28 nodes

## Key Concepts

- **SettingsCase** (14 connections) — `app/tests/test_settings.py`
- **._baselines()** (5 connections) — `app/tests/test_settings.py`
- **DrawdownHaltTest** (5 connections) — `app/tests/test_settings.py`
- **test_settings.py** (4 connections) — `app/tests/test_settings.py`
- **DrawdownGuardTest** (4 connections) — `app/tests/test_settings.py`
- **.test_behavioural_change_starts_a_new_baseline()** (3 connections) — `app/tests/test_settings.py`
- **.test_halt_is_operational_and_must_not_reset_the_baseline()** (3 connections) — `app/tests/test_settings.py`
- **.test_halt_and_resume_are_both_audited()** (2 connections) — `app/tests/test_settings.py`
- **.test_no_op_change_is_not_logged()** (2 connections) — `app/tests/test_settings.py`
- **.test_drawdown_limit_is_operational_not_behavioural()** (2 connections) — `app/tests/test_settings.py`
- **.setUp()** (1 connections) — `app/tests/test_settings.py`
- **.tearDown()** (1 connections) — `app/tests/test_settings.py`
- **.test_defaults_when_nothing_set()** (1 connections) — `app/tests/test_settings.py`
- **.test_change_is_persisted_and_logged()** (1 connections) — `app/tests/test_settings.py`
- **.test_unknown_setting_is_refused()** (1 connections) — `app/tests/test_settings.py`
- **.test_bool_coercion_from_json_and_strings()** (1 connections) — `app/tests/test_settings.py`
- **.test_corrupt_row_falls_back_to_default_rather_than_crashing()** (1 connections) — `app/tests/test_settings.py`
- **.test_every_setting_is_classified()** (1 connections) — `app/tests/test_settings.py`
- **.test_drawdown_default_is_a_real_limit()** (1 connections) — `app/tests/test_settings.py`
- **.setUp()** (1 connections) — `app/tests/test_settings.py`
- **.tearDown()** (1 connections) — `app/tests/test_settings.py`
- **.test_halt_trips_and_blocks_later_entries()** (1 connections) — `app/tests/test_settings.py`
- **Operator settings: audited, correctly classed, and honest about baselines.** (1 connections) — `app/tests/test_settings.py`
- **A record spanning two configs cannot say which produced which result.** (1 connections) — `app/tests/test_settings.py`
- **Halting is how the operator stays safe. If it destroyed the forward         rec** (1 connections) — `app/tests/test_settings.py`
- *... and 3 more nodes in this community*

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_settings.py`

## Audit Trail

- EXTRACTED: 62 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*