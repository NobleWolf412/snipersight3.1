# Chart Vendor Data Layer

> 22 nodes

## Key Concepts

- **prune.py** (21 connections) — `app/prune.py`
- **apply_runs()** (7 connections) — `app/prune.py`
- **main()** (7 connections) — `app/prune.py`
- **apply_facts()** (6 connections) — `app/prune.py`
- **maybe_auto_prune_runs()** (5 connections) — `app/prune.py`
- **plan_runs()** (4 connections) — `app/prune.py`
- **last_runs_prune_at()** (3 connections) — `app/prune.py`
- **_retry_locked()** (3 connections) — `app/prune.py`
- **_delete_batch()** (3 connections) — `app/prune.py`
- **_freelist_bytes()** (3 connections) — `app/prune.py`
- **test_prune_facts.py** (3 connections) — `app/tests/test_prune_facts.py`
- **_report()** (2 connections) — `app/prune.py`
- **_report_facts()** (2 connections) — `app/prune.py`
- **Retention — delete what nothing can read, and nothing else.  `docs/SPEC-persiste** (1 connections) — `app/prune.py`
- **What would go, and what each keep rule is protecting.      Four keeps, and every** (1 connections) — `app/prune.py`
- **Delete in retried batches; ALWAYS leave a retention fact behind.      The fact i** (1 connections) — `app/prune.py`
- **When the runs target last pruned — read from the receipts themselves.      The r** (1 connections) — `app/prune.py`
- **The scanner's routine telemetry sweep. Runs target ONLY, ever.      The runs tab** (1 connections) — `app/prune.py`
- **Run one write op through lock contention; the scanner is a legitimate     concur** (1 connections) — `app/prune.py`
- **One batch, retried through contention. Raises only if it never lands.      The s** (1 connections) — `app/prune.py`
- **Delete in batches, then record the deletion as a fact.      The fact matters mor** (1 connections) — `app/prune.py`
- **Retention on superseded derived facts — the reference test, mostly.  `SPEC-persi** (1 connections) — `app/tests/test_prune_facts.py`

## Relationships

- [plan_facts](plan_facts.md) (6 shared connections)
- [Universe & Rate Limiting](Universe_%26_Rate_Limiting.md) (2 shared connections)
- [Chart Vendor Pane Views](Chart_Vendor_Pane_Views.md) (1 shared connections)
- [Bias, Trend & Setups](Bias%2C_Trend_%26_Setups.md) (1 shared connections)
- [Shell Disposition & Risk Rendering](Shell_Disposition_%26_Risk_Rendering.md) (1 shared connections)
- [Chart Vendor Scales](Chart_Vendor_Scales.md) (1 shared connections)

## Source Files

- `app/prune.py`
- `app/tests/test_prune_facts.py`

## Audit Trail

- EXTRACTED: 76 (97%)
- INFERRED: 2 (3%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*