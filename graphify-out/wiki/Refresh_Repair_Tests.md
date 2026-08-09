# Refresh Repair Tests

> 7 nodes

## Key Concepts

- **RefreshUniverseRepairs** (6 connections) — `app/tests/test_cold_start.py`
- **._run_with()** (3 connections) — `app/tests/test_cold_start.py`
- **.test_an_unavailable_ranking_does_not_disable_the_repair()** (3 connections) — `app/tests/test_cold_start.py`
- **.setUp()** (2 connections) — `app/tests/test_cold_start.py`
- **.test_a_normal_refresh_runs_the_repair_pass()** (2 connections) — `app/tests/test_cold_start.py`
- **The repair only ever fires from the hourly refresh, so these pin that it     is** (1 connections) — `app/tests/test_cold_start.py`
- **The early return used to skip everything below it. A hole in the         candle** (1 connections) — `app/tests/test_cold_start.py`

## Relationships

- [Cold Start Live Loop Tests](Cold_Start_Live_Loop_Tests.md) (1 shared connections)
- [_facts](_facts.md) (1 shared connections)

## Source Files

- `app/tests/test_cold_start.py`

## Audit Trail

- EXTRACTED: 17 (94%)
- INFERRED: 1 (6%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*