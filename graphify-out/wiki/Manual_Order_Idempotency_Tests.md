# Manual Order Idempotency Tests

> 23 nodes

## Key Concepts

- **load_orders()** (11 connections) — `app/engine/entrystats.py`
- **counterfactual()** (8 connections) — `app/engine/entrystats.py`
- **_d()** (6 connections) — `app/engine/entrystats.py`
- **_f()** (5 connections) — `app/engine/entrystats.py`
- **walk_forward()** (5 connections) — `app/engine/entrystats.py`
- **_spread()** (3 connections) — `app/engine/entrystats.py`
- **_execution_window()** (3 connections) — `app/engine/entrystats.py`
- **_first_bar_at_or_after()** (3 connections) — `app/engine/entrystats.py`
- **_rows()** (3 connections) — `app/engine/entrystats.py`
- **_plans_elsewhere()** (3 connections) — `app/engine/entrystats.py`
- **_plan_anchor()** (3 connections) — `app/engine/entrystats.py`
- **_feature()** (2 connections) — `app/engine/entrystats.py`
- **Taker-minus-maker spread for THIS symbol's venue.      The entry-fee penalty i** (1 connections) — `app/engine/entrystats.py`
- **(max_holding_bars, max_entry_bars) as RECORDED, not as currently coded.      E** (1 connections) — `app/engine/entrystats.py`
- **Best-effort float. Used ONLY on R-multiples and already-derived ratios.** (1 connections) — `app/engine/entrystats.py`
- **Decimal or None. Used on every price. Never returns a float.** (1 connections) — `app/engine/entrystats.py`
- **Index of the first candle that OPENS at or after `available_at`.      This is** (1 connections) — `app/engine/entrystats.py`
- **Resolve a hypothetical position against stored bars. COUNTERFACTUAL.      Rule** (1 connections) — `app/engine/entrystats.py`
- **What the trade WOULD have done. COUNTERFACTUAL — never a recorded result.** (1 connections) — `app/engine/entrystats.py`
- **Facts of one kind/version across the whole portfolio, in causal order.      `s** (1 connections) — `app/engine/entrystats.py`
- **Which OTHER setup versions claim these order keys.      Diagnostic only, and i** (1 connections) — `app/engine/entrystats.py`
- **The plan price an order was created from, not necessarily its limit.      MAKER_** (1 connections) — `app/engine/entrystats.py`
- **One record per VALIDATED plan, joined to its order lifecycle, its outcome     a** (1 connections) — `app/engine/entrystats.py`

## Relationships

- [Entry Stats Engine](Entry_Stats_Engine.md) (13 shared connections)
- [Kraken Adapter](Kraken_Adapter.md) (3 shared connections)

## Source Files

- `app/engine/entrystats.py`

## Audit Trail

- EXTRACTED: 66 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*