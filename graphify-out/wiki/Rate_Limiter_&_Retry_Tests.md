# Rate Limiter & Retry Tests

> 14 nodes

## Key Concepts

- **test_universe_coverage.py** (6 connections) — `app/tests/test_universe_coverage.py`
- **RetryTest** (4 connections) — `app/tests/test_universe_coverage.py`
- **RateLimiterTest** (3 connections) — `app/tests/test_universe_coverage.py`
- **.test_spacing_is_global_not_per_thread()** (2 connections) — `app/tests/test_universe_coverage.py`
- **VersionTest** (2 connections) — `app/tests/test_universe_coverage.py`
- **.test_version_bumped_past_the_broken_ranking()** (2 connections) — `app/tests/test_universe_coverage.py`
- **_http_error()** (1 connections) — `app/tests/test_universe_coverage.py`
- **.test_concurrent_workers_are_serialised()** (1 connections) — `app/tests/test_universe_coverage.py`
- **.test_429_is_retried_then_succeeds()** (1 connections) — `app/tests/test_universe_coverage.py`
- **.test_404_is_not_retried()** (1 connections) — `app/tests/test_universe_coverage.py`
- **.test_gives_up_after_the_configured_retries()** (1 connections) — `app/tests/test_universe_coverage.py`
- **Universe ranking must be complete, throttled, and fail closed.  Regression cov** (1 connections) — `app/tests/test_universe_coverage.py`
- **N workers each pausing 1/N s still bursts N requests at once, so the         ga** (1 connections) — `app/tests/test_universe_coverage.py`
- **v0.1 snapshots were built from partial data. They must not be read         as i** (1 connections) — `app/tests/test_universe_coverage.py`

## Relationships

- [Universe Coverage Tests](Universe_Coverage_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_universe_coverage.py`

## Audit Trail

- EXTRACTED: 27 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*