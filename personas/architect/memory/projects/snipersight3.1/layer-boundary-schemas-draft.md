---
name: SniperSight3 Layer Boundary Schemas — Draft (Remediation Item B)
description: Architect draft of the Layer Boundary Schemas section. Defines one canonical object per boundary between the five layers (§3) plus the fact-inspector record. Addresses audit FINDING-004, 010 (partial), 023 and re-audit B-01 (content_hash inputs → §D8), B-02 (provenance timeframe tags), B-03 (bar_close_ts convention).
type: project
---

# Layer Boundary Schemas — Draft §3.1

**Status:** Architect draft **v0.2**, 2026-07-17. Supersedes v0.1. Incorporates re-audit fixes B-01…B-06. Depends on Determinism Policy draft v0.2 §4.1 (numeric types, ordering, version stamps, §D8 Fact Identity). Freeze caveat per re-audit §1: cannot merge until §30 (item F) closes.
**Rule:** any object crossing a layer boundary must conform to one of these schemas. Layers may add internal fields but the boundary contract is frozen per version.

Notation: fields marked `!` are required; `?` optional; types use Python-like syntax with `Decimal` per D1.

---

## S1. Layer 1 → Layer 2 boundary: `Candle`

```
Candle {
  ! symbol:            str                  # "BTCUSDT"
  ! venue:             str                  # "binance-spot"
  ! timeframe:         Enum{1W,1D,4H,1H,15m,5m}
  ! bar_open_ts:       int                  # UTC epoch nanoseconds
  ! bar_close_ts:      int                  # UTC epoch nanoseconds; **exclusive-end convention (B-03): bar_close_ts = bar_open_ts_of_next_bar**. A 15m bar starting 00:00:00Z has bar_close_ts = 00:15:00Z (not 00:14:59.999…Z).
  ! open:              Decimal
  ! high:              Decimal
  ! low:               Decimal
  ! close:             Decimal
  ! volume:            Decimal
  ! source_lineage:    str                  # e.g. "binance-klines-v1@2026-01-15T00:00:00Z"
  ! ingest_batch_id:   str                  # groups candles from one import job
    gap_before:        bool = false         # true if prior bar is missing in source
}
```

**Invariants:** `low ≤ open,close ≤ high`; `bar_close_ts - bar_open_ts` = fixed per timeframe; `bar_open_ts` aligned per D4.

## S2. Layer 2 fact — common envelope: `Fact`

Every Layer-2 fact embeds this envelope. Concrete kinds (`Swing`, `StructureBreak`, `Zone`, `LiquidityLevel`, `Regime`) extend it.

```
Fact {
  ! fact_id:           str                  # content_hash prefixed with kind
  ! kind:              Enum{swing,structure_break,zone,liquidity,regime}
  ! symbol:            str
  ! timeframe:         Enum{...}
  ! order_key:         (bar_close_ts:int, timeframe_rank:int, entity_kind_rank:int, intra_bar_seq:int)   # D3
  ! state:             Enum{DEVELOPING,PROVISIONAL,CONFIRMED,INVALIDATED,EXPIRED,SUPERSEDED}
  ! state_history:     [ {state, at_bar_close_ts, cause_fact_id?} ]
  ! algo_version:      str
  ! policy_version:    str
  ! content_hash:      str                  # BLAKE2b-256; **inputs enumerated in Determinism Policy §D8.2** (B-01). Excludes state/state_history/fact_id/algo_version/policy_version/input_hash/content_hash/intra_bar_seq.
  ! input_hash:        str                  # BLAKE2b-256 of the ordered input-candle window per §D8.3
  ! provenance:        [ {timeframe: Enum{...}, bar_close_ts: int}, ... ]   # (B-02) per-candle tag pair; supports multi-timeframe facts
  ! body:              <kind-specific>
}
```

**Fact identity contract (cross-ref).** `fact_id = "<kind>:" + hex(content_hash)`. `content_hash` is stable across all lifecycle transitions of the same fact; `state` and `state_history` are excluded from the hash by §D8.2. Two facts with the same `content_hash` are the same fact; two facts with different `content_hash` are different facts even if their currently visible bodies would render identically after some later mutation. Canonical serialization format for both hashes is **RFC 8785 JCS with Decimal-as-string per §D8.1**.

## S3. Layer 2 kind bodies (v0)

```
SwingBody {
  ! tier:              Enum{micro, local, structural, major}
  ! side:              Enum{high, low}
  ! anchor_bar_ts:     int                  # bar_close_ts of the extreme bar
  ! anchor_price:      Decimal
  ! confirmation_bar_ts: int?               # set on transition PROVISIONAL→CONFIRMED
  ! protected:         bool = false         # per §30 item 3, once resolved
}

StructureBreakBody {
  ! kind:              Enum{BOS, CHoCH}
  ! direction:         Enum{up, down}
  ! reference_swing_id: str                 # fact_id of the swing whose level was broken
  ! break_bar_ts:      int
  ! break_price:       Decimal              # close price of breaking bar
  ! tolerance_used:    Decimal              # actual max(tick, 0.05*ATR) at emit time
}

ZoneBody {
  ! kind:              Enum{demand, supply, flipped_demand, flipped_supply}
  ! top:               Decimal
  ! bottom:            Decimal
  ! origin_bar_ts:     int
  ! lifecycle:         Enum{FRESH,TOUCHED,TESTED,WEAKENED,BROKEN,FLIPPED,INVALIDATED}
  ! touch_history:     [ {bar_ts, penetration_pct} ]
  ! strength_score:    Decimal?             # UNSPECIFIED until §30 item resolved
}

LiquidityLevelBody {
  ! kind:              Enum{equal_highs, equal_lows, session_high, session_low}
  ! price:             Decimal
  ! constituent_bar_ts: [int]               # bars forming the cluster
  ! swept_bar_ts:      int?
  ! rejection_bar_ts:  int?
}

RegimeBody {
  ! state:             Enum{BULL_TREND,WEAKENING_BULL,BEAR_TREND,WEAKENING_BEAR,
                            RANGE,COMPRESSION,EXPANSION,TRANSITION,DISORDERED}
  ! supporting_evidence: { swing_ids: [str], structure_break_ids: [str], zone_ids: [str] }
  # classification function itself is UNSPECIFIED — deferred to §30 remediation.
}
```

## S4. Layer 2 → Layer 3 boundary: `FactStream`

Layer 3 (strategy) consumes an **immutable, replayable stream** of `Fact` objects filtered by `order_key`. No push semantics; strategies pull with a cursor.

```
FactStream.read(after_order_key, until_order_key?, kinds?, symbols?, timeframes?) -> Iterator[Fact]
```

**Contract:** for identical arguments and identical audit-store state, the iterator produces the identical byte sequence. Bit-exact per §29(11).

## S5. Layer 3 → Layer 4 boundary: `TradeIntent` (v0-partial — Layer 3 exists in v0 as scaffolding only)

Deferred: not required for v0's §29 acceptance. Schema-stubbed here so §7 versioning has an anchor.

```
TradeIntent {
  ! intent_id:         str
  ! strategy_version:  str
  ! symbol:            str
  ! direction:         Enum{long, short}
  ! trigger_fact_ids:  [str]                # Layer-2 facts that led to this intent
  ! hypothesis_text:   str                  # human-readable "why"
  ! desired_size:      Decimal              # in base units
  ! desired_entry:     Decimal
  ! desired_stop:      Decimal
  ! desired_targets:   [Decimal]
  ! created_at_order_key: (…)
}
```

## S6. Layer 4 → Layer 5 boundary: `RiskVerdict` (deferred to v1; stub only, addresses FINDING-010)

```
RiskVerdict {
  ! intent_id:         str
  ! verdict:           Enum{APPROVE, REDUCE, REJECT}
  ! modified_size:     Decimal?             # required if REDUCE
  ! modified_stop:     Decimal?             # required if REDUCE and stop changed
  ! reject_code:       Enum{…}?             # required if REJECT
  ! decided_at_order_key: (…)
  ! risk_policy_version: str
}
```

## S7. Fact Inspector record

The fact inspector (§19) is a read-only view over the audit store. Its record is exactly `Fact` (S2) rendered with:
- `provenance` expanded to the concrete `Candle` records.
- `state_history` expanded with human-readable cause labels.
- `algo_version` linked to the version registry entry.

**"Lineage" is the union of `algo_version` + `input_hash` + `provenance`.** The word "lineage" (§19) and "version chain" (§7) refer to the same concept — resolves FINDING-023 by adopting **lineage** as the canonical term and marking "version chain" as deprecated wording.

---

## Open items requiring user sign-off

1. **Zone `strength_score`** is stubbed. Whether it's a v0 field or deferred to v1 depends on §30 item 7/8 resolution.
2. **Regime classification** stubbed. Same dependency.
3. **`TradeIntent.hypothesis_text`** — string vs structured reason enum. String is easier for v0 scaffolding; structured is better long-term. Recommend string with a v1 migration.
4. **Fact `body` polymorphism** — recommend tagged union serialized as JSON with a `kind` discriminator matching `Fact.kind`. Alternative: separate tables per kind. Preferred: single audit-store table with JSON body for v0 simplicity.
