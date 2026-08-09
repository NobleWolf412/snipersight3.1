# Toast Isolation Tests

> 8 nodes

## Key Concepts

- **report()** (6 connections) — `app/engine/factorstats.py`
- **load_candidates()** (4 connections) — `app/engine/factorstats.py`
- **main()** (4 connections) — `app/engine/factorstats.py`
- **format_report()** (3 connections) — `app/engine/factorstats.py`
- **Path** (2 connections)
- **Read every candidate of `setup_version` in `state`, joined to its outcome.** (1 connections) — `app/engine/factorstats.py`
- **Full grading over the store, as a plain JSON-serialisable dict. READ-ONLY:     t** (1 connections) — `app/engine/factorstats.py`
- **Paste-friendly rendering: headline first, per-factor table second, clusters** (1 connections) — `app/engine/factorstats.py`

## Relationships

- [Volume, Ranges & Aggregation](Volume%2C_Ranges_%26_Aggregation.md) (4 shared connections)
- [Tracer UI](Tracer_UI.md) (1 shared connections)
- [Funding Rate Engine](Funding_Rate_Engine.md) (1 shared connections)

## Source Files

- `app/engine/factorstats.py`

## Audit Trail

- EXTRACTED: 22 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*