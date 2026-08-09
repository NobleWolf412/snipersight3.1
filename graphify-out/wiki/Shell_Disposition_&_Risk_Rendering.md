# Shell Disposition & Risk Rendering

> 31 nodes

## Key Concepts

- **PruneRunsCase** (20 connections) — `app/tests/test_prune_runs.py`
- **.prune()** (12 connections) — `app/tests/test_prune_runs.py`
- **.add_run()** (11 connections) — `app/tests/test_prune_runs.py`
- **.surviving_ids()** (10 connections) — `app/tests/test_prune_runs.py`
- **.test_a_run_a_fact_points_at_is_never_deleted()** (6 connections) — `app/tests/test_prune_runs.py`
- **.test_a_failed_run_is_never_deleted()** (5 connections) — `app/tests/test_prune_runs.py`
- **.test_the_newest_run_of_each_engine_survives()** (5 connections) — `app/tests/test_prune_runs.py`
- **.test_an_old_unreferenced_passing_run_goes()** (5 connections) — `app/tests/test_prune_runs.py`
- **.test_a_run_with_an_empty_run_id_is_still_deletable()** (5 connections) — `app/tests/test_prune_runs.py`
- **.test_the_newest_run_of_each_version_survives_not_just_each_engine()** (4 connections) — `app/tests/test_prune_runs.py`
- **.test_runs_inside_the_keep_window_survive()** (4 connections) — `app/tests/test_prune_runs.py`
- **.test_the_keep_window_is_honoured_as_given()** (4 connections) — `app/tests/test_prune_runs.py`
- **.test_a_plan_alone_deletes_nothing()** (4 connections) — `app/tests/test_prune_runs.py`
- **.test_the_prune_records_itself_as_a_fact()** (4 connections) — `app/tests/test_prune_runs.py`
- **.test_facts_and_candles_are_never_touched()** (4 connections) — `app/tests/test_prune_runs.py`
- **test_prune_runs.py** (3 connections) — `app/tests/test_prune_runs.py`
- **.add_fact()** (3 connections) — `app/tests/test_prune_runs.py`
- **.test_deleting_requires_an_explicit_flag()** (2 connections) — `app/tests/test_prune_runs.py`
- **.test_both_targets_are_implemented()** (2 connections) — `app/tests/test_prune_runs.py`
- **.setUp()** (1 connections) — `app/tests/test_prune_runs.py`
- **.tearDown()** (1 connections) — `app/tests/test_prune_runs.py`
- **Retention on `engine_runs` — what survives a prune, and what it costs.  Every te** (1 connections) — `app/tests/test_prune_runs.py`
- **Lineage. This is the rule the whole table exists to serve.** (1 connections) — `app/tests/test_prune_runs.py`
- **2 rows in 4.1M on the live store. Keeping every failure forever is         free;** (1 connections) — `app/tests/test_prune_runs.py`
- **/api/overview asks for exactly this, twice a minute.** (1 connections) — `app/tests/test_prune_runs.py`
- *... and 6 more nodes in this community*

## Relationships

- [Chart Vendor Data Layer](Chart_Vendor_Data_Layer.md) (1 shared connections)

## Source Files

- `app/tests/test_prune_runs.py`

## Audit Trail

- EXTRACTED: 123 (98%)
- INFERRED: 2 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*