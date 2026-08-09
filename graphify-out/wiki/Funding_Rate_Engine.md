# Funding Rate Engine

> 11 nodes

## Key Concepts

- **analyze()** (10 connections) — `app/engine/factorstats.py`
- **pearson()** (3 connections) — `app/engine/factorstats.py`
- **noise_floor()** (3 connections) — `app/engine/factorstats.py`
- **_covariance()** (3 connections) — `app/engine/factorstats.py`
- **_clusters()** (3 connections) — `app/engine/factorstats.py`
- **_std()** (2 connections) — `app/engine/factorstats.py`
- **Pearson r over paired samples. Returns (r, n); r is None when undefined —     fe** (1 connections) — `app/engine/factorstats.py`
- **Two-sided 95% floor for a correlation at sample size n. |r| inside this is     i** (1 connections) — `app/engine/factorstats.py`
- **Pairwise-complete covariance: pairs where either side is missing are dropped** (1 connections) — `app/engine/factorstats.py`
- **Connected components over the |r| >= REDUNDANT_R graph. Transitivity is the** (1 connections) — `app/engine/factorstats.py`
- **Grade every factor the extractor produces. Pure computation, no I/O, no RNG,** (1 connections) — `app/engine/factorstats.py`

## Relationships

- [Volume, Ranges & Aggregation](Volume%2C_Ranges_%26_Aggregation.md) (7 shared connections)
- [Bias Ladder Engine](Bias_Ladder_Engine.md) (1 shared connections)
- [Toast Isolation Tests](Toast_Isolation_Tests.md) (1 shared connections)

## Source Files

- `app/engine/factorstats.py`

## Audit Trail

- EXTRACTED: 28 (97%)
- INFERRED: 1 (3%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*