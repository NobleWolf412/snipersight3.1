# Chart Vendor Data Layer

> 30 nodes

## Key Concepts

- **prune.py** (21 connections) — `app/prune.py`
- **plan_facts()** (7 connections) — `app/prune.py`
- **apply_runs()** (7 connections) — `app/prune.py`
- **main()** (7 connections) — `app/prune.py`
- **apply_facts()** (6 connections) — `app/prune.py`
- **maybe_auto_prune_runs()** (5 connections) — `app/prune.py`
- **plan_runs()** (4 connections) — `app/prune.py`
- **current_versions()** (3 connections) — `app/prune.py`
- **versions_named_in_code()** (3 connections) — `app/prune.py`
- **_last_ran_at()** (3 connections) — `app/prune.py`
- **referenced_zone_ids()** (3 connections) — `app/prune.py`
- **last_runs_prune_at()** (3 connections) — `app/prune.py`
- **_retry_locked()** (3 connections) — `app/prune.py`
- **_delete_batch()** (3 connections) — `app/prune.py`
- **_freelist_bytes()** (3 connections) — `app/prune.py`
- **_report()** (2 connections) — `app/prune.py`
- **_report_facts()** (2 connections) — `app/prune.py`
- **Retention — delete what nothing can read, and nothing else.  `docs/SPEC-persiste** (1 connections) — `app/prune.py`
- **What would go, and what each keep rule is protecting.      Four keeps, and every** (1 connections) — `app/prune.py`
- **What each derived engine writes right now, read from the engines.** (1 connections) — `app/prune.py`
- **Every derived-kind version string that appears anywhere in engine     source. A** (1 connections) — `app/prune.py`
- **Wall-clock time this algo_version last produced a run. engine_runs is     the on** (1 connections) — `app/prune.py`
- **Zone ids named by a PERMANENT fact.      `zone_id` is `SYMBOL|TF|TYPE|TS` and ca** (1 connections) — `app/prune.py`
- **Superseded derived generations that nothing reads and nothing names.      Four g** (1 connections) — `app/prune.py`
- **Delete in retried batches; ALWAYS leave a retention fact behind.      The fact i** (1 connections) — `app/prune.py`
- *... and 5 more nodes in this community*

## Relationships

- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (2 shared connections)
- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (1 shared connections)
- [Bias, Trend & Setups](Bias%2C_Trend_%26_Setups.md) (1 shared connections)
- [Chart Vendor Scales](Chart_Vendor_Scales.md) (1 shared connections)
- [Shell Disposition & Risk Rendering](Shell_Disposition_%26_Risk_Rendering.md) (1 shared connections)

## Source Files

- `app/prune.py`

## Audit Trail

- EXTRACTED: 96 (98%)
- INFERRED: 2 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*