# plan_facts

> 10 nodes

## Key Concepts

- **plan_facts()** (7 connections) — `app/prune.py`
- **current_versions()** (3 connections) — `app/prune.py`
- **versions_named_in_code()** (3 connections) — `app/prune.py`
- **_last_ran_at()** (3 connections) — `app/prune.py`
- **referenced_zone_ids()** (3 connections) — `app/prune.py`
- **What each derived engine writes right now, read from the engines.** (1 connections) — `app/prune.py`
- **Every derived-kind version string that appears anywhere in engine     source. A** (1 connections) — `app/prune.py`
- **Wall-clock time this algo_version last produced a run. engine_runs is     the on** (1 connections) — `app/prune.py`
- **Zone ids named by a PERMANENT fact.      `zone_id` is `SYMBOL|TF|TYPE|TS` and ca** (1 connections) — `app/prune.py`
- **Superseded derived generations that nothing reads and nothing names.      Four g** (1 connections) — `app/prune.py`

## Relationships

- [Chart Vendor Data Layer](Chart_Vendor_Data_Layer.md) (6 shared connections)

## Source Files

- `app/prune.py`

## Audit Trail

- EXTRACTED: 24 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*