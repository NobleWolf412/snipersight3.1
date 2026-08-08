# Kraken Window Walk Tests

> 27 nodes

## Key Concepts

- **test_kraken_walk.py** (7 connections) — `app/tests/test_kraken_walk.py`
- **_dense()** (7 connections) — `app/tests/test_kraken_walk.py`
- **WalkCoversTheWholeSpan** (6 connections) — `app/tests/test_kraken_walk.py`
- **WalkStillTerminates** (6 connections) — `app/tests/test_kraken_walk.py`
- **_window()** (3 connections) — `app/tests/test_kraken_walk.py`
- **.test_a_multi_window_span_is_walked_to_the_end()** (3 connections) — `app/tests/test_kraken_walk.py`
- **.test_coverage_does_not_degrade_as_the_span_grows()** (3 connections) — `app/tests/test_kraken_walk.py`
- **.test_a_healthy_walk_says_nothing()** (3 connections) — `app/tests/test_kraken_walk.py`
- **RealFloorsFitTheBudget** (3 connections) — `app/tests/test_kraken_walk.py`
- **_bar()** (2 connections) — `app/tests/test_kraken_walk.py`
- **.test_a_gap_before_listing_is_skipped_not_read_as_the_end()** (2 connections) — `app/tests/test_kraken_walk.py`
- **.test_exhausting_the_budget_is_loud()** (2 connections) — `app/tests/test_kraken_walk.py`
- **.setUp()** (1 connections) — `app/tests/test_kraken_walk.py`
- **.test_it_issues_at_least_one_request_per_window()** (1 connections) — `app/tests/test_kraken_walk.py`
- **.setUp()** (1 connections) — `app/tests/test_kraken_walk.py`
- **.test_a_venue_that_never_advances_stops()** (1 connections) — `app/tests/test_kraken_walk.py`
- **.test_every_history_floor_needs_one_window()** (1 connections) — `app/tests/test_kraken_walk.py`
- **The Kraken candle walk must cover the whole span, or say that it did not.  `fetc** (1 connections) — `app/tests/test_kraken_walk.py`
- **The [from, to) the walk asked for, bucket-aligned.** (1 connections) — `app/tests/test_kraken_walk.py`
- **Every bucket in the requested window — a fully listed contract.** (1 connections) — `app/tests/test_kraken_walk.py`
- **The regression. Ten windows in, ten windows walked — the old guard         allow** (1 connections) — `app/tests/test_kraken_walk.py`
- **The old guard's signature, stated directly: the longer the span, the         lar** (1 connections) — `app/tests/test_kraken_walk.py`
- **A contract listed mid-span must still be found. An empty window means         'n** (1 connections) — `app/tests/test_kraken_walk.py`
- **Fixing the truncation must not reintroduce the spin it was guarding.** (1 connections) — `app/tests/test_kraken_walk.py`
- **The backstop firing means the returned span is PARTIAL. Saying so is         the** (1 connections) — `app/tests/test_kraken_walk.py`
- *... and 2 more nodes in this community*

## Relationships

- No strong cross-community connections detected

## Source Files

- `app/tests/test_kraken_walk.py`

## Audit Trail

- EXTRACTED: 56 (90%)
- INFERRED: 6 (10%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*