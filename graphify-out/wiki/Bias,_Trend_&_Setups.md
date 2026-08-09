# Bias, Trend & Setups

> 20 nodes

## Key Concepts

- **AutoPruneCase** (14 connections) — `app/tests/test_auto_prune.py`
- **.add_run()** (7 connections) — `app/tests/test_auto_prune.py`
- **.receipts()** (4 connections) — `app/tests/test_auto_prune.py`
- **.test_the_receipt_is_the_schedule_state()** (4 connections) — `app/tests/test_auto_prune.py`
- **test_auto_prune.py** (3 connections) — `app/tests/test_auto_prune.py`
- **.test_first_sweep_runs_and_leaves_a_receipt()** (3 connections) — `app/tests/test_auto_prune.py`
- **.test_a_second_sweep_the_same_day_is_refused()** (3 connections) — `app/tests/test_auto_prune.py`
- **.test_kept_rows_survive_the_sweep()** (3 connections) — `app/tests/test_auto_prune.py`
- **.test_a_facts_receipt_does_not_satisfy_the_runs_cadence()** (2 connections) — `app/tests/test_auto_prune.py`
- **.test_an_old_receipt_makes_the_sweep_due_again()** (2 connections) — `app/tests/test_auto_prune.py`
- **.test_the_routine_path_can_never_reach_the_facts_target()** (2 connections) — `app/tests/test_auto_prune.py`
- **.test_the_heartbeat_is_beaten_per_batch()** (2 connections) — `app/tests/test_auto_prune.py`
- **.setUp()** (1 connections) — `app/tests/test_auto_prune.py`
- **.tearDown()** (1 connections) — `app/tests/test_auto_prune.py`
- **.test_this_suite_cannot_reach_the_live_store()** (1 connections) — `app/tests/test_auto_prune.py`
- **The scanner's routine telemetry sweep — cadence, receipts, and its cage.  The sw** (1 connections) — `app/tests/test_auto_prune.py`
- **No sidecar file, no settings row: due-ness is read from the last         runs re** (1 connections) — `app/tests/test_auto_prune.py`
- **The two targets keep separate clocks — a manual facts prune must         not pos** (1 connections) — `app/tests/test_auto_prune.py`
- **The cage, pinned at the AST: every function the sweep calls is on         an all** (1 connections) — `app/tests/test_auto_prune.py`
- **The sweep inherits every keep rule — referenced, failed, newest,         window** (1 connections) — `app/tests/test_auto_prune.py`

## Relationships

- [Chart Vendor Data Layer](Chart_Vendor_Data_Layer.md) (1 shared connections)

## Source Files

- `app/tests/test_auto_prune.py`

## Audit Trail

- EXTRACTED: 57 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*