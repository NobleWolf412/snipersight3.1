# Pipeline Gate Tests

> 57 nodes

## Key Concepts

- **bias.py** (14 connections) — `app/engine/bias.py`
- **htfread.py** (14 connections) — `app/engine/htfread.py`
- **_d()** (8 connections) — `app/engine/htfread.py`
- **HtfContext** (8 connections) — `app/engine/htfread.py`
- **rungs_above()** (7 connections) — `app/engine/bias.py`
- **Bias** (7 connections) — `app/engine/bias.py`
- **.check()** (7 connections) — `app/engine/bias.py`
- **target_alt()** (7 connections) — `app/engine/htfread.py`
- **annotate()** (7 connections) — `app/engine/htfread.py`
- **.reading()** (5 connections) — `app/engine/bias.py`
- **.htf_zone_at()** (5 connections) — `app/engine/htfread.py`
- **.next_htf_pool()** (5 connections) — `app/engine/htfread.py`
- **load()** (5 connections) — `app/engine/htfread.py`
- **counterfactual()** (5 connections) — `app/engine/htfread.py`
- **grade()** (5 connections) — `app/engine/htfread.py`
- **composite()** (4 connections) — `app/engine/bias.py`
- **alignment()** (4 connections) — `app/engine/bias.py`
- **verdict()** (4 connections) — `app/engine/bias.py`
- **load()** (4 connections) — `app/engine/bias.py`
- **.range_at()** (4 connections) — `app/engine/htfread.py`
- **_as_of()** (3 connections) — `app/engine/bias.py`
- **.evidence()** (3 connections) — `app/engine/bias.py`
- **_fill_bar()** (3 connections) — `app/engine/htfread.py`
- **blocked()** (2 connections) — `app/engine/bias.py`
- **permitted()** (2 connections) — `app/engine/bias.py`
- *... and 32 more nodes in this community*

## Relationships

- [Funding Rate Engine](Funding_Rate_Engine.md) (1 shared connections)
- [Cycle Detection Engine](Cycle_Detection_Engine.md) (1 shared connections)
- [Kraken Adapter](Kraken_Adapter.md) (1 shared connections)

## Source Files

- `app/engine/bias.py`
- `app/engine/htfread.py`

## Audit Trail

- EXTRACTED: 175 (98%)
- INFERRED: 4 (2%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*