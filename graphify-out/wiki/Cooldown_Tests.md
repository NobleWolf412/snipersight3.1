# Cooldown Tests

> 37 nodes

## Key Concepts

- **PointInTime** (8 connections) — `app/tests/test_cooldowns.py`
- **Derivation** (8 connections) — `app/tests/test_cooldowns.py`
- **test_cooldowns.py** (6 connections) — `app/tests/test_cooldowns.py`
- **._exec()** (5 connections) — `app/tests/test_cooldowns.py`
- **Durations** (4 connections) — `app/tests/test_cooldowns.py`
- **RiskIntegration** (4 connections) — `app/tests/test_cooldowns.py`
- **Scope** (3 connections) — `app/tests/test_cooldowns.py`
- **.test_a_missed_order_creates_no_cooldown()** (3 connections) — `app/tests/test_cooldowns.py`
- **.test_the_cooldown_starts_at_the_EXIT_not_at_run_time()** (3 connections) — `app/tests/test_cooldowns.py`
- **.test_a_stop_out_locks_out_far_longer_than_a_target()** (2 connections) — `app/tests/test_cooldowns.py`
- **.test_lockout_scales_with_horizon()** (2 connections) — `app/tests/test_cooldowns.py`
- **.test_long_and_short_cool_down_independently()** (2 connections) — `app/tests/test_cooldowns.py`
- **.test_not_blocked_before_the_exit_that_caused_it()** (2 connections) — `app/tests/test_cooldowns.py`
- **.test_the_longest_overlapping_lockout_wins()** (2 connections) — `app/tests/test_cooldowns.py`
- **.test_the_blocking_fact_is_returned_not_a_bare_boolean()** (2 connections) — `app/tests/test_cooldowns.py`
- **.test_cooldowns_are_derived_from_exits_not_held_as_live_state()** (2 connections) — `app/tests/test_cooldowns.py`
- **.test_rerunning_writes_zero_new_facts()** (2 connections) — `app/tests/test_cooldowns.py`
- **.test_trail_and_time_exits_count_as_resolved_not_invalidated()** (1 connections) — `app/tests/test_cooldowns.py`
- **.test_a_cooldown_does_not_leak_across_symbols()** (1 connections) — `app/tests/test_cooldowns.py`
- **.setUp()** (1 connections) — `app/tests/test_cooldowns.py`
- **.test_blocked_inside_the_window()** (1 connections) — `app/tests/test_cooldowns.py`
- **.test_not_blocked_after_expiry()** (1 connections) — `app/tests/test_cooldowns.py`
- **.setUp()** (1 connections) — `app/tests/test_cooldowns.py`
- **.tearDown()** (1 connections) — `app/tests/test_cooldowns.py`
- **.setUp()** (1 connections) — `app/tests/test_cooldowns.py`
- *... and 12 more nodes in this community*

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_cooldowns.py`

## Audit Trail

- EXTRACTED: 80 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*