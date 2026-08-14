# Boundary Wake Grid Tests

> 12 nodes

## Key Concepts

- **test_boundary_wake.py** (5 connections) — `app/tests/test_boundary_wake.py`
- **GridCoversEveryBoundary** (4 connections) — `app/tests/test_boundary_wake.py`
- **TheLoopWearsIt** (3 connections) — `app/tests/test_boundary_wake.py`
- **.test_daily_and_weekly_edges_sit_on_the_grid()** (2 connections) — `app/tests/test_boundary_wake.py`
- **.test_main_sleeps_through_next_wake()** (2 connections) — `app/tests/test_boundary_wake.py`
- **.test_the_pass_logs_its_boundary_lag()** (2 connections) — `app/tests/test_boundary_wake.py`
- **.test_every_tracked_granularity_sits_on_the_grid()** (1 connections) — `app/tests/test_boundary_wake.py`
- **Wakes land just past candle boundaries, and never starve the heartbeat.  The s** (1 connections) — `app/tests/test_boundary_wake.py`
- **The claim that lets ONE grid serve every timeframe, pinned as fact.** (1 connections) — `app/tests/test_boundary_wake.py`
- **Midnight UTC and Monday 00:00 UTC are epoch multiples of 900s, so         the c** (1 connections) — `app/tests/test_boundary_wake.py`
- **The nap must be COMPUTED, never a constant.          This asserted the literal** (1 connections) — `app/tests/test_boundary_wake.py`
- **The buffer is a modelled constant until production logs argue         otherwise** (1 connections) — `app/tests/test_boundary_wake.py`

## Relationships

- [Live Scanner Loop](Live_Scanner_Loop.md) (1 shared connections)
- [yn](yn.md) (1 shared connections)

## Source Files

- `app/tests/test_boundary_wake.py`

## Audit Trail

- EXTRACTED: 24 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*