---
name: SniperSight3 State Transition Tables — Draft (Remediation Item C)
description: Architect draft of the State Transition Tables appendix. Binds the §6 six-state enum to every stateful entity (candle, swing, structure break, zone, liquidity level, regime), gives per-transition deterministic triggers, and resolves the four §30 mechanism items (tier promotion, break tolerance, retest, provisional-vs-tradable). Addresses FINDING-005, 007, 014 (partial), 022, 024; files change requests CR-A/CR-B against Drafts A and B.
type: project
---

# State Transition Tables — Draft Appendix ST

**Status:** Architect draft **v0.1**, 2026-07-17.
**Depends on:** Determinism Policy draft v0.3 (§D1–§D9) and Layer Boundary Schemas draft v0.2 (§S1–§S7). Freeze caveat per re-audit §1 applies: this draft does not merge until §30 (item F) closes, and is re-reviewed at F-close together with A and B.
**Findings addressed:** FINDING-005 (blocker — closed), FINDING-007 (major — closed), FINDING-014 (major — partial; classifier remainder assigned to item F), FINDING-022 (minor — closed), FINDING-024 (minor — closed via §M1).
**§30 mechanism items resolved here:** item 2 (tier promotion function, §M3), item 6 (break tolerance, §M1), item 8 (retest definition and expiration, §M4), item 10 (provisional-vs-tradable, §M2).

---

## ST0. Conventions and the emit-once principle

1. **Event clock.** All state transitions occur at bar closes only, per §D5. No fact changes state mid-bar in v0. `at_bar_close_ts` on every transition is the close (exclusive-end, §S1/B-03) of the bar whose close triggered it.
2. **Deterministic triggers.** Every trigger below is a pure function of: canonical candles up to and including the triggering bar, facts already committed at strictly smaller `order_key` (or same instant but smaller rank per §D5/§D3), the parameter registry (§ST9), and `policy_version`. All comparisons are full-precision `Decimal` per §D1. ATR references are the canonical ATR(14) of the fact's own timeframe per §D2; any ATR-dependent trigger is suppressed during warmup per §D2 (no fact, diagnostic per §D9).
3. **Emit-once, transition-by-event.** A fact's body is frozen at emit (fact identity, §D8). Everything that changes after emit is recorded as an appended entry in `state_history` (envelope, hash-excluded) or — for zones — `lifecycle_history` (§ST5). Fields that would mutate the body are removed from the body and derived from history; see change requests §ST10. **Rejected alternative:** mutable body fields with re-hashing — rejected because it breaks `fact_id` stability across transitions and §29(11) bit-exactness.
4. **Evaluation order within one bar-close instant.** (a) timeframes ascending per §D5; (b) within a timeframe, entity kinds in `entity_kind_rank` order (§D3): candle → swing → structure_break → zone → liquidity → regime; (c) within a kind: transitions of existing facts first (in ascending `order_key` of the fact), then new-fact emissions (ordered per §D3). This makes same-instant cross-references well-defined (e.g., a zone created from a swing confirmed at the same close; a 1H sweep-rejection consuming a 15m CHoCH committed earlier in the same instant).
5. **One transition per fact per bar.** When multiple transitions of one fact could fire on the same close, the highest-precedence transition fires and the intermediate ones are not recorded (precedence stated per table). Rationale: replay equality is defined over recorded transitions; recording synthesized intermediate hops invites divergence.
6. **History is never falsified.** A CONFIRMED fact is a permanent historical record. Later price action never deletes or "un-confirms" it; it is captured by new facts (StructureBreak, sweep events, successor facts) referencing the old one. This matches §23 ("state changes instead of deleting history") and keeps the audit store append-only.

## ST1. §6 state × entity applicability matrix (FINDING-005, FINDING-022)

| Entity | DEVELOPING | PROVISIONAL | CONFIRMED | INVALIDATED | EXPIRED | SUPERSEDED |
|---|---|---|---|---|---|---|
| Candle (Layer 1, not a Fact) | UI-only (§ST2) | — | implicit "closed" | — | — | — |
| Swing | — | ✓ entry state | ✓ | ✓ (from PROVISIONAL only) | — | ✓ (tier promotion §M3) |
| StructureBreak | — | — | ✓ entry, terminal | — | — | — |
| Zone (envelope; zone lifecycle is a second track, §ST5) | — | — | ✓ entry | ✓ (mirrors lifecycle INVALIDATED) | — | ✓ (merge or flip successor) |
| LiquidityLevel | — | — | ✓ entry | ✓ (accepted sweep) | ✓ (session rollover) | ✓ (constituent addition) |
| Regime | — | — | ✓ entry | — | — | ✓ (classification change) |

**Bindings of the previously dead enum values (closes FINDING-022):**
- **DEVELOPING** — reserved for sub-bar observation (v1). Under v0's bar-close event clock (§D5) no persisted Layer-2 fact is ever DEVELOPING. The forming-candle overlay in the UI is a Layer-5 rendering, not a fact.
- **EXPIRED** — enters only for session-scoped liquidity levels at boundary rollover (§ST6). No other v0 entity expires: swing candidates always resolve deterministically within their confirmation window (§ST3), zones are stored forever (§23), breaks and regimes are historical records.
- **SUPERSEDED** — a fact replaced by a **successor fact**, always with `cause_fact_id` = successor and (CR-A-1) the successor carrying `predecessor_fact_ids` back-reference. Three successor mechanisms exist in v0: swing tier promotion (§M3), zone merge/flip (§ST5), liquidity constituent addition (§ST6), plus regime change (§ST7).

**Uniform query contract:** "live facts" = `state == CONFIRMED`. PROVISIONAL facts are visible in replay but flagged; INVALIDATED / EXPIRED / SUPERSEDED are terminal.

## ST2. Candle (Layer 1)

Candles are not Facts and carry no envelope. Two implicit states:

| # | From | To | Trigger |
|---|---|---|---|
| C1 | (forming) | DEVELOPING (UI only) | current bar open per §D4 boundary; never persisted to the canonical store |
| C2 | DEVELOPING | closed (canonical) | bar boundary reached per §D4; candle written once, immutable; re-import must reproduce it byte-identically (§19, §29(12)) |

`gap_before = true` on the first candle after a detected gap; triggers ATR reset per §D2. No other candle state exists.

## ST3. Swing

States: PROVISIONAL → CONFIRMED → SUPERSEDED; PROVISIONAL → INVALIDATED. Written for a swing **high**; lows are the exact mirror (swap high/low, > / <).

**Candidate detection (emit rule).** At close of bar X (all of X−2, X−1, X closed, same timeframe): if `high[X] > high[X−1]` and `high[X] > high[X−2]` (strict Decimal comparisons), emit `Swing{tier: micro, side: high, anchor_bar_ts: close_ts(X), anchor_price: high[X]}` with `state = PROVISIONAL`. Detection time = close of X. Exact equality with either left neighbor disqualifies the candidate (tie rule **P-SW-TIE**, mechanism default, ratify at F — §ST11).

| # | From | To | Trigger (at each subsequent bar close X+k, k = 1, 2) | Recorded detail |
|---|---|---|---|---|
| SW1 | PROVISIONAL | INVALIDATED | `high[X+k] ≥ high[X]` for k ∈ {1, 2} (equality invalidates, per P-SW-TIE) | `cause: violated_by_bar`, violating `bar_close_ts` |
| SW2 | PROVISIONAL | CONFIRMED | k = 2 and `high[X+1] < high[X]` and `high[X+2] < high[X]` (the §20 five-candle fractal complete: two closed candles each side) | confirmation time = close of X+2; `confirmation_bar_ts` derived from this entry (CR-B-1) |
| SW3 | CONFIRMED | SUPERSEDED | tier promotion fires per §M3 | `cause_fact_id` = successor swing |

**Resolution is total and bounded:** every PROVISIONAL swing reaches CONFIRMED or INVALIDATED within exactly 2 bars. No TTL, hence no EXPIRED.

**Confirmed swings are permanent (ST0.6).** A later trade or close beyond `anchor_price` does not invalidate a CONFIRMED swing; it produces a StructureBreak (§ST4) and/or sweep event (§ST6) referencing it. Whether a swing is currently "intact" is a derived query (no StructureBreak/accepted-sweep referencing it), not a state. **Rejected alternative:** CONFIRMED → INVALIDATED on price violation — rejected because it makes historical facts mutable on every stop-hunt, and the wick-vs-close choice (§30 item 5) would then contaminate fact identity; as a derived query, item 5's answer only affects downstream interpretation.

**Protected flag (§30 item 3 — user methodology, slot only).** Protected status is an annotation event pair `PROTECTED_SET` / `PROTECTED_CLEARED` appended to `state_history.detail` (CR-A-2, CR-B-2), not a state and not a body field. Entry/exit predicates are **UNSPECIFIED pending §30 item 3**; the mechanism (where the annotation lives, that it is hash-excluded, that it transitions only at bar closes) is fixed here.

## ST4. StructureBreak

Single-state entity: emitted CONFIRMED at the breaking bar's close; terminal. A break is a historical event — it is never invalidated, expired, or superseded. Reclaim behavior is recorded as evidence annotation on the break fact (`state_history.detail`, CR-A-2), per §22's "recorded as evidence before becoming required filters" (this also implements the accepted remedy of FINDING-008: displacement / follow-through / reclaim are demoted to recorded evidence, not required predicates).

**Emit rule (mechanism; §22 made precise):** at close of bar B on timeframe tf:
1. Reference level `L` = `anchor_price` of a CONFIRMED swing of tier ≥ **P-SB-TIER** (pends §30 item 4 — recommended: `local` for CHoCH, `structural` for BOS), on the same timeframe, not already broken in this direction (derived query, §ST3).
2. `close[B] > L + tolerance` for an upward break (mirror for downward), tolerance per §M1. Close-based confirmation is already normative in §22 ("a wick alone does not confirm the break") — §30 item 5 does **not** reopen this; item 5 governs swing-violation and zone-touch semantics only.
3. Kind label: prevailing structural direction `dir(tf)` = direction of the most recent StructureBreak of tier ≥ structural on tf (any label). If break direction == `dir(tf)` → **BOS**; if opposite → **CHoCH**; if `dir(tf)` is UNDEFINED (no prior break since stream start / gap reset) → **BOS** by convention and `dir(tf)` initializes to the break direction. (Labeling convention **P-SB-LABEL**, mechanism default, ratify at F — §ST11.)

Body records `reference_swing_id`, `break_price = close[B]`, `tolerance_used` with both components (`tick_component`, `atr_component`, `chosen` — aligns with deferred B-05; CR-B-6).

A retest window opens at emit per §M4; retest contact / rejection / expiry are recorded as evidence annotations on this fact, not states.

## ST5. Zone — two-track machine (FINDING-007)

Zones carry (a) the §6 **envelope** state and (b) the §23 **lifecycle** — parallel tracks. The lifecycle lives in `lifecycle` + `lifecycle_history` as envelope-level, hash-excluded fields (CR-B-3); `ZoneBody` retains only immutable creation attributes `{kind, top, bottom, origin_bar_ts, source_fact_ids}`.

**Creation.** Zone creation predicates (which §23 source patterns produce a zone, and how the band [bottom, top] is constructed) are **UNSPECIFIED and added to the item-F session agenda** (§ST11) — they were never specified in the source doc and are methodology. Everything below is fully specified *given* a created zone. Envelope at creation: CONFIRMED. Lifecycle at creation: FRESH.

**Penetration metric (demand zone; supply mirrored).** For bar B: `penetration(B) = clamp((top − low[B]) / (top − bottom), 0, 1)` if `low[B] ≤ top`, else 0. Full-precision Decimal; division at context precision per §D1.

**Lifecycle transitions** — evaluated at each bar close; precedence (highest first) within one bar: BROKEN > INVALIDATED > TESTED > TOUCHED; WEAKENED and FLIPPED are re-evaluated after the per-bar event lands (see notes):

| # | From | To | Trigger (demand zone; supply mirrored) | Params |
|---|---|---|---|---|
| Z1 | FRESH \| TOUCHED \| TESTED \| WEAKENED | TOUCHED | bar range intersects band (`low[B] ≤ top` and `high[B] ≥ bottom`) and `close[B] > top` (closes back outside — wick touch) | — |
| Z2 | FRESH \| TOUCHED \| TESTED \| WEAKENED | TESTED | `bottom ≤ close[B] ≤ top` (bar closes inside the band) | — |
| Z3 | TOUCHED \| TESTED | WEAKENED | cumulative: count of TESTED entries in `lifecycle_history` ≥ **P-ZN-KWEAK** (default 2) or `max penetration` over history ≥ **P-ZN-PWEAK** (default 0.75) | P-ZN-KWEAK, P-ZN-PWEAK |
| Z4 | FRESH \| TOUCHED \| TESTED \| WEAKENED | BROKEN | `close[B] < bottom − tolerance` (closes beyond the far edge), tolerance per §M1 | §M1 |
| Z5 | FRESH \| TOUCHED \| TESTED \| WEAKENED | INVALIDATED | full wick-through without break: `penetration(B) = 1` and `high[B] ≥ top` and `close[B] > top` (entire band swept intrabar, close back outside) — zone liquidity fully consumed | **P-ZN-INVAL** (default `full_wick_sweep`; ratify at F) |
| Z6 | BROKEN | FLIPPED | per **P-ZN-FLIP**, pends §30 item 7 (user). Both branches fully drafted: **Branch A (any close-through):** fires on the same close as Z4; successor zone of opposite polarity (kind `flipped_supply`) emitted immediately, band unchanged, `origin_bar_ts` = break bar. **Branch B (retest-and-rejection):** after Z4, if a retest per §M4 contacts the band within **P-RT-W** bars and rejects (close beyond the broken edge in the break direction within **P-RT-R** bars of contact), FLIPPED fires at the rejecting close and the successor is emitted; if the retest window expires or the retest reclaims (any close back inside/through against the break), the zone remains BROKEN, terminal. | P-ZN-FLIP (§30-7), §M4 |

Notes:
- Z3 (WEAKENED) is evaluated after Z1/Z2 land on the same close — a second TESTED close records TESTED then immediately WEAKENED? No: per ST0.5 one transition per bar — the recorded transition is WEAKENED (higher precedence once its cumulative condition holds, counting the current bar's would-be TESTED event). `detail` records the triggering penetration.
- Z1/Z2 re-entry from TOUCHED/TESTED/WEAKENED records repeat events in `lifecycle_history` without changing the headline lifecycle backward (monotone: FRESH → TOUCHED → TESTED → WEAKENED; repeats append `detail` only).
- BROKEN and FLIPPED are terminal for the lifecycle track. Broken zones remain stored (§23).

**Envelope track:**

| # | From | To | Trigger |
|---|---|---|---|
| ZE1 | CONFIRMED | INVALIDATED | lifecycle enters INVALIDATED (Z5) |
| ZE2 | CONFIRMED | SUPERSEDED | zone merge (below) or FLIPPED successor emitted (Z6); `cause_fact_id` = successor |

**Merge.** At creation time only: if a newly created zone's band overlaps a live (envelope-CONFIRMED, lifecycle ∉ {BROKEN, FLIPPED, INVALIDATED}) same-kind, same-timeframe zone by any amount (**P-ZN-MERGE** = any overlap, default), a merged zone is emitted instead: band = [min(bottoms), max(tops)], `origin_bar_ts` = earliest constituent origin, `predecessor_fact_ids` = all constituents, lifecycle carried = furthest-progressed constituent lifecycle; constituents → SUPERSEDED. **Rejected alternative:** post-hoc merging of two live zones drifting together — rejected for v0; merge is evaluated only when a new zone is born (single deterministic evaluation point).

## ST6. LiquidityLevel

Kinds per §S3: `equal_highs, equal_lows, session_high, session_low`. B-04's "cluster" question is resolved from C's side: **a cluster is not a separate kind — it is `equal_highs`/`equal_lows` with ≥ 3 constituents** (input to B's follow-up minor pass).

**Emit — equal highs (lows mirrored).** At the close where a swing (tier ≥ micro, §ST3) reaches CONFIRMED: if its `anchor_price` lies within **P-LQ-TOL** (= 0.10 ATR of the emitting timeframe at the current close, §24) of the anchor of ≥ 1 other CONFIRMED, non-superseded swing of the same side/timeframe not already a constituent of a live level at this price band, emit `LiquidityLevel{kind: equal_highs, price: max(constituent anchors), constituent_bar_ts: [...]}`, state = CONFIRMED. `price` = outermost extreme because that is the level a sweep must trade through. Constituent addition (another qualifying swing confirms later): successor fact with the enlarged constituent set; predecessor → SUPERSEDED.

**Emit — session levels.** At each 1D (resp. 1W) canonical candle close per §D4: emit `session_high` = that candle's `high` and `session_low` = its `low` on the source timeframe (1D/1W), state = CONFIRMED; simultaneously the previous period's session facts → **EXPIRED**. LTF charts consume them via FactStream timeframe filter.

**Sweep machine** — events appended to `state_history.detail` (CR-A-2, CR-B-4); level state changes only as shown. For a high-side level at price `P` (low-side mirrored):

| # | Event / transition | Trigger |
|---|---|---|
| L1 | event `SWEEP_START` | first bar with `high[B] > P` (wick suffices — §24 defines a sweep as *trade beyond and return*; this is normative, not a §30-5 question) |
| L2 | event `SWEEP_REJECTED`; state unchanged (CONFIRMED) | within **P-LQ-W** bars (default 3) of SWEEP_START: any `close < P`, **or** a CHoCH (§ST4) confirmed on the next lower timeframe in the opposing direction within the window (§24 "lower-timeframe structural reversal"; consumes same-instant LTF facts per ST0.4/§D5). Level may be swept again later (new SWEEP_START). |
| L3 | CONFIRMED → INVALIDATED (event `SWEEP_ACCEPTED`) | window of P-LQ-W bars elapses with every close ≥ P (price accepted beyond; liquidity consumed) |
| L4 | CONFIRMED → EXPIRED | session levels only: next period's canonical candle closes (rollover) |
| L5 | CONFIRMED → SUPERSEDED | constituent addition (equal_* kinds only); `cause_fact_id` = successor |

## ST7. Regime — mechanism scaffold (FINDING-014, partial)

What is fixed here (mechanism): regime is a per-`(symbol, timeframe)` singleton stream. At each bar close after warmup, the classifier (a deterministic function of committed Layer-2 facts — **the function itself pends item F**, per Draft B §S3) produces a value from the §25 nine-state enum. On the first classification, a Regime fact is emitted, state = CONFIRMED. On any close where the classification differs from the current live regime fact's value, a new Regime fact is emitted and the prior one → SUPERSEDED (`cause_fact_id` = successor). No PROVISIONAL, INVALIDATED, or EXPIRED. `supporting_evidence` per §S3 references the fact_ids the classifier consumed.

| # | From | To | Trigger |
|---|---|---|---|
| R1 | (none) | CONFIRMED | first classification after warmup |
| R2 | CONFIRMED | SUPERSEDED | classification changes at a bar close; successor emitted at same close |

**Assigned to item F (remainder of FINDING-014):** the classification function, per-state entry/exit thresholds, and hysteresis parameters. The transition *mechanics* above are complete and final.

## §30 mechanism resolutions

### M1. Break tolerance (§30 item 6; closes FINDING-024)

`tolerance(tf, B) = max(1 × tick_size, 0.05 × ATR14(tf) at close of B)`, both operands Decimal.
- `tick_size` = venue tick for the symbol (BTCUSDT/ETHUSDT spot = 0.01 USDT). The unquantified "small tick buffer" of §22 is pinned to **1 tick**.
- Every consumer (structural break §ST4, zone break Z4) records `{tick_component, atr_component, chosen}` in the fact (CR-B-6).
- **Rejected alternative:** 2-tick buffer — no evidence either way pre-research; 1 tick is the minimum that excludes exact-touch noise, and the parameter is registered tunable (§ST9) so research can revise it under versioning (§7).

### M2. Provisional vs tradable (§30 item 10)

- **PROVISIONAL** is mechanically defined by the tables above: a fact emitted whose confirmation criteria are not yet met. In v0 exactly one entity uses it: Swing (§ST3). Everything else is born CONFIRMED.
- **TRADABLE** is a Layer-3 (strategy) predicate over facts, not a Layer-2 state — deferred to v1 with the rest of Layer 3. The v0 rule of record is §6's own sentence: strategy scaffolding reads CONFIRMED facts only.
- **Rejected alternative:** adding a TRADABLE state to the §6 enum — rejected because tradability depends on strategy context (a fact tradable for one strategy is noise for another); baking it into Layer 2 would violate the layer boundary (§3).

### M3. Tier promotion function (§30 item 2 — mechanism half)

Promotion emits a **successor fact** (same anchor, higher tier); predecessor → SUPERSEDED (SW3); successor carries `predecessor_fact_ids` (CR-A-1). Written for highs; lows mirrored.

- **micro → local:** at any bar close after confirmation, if the downward excursion from the anchor — `anchor_price − min(low[j] for j in (X+2 .. now])` — first reaches ≥ **θ_local** × ATR14(tf) at the *evaluation* close (θ_local = 0.75, §20 given), promote at that close. The promotion window closes permanently if price violates the anchor first, per **P-SW-VIOL** (violation predicate pends §30 item 5: recommended `close > anchor_price`; wick-based is the alternative). ATR at the evaluation close (not the anchor close) is pinned so anchors inside ATR warmup remain promotable.
- **local → structural:** promote when a StructureBreak (§ST4) is confirmed whose breaking leg originates at this swing — pinned attribution: this swing is the most recent CONFIRMED opposite-side swing of tier ≥ local on the timeframe prior to the break bar — **or** when displacement ≥ **θ_disp** × ATR (θ_disp pends item F). §20's third clause ("significant directional leg") is demoted to recorded evidence per FINDING-008's accepted remedy.
- **local/structural → major:** major is HTF macro structure (§20, "by chart"). Promotion rule **pends item F** (bound up with §30 item 9, HTF influence). Slot registered as **P-SW-MAJOR**.

### M4. Retest definition and expiration (§30 item 8)

Defined relative to a broken level `L` (StructureBreak) or broken zone edge, break downward (upward mirrored):
- **Window:** opens at the break close; spans **P-RT-W** bars (default 20, tunable) on the break's timeframe.
- **Contact:** first bar B in the window with `high[B] ≥ L − P-RT-TOL`, where P-RT-TOL = 0.10 × ATR14(tf) at close of B (reuses the §24 tolerance scale).
- **Rejection:** within **P-RT-R** bars of contact (default 3, counting the contact bar), a close below `L − tolerance` (§M1) with no intervening close above `L` (a close back above `L` is a **reclaim** → retest failed, recorded as evidence).
- **Expiration:** no contact within P-RT-W bars → retest opportunity expires. Recorded as an evidence annotation on the break/zone fact (`state_history.detail`), **not** an envelope state — EXPIRED the fact-state is reserved per §ST1.
- The *definition* above is independent of §30 item 7; only the retest's **role** (whether it gates zone flip) depends on the user's item-7 answer (Z6 branches).

## ST9. Parameter registry

| Param | Meaning | Value / default | Status |
|---|---|---|---|
| P-SW-TIE | fractal tie rule (exact-equal neighbor disqualifies) | strict `>` both sides; right-side `≥` invalidates | mechanism default — ratify at F |
| P-SW-VIOL | swing-anchor violation predicate (promotion window close) | recommended close-beyond | **pends §30 item 5 (user)** |
| P-SW-MAJOR | major-tier promotion rule | — | **pends F (§30 items 2/9)** |
| θ_local | micro→local excursion threshold | 0.75 ATR | given by §20; tunable research default |
| θ_disp | local→structural displacement threshold | — | **pends F** |
| P-SB-TIER | reference-swing tier for BOS / CHoCH | recommended local (CHoCH) / structural (BOS) | **pends §30 item 4 (user)** |
| P-SB-LABEL | BOS/CHoCH labeling vs prevailing direction; first-break = BOS | as §ST4.3 | mechanism default — ratify at F |
| M1 tolerance | break tolerance | max(1 tick, 0.05 ATR) | **pinned (§30 item 6)** |
| P-ZN-KWEAK / P-ZN-PWEAK | zone weakening: test count / max penetration | 2 / 0.75 | tunable research defaults |
| P-ZN-INVAL | zone invalidation trigger | full_wick_sweep | mechanism default — ratify at F |
| P-ZN-FLIP | flip rule branch A/B | both drafted (Z6) | **pends §30 item 7 (user)** |
| P-ZN-MERGE | merge overlap threshold at creation | any overlap | tunable research default |
| P-LQ-TOL | equal-highs/lows tolerance | 0.10 ATR | given by §24 |
| P-LQ-W | sweep resolution window | 3 bars | tunable research default |
| P-RT-W / P-RT-R / P-RT-TOL | retest window / rejection window / contact tolerance | 20 bars / 3 bars / 0.10 ATR | **pinned mechanism (§30 item 8)**; numeric values tunable |

All tunables are configuration under §7 versioning: changing one is a new `algo_version`/config version, never an in-place edit.

## ST10. Change requests against Drafts A and B

Filed for the already-scheduled follow-up minor pass (with B-04/B-05/B-06 and R-01..R-07); none reopen closed findings — they are consequences of the emit-once principle (ST0.3) that only became visible once transitions were tabled.

- **CR-A-1 (Draft A §D8.2):** add envelope field `predecessor_fact_ids?: [str]` to the **included** hash set (immutable at emit; anchors successor lineage for §M3, merge, flip, constituent addition).
- **CR-A-2 (Draft A / B §S2):** extend `state_history` entries with optional `detail: dict` (hash-excluded already) — carries lifecycle events, sweep events, penetration values, protected annotations, retest evidence.
- **CR-B-1 (§S3 SwingBody):** remove `confirmation_bar_ts` from the body — derived from the CONFIRMED `state_history` entry. Mutable body fields violate §D8 identity.
- **CR-B-2 (§S3 SwingBody):** remove `protected` from the hashed body — protected status is annotation events (§ST3).
- **CR-B-3 (§S3 ZoneBody):** move `lifecycle` and `touch_history` out of the body to envelope-level hash-excluded fields `lifecycle` + `lifecycle_history`; body keeps `{kind, top, bottom, origin_bar_ts, source_fact_ids}`.
- **CR-B-4 (§S3 LiquidityLevelBody):** remove `swept_bar_ts` / `rejection_bar_ts` — derived from sweep events.
- **CR-B-5 (§S3):** note that `flipped_demand`/`flipped_supply` kinds denote **successor** facts created at Z6; the predecessor keeps its original kind with lifecycle FLIPPED.
- **CR-B-6 (§S3 StructureBreakBody):** `tolerance_used` becomes `{tolerance_used, tick_component, atr_component, chosen}` (implements deferred B-05; consumed by §M1).

## ST11. Additions to the item-F working-session agenda

Beyond the six §30 methodology questions already queued, this draft surfaces:
1. **Zone creation predicates** (which §23 sources produce zones; band construction) — genuinely new, was never specified anywhere. Largest addition; without it the zone engine cannot start.
2. **Ratification list** (mechanism defaults, ~30 seconds each): P-SW-TIE, P-SB-LABEL, P-ZN-INVAL.

## Open items requiring user sign-off

1. The four parameters marked **pends §30 item N (user)** in §ST9 — unchanged from the remediation plan's six methodology questions; this draft narrows each to a concrete either/or where possible (Z6 branches; P-SW-VIOL close-vs-wick).
2. §ST11 additions to the F session.
3. Confirm the emit-once consequence that confirmed swings are never price-invalidated (§ST3) — architect holds this is the right call for auditability, but it changes how "intact swing" queries are expressed and the user should be aware.
