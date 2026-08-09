# Candle Cache Tests

> 22 nodes

## Key Concepts

- **CacheCase** (14 connections) — `app/tests/test_candle_cache.py`
- **._count_candle_selects()** (5 connections) — `app/tests/test_candle_cache.py`
- **test_candle_cache.py** (3 connections) — `app/tests/test_candle_cache.py`
- **.test_a_ranged_call_bypasses_the_cache()** (3 connections) — `app/tests/test_candle_cache.py`
- **EngineWritesNothing** (3 connections) — `app/tests/test_candle_cache.py`
- **.test_one_select_per_series_inside_the_scope()** (2 connections) — `app/tests/test_candle_cache.py`
- **.test_no_cache_means_todays_behaviour_exactly()** (2 connections) — `app/tests/test_candle_cache.py`
- **.test_the_scope_ends_when_the_walk_ends()** (2 connections) — `app/tests/test_candle_cache.py`
- **.test_every_consumer_idiom_still_works()** (2 connections) — `app/tests/test_candle_cache.py`
- **.test_consumers_get_private_copies()** (2 connections) — `app/tests/test_candle_cache.py`
- **.setUp()** (1 connections) — `app/tests/test_candle_cache.py`
- **.tearDown()** (1 connections) — `app/tests/test_candle_cache.py`
- **.test_cached_and_uncached_reads_are_equal()** (1 connections) — `app/tests/test_candle_cache.py`
- **.test_two_connections_do_not_share_a_cache()** (1 connections) — `app/tests/test_candle_cache.py`
- **.test_the_scope_survives_an_engine_raising()** (1 connections) — `app/tests/test_candle_cache.py`
- **.test_the_walk_runs_inside_the_scope()** (1 connections) — `app/tests/test_candle_cache.py`
- **.test_no_roster_engine_writes_candles()** (1 connections) — `app/tests/test_candle_cache.py`
- **One read per series per walk — and the invariant that makes it safe.  The engine** (1 connections) — `app/tests/test_candle_cache.py`
- **Engines do `[dict(r) for r in rows]` then index by name. Both must         hold** (1 connections) — `app/tests/test_candle_cache.py`
- **The comprehension every engine opens with is also its isolation:         mutatin** (1 connections) — `app/tests/test_candle_cache.py`
- **Only the whole-series form is cached — the only form an engine         uses. A w** (1 connections) — `app/tests/test_candle_cache.py`
- **The invariant the cache's correctness rests on, pinned as source.      A cached** (1 connections) — `app/tests/test_candle_cache.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_candle_cache.py`

## Audit Trail

- EXTRACTED: 50 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*