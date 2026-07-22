---
name: HTF Level Query Shape — Sketch
type: finding
status: draft
project: snipersight3.1
next_owner: architect
closed_at:
---

# HTF Level Query Shape — Sketch

## Problem
The v0 spec (§19 fact-inspector, §26 multi-timeframe context) commits to per-entity fact engines and MTF context but does not yet specify the **runtime shape** by which higher-timeframe levels are consumed by (a) the chart renderer and (b) strategy/entry logic. Without that shape pinned down, Item D (Persistence & Retention) and the eventual Chart Interface + Strategy modules risk drifting into incompatible read paths — the classic "the bot sees different levels than the chart" bug.

This note captures a design sketch surfaced in an operator conversation on 2026-07-18 so Item D can either adopt, adapt, or reject it with reasoning on record. It is NOT a decision.

## Substance

### Core proposal
Higher-timeframe engines (swing / structure / zone / liquidity / regime — §19) publish their outputs as **typed, stateful, timestamped fact records** into a shared **level/fact store**. Both the chart renderer and the strategy engine read from that store via the same query API with an `as_of` cursor. The HTF engines do NOT re-run per LTF candle — they run on their own timeframe's candle close and their outputs persist until state-transitioned.

### Record shape (illustrative — Item D owns the canonical schema)
Every stored fact carries at minimum:
- `id` (deterministic, content-addressable per §4/§7)
- `instrument`, `timeframe`, `class` (SWING | STRUCTURE_BREAK | ZONE | LIQUIDITY | REGIME | ...)
- geometry: `price` for point levels, `(top, bottom)` for range levels, `(anchor_a, anchor_b)` for lines
- `state` — the entity's state machine value (per State Transition Tables §ST, `mem:state-transition-tables-draft`)
- `market_time` (source candle close), `confirmed_at` (per §5 causality), `invalidated_at` if applicable
- `source_ids` — lineage back to the facts / candles that produced this (per §8 auditability)
- `algo_version` (per §7 versioning constitution)
- `meta` — class-specific evidence (ATR at creation, touches, displacement, etc.)

### Query contract (illustrative)
```
levels.query(
  instrument,
  timeframes=[...],
  classes=[...],            # optional class filter
  states=[...],             # e.g. exclude BROKEN/INVALIDATED
  as_of=<timestamp>,        # HARD requirement — no facts with confirmed_at > as_of
  near_price=<optional>,
  window_pct=<optional>
) -> [FactRecord]
```

The `as_of` filter is the runtime realization of §5 causality: replay at time T sees only facts confirmed by T, and only the state each fact held at T. This is the mechanism that prevents repainting from being possible, rather than a policy against it.

### Why one store for chart and strategy
Reasoning from §8 (auditability) and §29 (visible comparison reports): if the chart renders from one path and the strategy reasons from another, no diff between the two is trustworthy. Single store + shared query = every entry can be pinned to the exact fact IDs that justified it, and the chart is guaranteed to be showing those same objects.

### Ranking & index concerns (for Item D)
- Price-indexed retrieval ("nearest untested 1D zone above spot") wants an interval tree or sorted structure keyed on price per (instrument, timeframe).
- State transitions must be an append-only event log so `as_of` reconstruction is exact, not approximate.
- HTF facts persist across many LTF candles — the LTF loop must NOT trigger HTF recomputation.

## A→Z (deferred to Item D)
This sketch does not prescribe implementation phases. Item D (Persistence & Retention spec) is the owner; it should:

1. Decide whether the fact store is one logical store or per-class stores with a query facade.
2. Specify the canonical record schema (fields, types, invariants) — must reconcile with Layer Boundary Schemas `mem:layer-boundary-schemas-draft` and State Transition Tables `mem:state-transition-tables-draft`.
3. Specify the query API surface (or at minimum, the required capabilities).
4. Specify the `as_of` semantics rigorously — including tie-breaking when a state transition and a query share a timestamp.
5. Specify retention: broken/invalidated facts retained per §23; how long, purged when.
6. Address whether HTF context (§26) is a materialized view over the store or a live query.

## Next step + owner
Owner: architect (self). Next step: **fold this sketch into Item D authoring** when Item D reaches the queue (currently blocked behind minor-pass follow-ups per TODO.md). If Item D diverges from this sketch, record the reasoning in the Item D document and mark this note `superseded`.

## Provenance
Surfaced in operator conversation 2026-07-18 while discussing "how would a trading app see HTF levels" against a BTC 1D chart with SMC-style annotations (order blocks, EQH, BOS/CHoCH, premium/discount bands, prev-day-highs). Operator's framing: the bot must be able to plot entries against the same HTF levels it reasons from.
