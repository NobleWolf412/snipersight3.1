# Health Scope Tests

> 16 nodes

## Key Concepts

- **HealthScopeCase** (10 connections) — `app/tests/test_health_scope.py`
- **._health()** (8 connections) — `app/tests/test_health_scope.py`
- **.test_a_stale_maintained_series_still_degrades()** (3 connections) — `app/tests/test_health_scope.py`
- **.test_stale_series_is_actionable_only()** (3 connections) — `app/tests/test_health_scope.py`
- **.test_nothing_is_hidden()** (3 connections) — `app/tests/test_health_scope.py`
- **test_health_scope.py** (2 connections) — `app/tests/test_health_scope.py`
- **.test_stale_unmaintained_series_do_not_degrade_the_status()** (2 connections) — `app/tests/test_health_scope.py`
- **.test_every_series_says_whether_it_is_maintained()** (2 connections) — `app/tests/test_health_scope.py`
- **.test_a_clean_store_with_no_history_reads_ok()** (2 connections) — `app/tests/test_health_scope.py`
- **.setUp()** (1 connections) — `app/tests/test_health_scope.py`
- **.tearDown()** (1 connections) — `app/tests/test_health_scope.py`
- **Health is about the data the app undertook to keep current.  `/api/health` compu** (1 connections) — `app/tests/test_health_scope.py`
- **Run the endpoint against a fabricated store.** (1 connections) — `app/tests/test_health_scope.py`
- **The case that means something is not weakened.** (1 connections) — `app/tests/test_health_scope.py`
- **The wizard turns this list into "run a scan". Everything in it must         be a** (1 connections) — `app/tests/test_health_scope.py`
- **Rescoping must not mean silently dropping the count.** (1 connections) — `app/tests/test_health_scope.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_health_scope.py`

## Audit Trail

- EXTRACTED: 42 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*