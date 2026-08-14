# Universe Coverage Tests

> 13 nodes

## Key Concepts

- **.universe()** (18 connections) — `app/tests/test_weather.py`
- **CoverageGateTest** (10 connections) — `app/tests/test_universe_coverage.py`
- **._snapshots()** (4 connections) — `app/tests/test_universe_coverage.py`
- **.test_full_coverage_records_a_snapshot()** (3 connections) — `app/tests/test_universe_coverage.py`
- **.test_partial_coverage_refuses_to_overwrite()** (3 connections) — `app/tests/test_universe_coverage.py`
- **.test_injected_rankings_bypass_the_gate()** (3 connections) — `app/tests/test_universe_coverage.py`
- **.test_response_names_the_engine_versions_that_produced_it()** (3 connections) — `app/tests/test_weather.py`
- **.test_boundary_just_above_floor_is_accepted()** (2 connections) — `app/tests/test_universe_coverage.py`
- **.test_boundary_just_below_floor_is_refused()** (2 connections) — `app/tests/test_universe_coverage.py`
- **.setUp()** (1 connections) — `app/tests/test_universe_coverage.py`
- **.tearDown()** (1 connections) — `app/tests/test_universe_coverage.py`
- **The core fix: a partial ranking must NEVER overwrite a good universe.** (1 connections) — `app/tests/test_universe_coverage.py`
- **Tests and replays inject a ranking directly; it is complete by         construc** (1 connections) — `app/tests/test_universe_coverage.py`

## Relationships

- [Weather Row Accounting Tests](Weather_Row_Accounting_Tests.md) (8 shared connections)
- [Shadow Classification Tests](Shadow_Classification_Tests.md) (2 shared connections)
- [Regime Wording Tests](Regime_Wording_Tests.md) (2 shared connections)
- [Rate Limiter & Retry Tests](Rate_Limiter_%26_Retry_Tests.md) (1 shared connections)
- [Multi-Venue Universe Tests](Multi-Venue_Universe_Tests.md) (1 shared connections)
- [Weather Endpoint Tests](Weather_Endpoint_Tests.md) (1 shared connections)
- [TestEveryRowIsAccountedFor](TestEveryRowIsAccountedFor.md) (1 shared connections)

## Source Files

- `app/tests/test_universe_coverage.py`
- `app/tests/test_weather.py`

## Audit Trail

- EXTRACTED: 41 (79%)
- INFERRED: 11 (21%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*