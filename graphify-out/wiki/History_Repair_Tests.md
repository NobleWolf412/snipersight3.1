# History Repair Tests

> 8 nodes

## Key Concepts

- **RepairHistory** (6 connections) — `app/tests/test_cold_start.py`
- **.test_it_counts_rows_added_not_rows_seen()** (3 connections) — `app/tests/test_cold_start.py`
- **.test_it_asks_from_the_floor_not_from_the_watermark()** (3 connections) — `app/tests/test_cold_start.py`
- **.setUp()** (1 connections) — `app/tests/test_cold_start.py`
- **.tearDown()** (1 connections) — `app/tests/test_cold_start.py`
- **.test_it_reports_what_actually_landed()** (1 connections) — `app/tests/test_cold_start.py`
- **`importer.backfill` re-imports the whole window and REPLACEs what is         alr** (1 connections) — `app/tests/test_cold_start.py`
- **The whole point: resuming from the watermark is what left the hole.** (1 connections) — `app/tests/test_cold_start.py`

## Relationships

- [Missing History Tests](Missing_History_Tests.md) (2 shared connections)
- [Cold Start Live Loop Tests](Cold_Start_Live_Loop_Tests.md) (1 shared connections)

## Source Files

- `app/tests/test_cold_start.py`

## Audit Trail

- EXTRACTED: 17 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*